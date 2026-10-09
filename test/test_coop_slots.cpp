#include "game/system/hid/coop_slots.h"
#include "gtest/gtest.h"

using namespace coop;

namespace {
// two physical pads of the same model share a GUID, only the instance id differs
const std::string kXbox = "xbox-guid";
const std::string kDs4 = "ds4-guid";
}  // namespace

TEST(CoopSlots, AutoAssignTwoControllers) {
  SlotAssigner a;
  a.auto_assign({{10, kXbox}, {11, kDs4}});
  EXPECT_EQ(a.slot(0).kind, DeviceKind::CONTROLLER);
  EXPECT_EQ(a.slot(0).instance_id, 10);
  EXPECT_EQ(a.slot(1).kind, DeviceKind::CONTROLLER);
  EXPECT_EQ(a.slot(1).instance_id, 11);
  EXPECT_EQ(a.keyboard_slot(), -1);
}

TEST(CoopSlots, AutoAssignKeyboardAndOneController) {
  SlotAssigner a;
  a.auto_assign({{10, kXbox}});
  EXPECT_EQ(a.keyboard_slot(), 0);
  EXPECT_EQ(a.slot_for_controller(10), 1);
  EXPECT_TRUE(a.status_bits(0) & StatusBits::CONNECTED);
  EXPECT_TRUE(a.status_bits(1) & StatusBits::CONNECTED);
}

TEST(CoopSlots, AutoAssignNoControllers) {
  SlotAssigner a;
  a.auto_assign({});
  EXPECT_EQ(a.keyboard_slot(), 0);
  EXPECT_EQ(a.slot(1).kind, DeviceKind::NONE);
  EXPECT_FALSE(a.status_bits(1) & StatusBits::CONNECTED);
}

TEST(CoopSlots, DeviceCannotDriveBothSlots) {
  SlotAssigner a;
  EXPECT_TRUE(a.assign_controller(0, 10, kXbox));
  EXPECT_FALSE(a.assign_controller(1, 10, kXbox));
  EXPECT_EQ(a.slot(1).kind, DeviceKind::NONE);
  EXPECT_EQ(a.slot_for_controller(10), 0);

  EXPECT_TRUE(a.assign_keyboard(1));
  EXPECT_FALSE(a.assign_keyboard(0));
  EXPECT_EQ(a.keyboard_slot(), 1);
  // re-assigning to the same slot is fine
  EXPECT_TRUE(a.assign_keyboard(1));
  EXPECT_TRUE(a.assign_controller(0, 10, kXbox));
}

TEST(CoopSlots, IdenticalControllersAreSeparatePlayers) {
  SlotAssigner a;
  a.auto_assign({{10, kXbox}, {11, kXbox}});
  EXPECT_EQ(a.slot_for_controller(10), 0);
  EXPECT_EQ(a.slot_for_controller(11), 1);
}

TEST(CoopSlots, DisconnectKeepsClaimAndDoesNotReassignOtherDevice) {
  SlotAssigner a;
  a.auto_assign({{10, kXbox}, {11, kDs4}});
  // player 2's pad is unplugged
  EXPECT_TRUE(a.on_controllers_changed({{10, kXbox}}));
  EXPECT_EQ(a.slot(1).kind, DeviceKind::CONTROLLER);
  EXPECT_FALSE(a.status_bits(1) & StatusBits::CONNECTED);
  // player 1's pad keeps feeding only player 1
  EXPECT_EQ(a.slot_for_controller(10), 0);
  // player 1 pressing buttons must not claim player 2's slot
  EXPECT_FALSE(a.on_controller_button(10, kXbox));
  EXPECT_EQ(a.slot_for_controller(10), 0);
}

TEST(CoopSlots, ReconnectSameModelRefillsSlot) {
  SlotAssigner a;
  a.auto_assign({{10, kXbox}, {11, kDs4}});
  a.on_controllers_changed({{10, kXbox}});
  // the DS4 comes back with a new instance id
  EXPECT_TRUE(a.on_controllers_changed({{10, kXbox}, {12, kDs4}}));
  EXPECT_EQ(a.slot_for_controller(12), 1);
  EXPECT_TRUE(a.status_bits(1) & StatusBits::CONNECTED);
}

TEST(CoopSlots, DifferentModelNeedsButtonPressToClaim) {
  SlotAssigner a;
  a.auto_assign({{10, kXbox}, {11, kDs4}});
  a.on_controllers_changed({{10, kXbox}});
  // a different pad is plugged in: not assigned automatically
  EXPECT_FALSE(a.on_controllers_changed({{10, kXbox}, {13, kXbox}}));
  EXPECT_EQ(a.slot_for_controller(13), -1);
  // ... until it presses a button
  EXPECT_TRUE(a.on_controller_button(13, kXbox));
  EXPECT_EQ(a.slot_for_controller(13), 1);
}

TEST(CoopSlots, IdenticalModelReconnectOnlyFillsDisconnectedSlot) {
  SlotAssigner a;
  a.auto_assign({{10, kXbox}, {11, kXbox}});
  a.on_controllers_changed({{11, kXbox}});  // player 1's pad drops
  EXPECT_FALSE(a.status_bits(0) & StatusBits::CONNECTED);
  EXPECT_TRUE(a.on_controllers_changed({{11, kXbox}, {14, kXbox}}));
  EXPECT_EQ(a.slot_for_controller(14), 0);
  EXPECT_EQ(a.slot_for_controller(11), 1);
}

TEST(CoopSlots, JoinFlow) {
  SlotAssigner a;
  a.assign_keyboard(0);
  // keyboard presses never claim a slot unless one is joining
  EXPECT_FALSE(a.on_keyboard_key());
  a.begin_join(1);
  EXPECT_TRUE(a.status_bits(1) & StatusBits::JOINING);
  // keyboard already belongs to player 1, so it can't join as player 2
  EXPECT_FALSE(a.on_keyboard_key());
  EXPECT_TRUE(a.on_controller_button(20, kDs4));
  EXPECT_EQ(a.slot_for_controller(20), 1);
  EXPECT_EQ(a.joining_slot(), -1);
}

TEST(CoopSlots, UnassignedButtonClaimsFirstFreeSlot) {
  SlotAssigner a;
  EXPECT_TRUE(a.on_controller_button(30, kDs4));
  EXPECT_EQ(a.slot_for_controller(30), 0);
  EXPECT_TRUE(a.on_controller_button(31, kDs4));
  EXPECT_EQ(a.slot_for_controller(31), 1);
  // no free slot left
  EXPECT_FALSE(a.on_controller_button(32, kDs4));
  EXPECT_EQ(a.slot_for_controller(32), -1);
}

TEST(CoopSlots, InvalidSlotsRejected) {
  SlotAssigner a;
  EXPECT_FALSE(a.assign_keyboard(2));
  EXPECT_FALSE(a.assign_controller(-1, 1, kXbox));
  EXPECT_FALSE(a.assign_controller(0, -1, kXbox));
  EXPECT_EQ(a.status_bits(5), 0u);
}
