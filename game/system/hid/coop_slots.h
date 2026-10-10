#pragma once

/*!
 * @file coop_slots.h
 * Explicit device -> player slot assignment for local split-screen co-op.
 *
 * This is deliberately free of SDL so the assignment rules can be unit tested.
 * Controllers are identified by their SDL instance id, which is unique for as long as the device
 * stays connected. The GUID only identifies the controller model (two identical pads share it),
 * so it is used only as a preference when a disconnected slot gets a device back.
 *
 * Rules:
 * - every device feeds at most one slot (a device can never control both players)
 * - assigning a device that already belongs to another slot is rejected, never silently moved
 * - when a slot's controller disconnects, the slot keeps its claim and reports "disconnected";
 *   another player's device is never moved into it
 * - a disconnected slot is refilled automatically only by a newly connected controller with the
 *   same GUID (one that wasn't connected before), otherwise by an unassigned controller pressing a
 *   button
 */

#include <array>
#include <string>
#include <vector>

#include "common/common_types.h"

namespace coop {

constexpr int kMaxPlayers = 2;

enum class DeviceKind : u8 { NONE = 0, KEYBOARD_MOUSE = 1, CONTROLLER = 2 };

struct ConnectedController {
  int instance_id = -1;
  std::string guid;
};

struct SlotState {
  DeviceKind kind = DeviceKind::NONE;
  /// SDL instance id of the controller, -1 if none or disconnected.
  int instance_id = -1;
  /// GUID of the last controller used by this slot, kept across disconnects.
  std::string guid;
  bool connected = false;
};

/// Bits returned by SlotAssigner::status_bits, mirrored in GOAL (pc-coop-slot-status).
enum StatusBits : u32 {
  KIND_MASK = 0x3,  // DeviceKind
  CONNECTED = 0x4,
  JOINING = 0x8,
};

class SlotAssigner {
 public:
  bool assign_keyboard(int slot);
  bool assign_controller(int slot, int instance_id, const std::string& guid);
  void unassign(int slot);
  void unassign_all();

  /// The next unassigned device that presses a button is assigned to this slot.
  void begin_join(int slot);
  void cancel_join() { m_joining_slot = -1; }
  int joining_slot() const { return m_joining_slot; }

  /// An unassigned controller pressed a button. Returns true if it claimed a slot.
  bool on_controller_button(int instance_id, const std::string& guid);
  /// A key was pressed. Only claims a slot when a slot is explicitly joining.
  bool on_keyboard_key();
  /// The set of connected controllers changed. Returns true if any slot changed.
  bool on_controllers_changed(const std::vector<ConnectedController>& controllers);
  /// Remember the connected controllers without changing slots (used while co-op is off), so they
  /// don't count as newly connected later.
  void note_controllers(const std::vector<ConnectedController>& controllers);

  /// Default assignment: two or more controllers -> controllers 0 and 1;
  /// otherwise keyboard/mouse is player 1 and the first controller (if any) is player 2.
  /// With two or more controllers, player1_instance_id (the pad that is player 1 right now, if
  /// connected) stays player 1, so starting co-op never moves the current player to slot 2.
  void auto_assign(const std::vector<ConnectedController>& controllers,
                   int player1_instance_id = -1);

  const SlotState& slot(int slot) const { return m_slots.at(slot); }
  int slot_for_controller(int instance_id) const;
  int keyboard_slot() const;
  bool any_assigned() const;
  u32 status_bits(int slot) const;

 private:
  static bool valid_slot(int slot) { return slot >= 0 && slot < kMaxPlayers; }
  int first_claimable_slot() const;

  std::array<SlotState, kMaxPlayers> m_slots;
  int m_joining_slot = -1;
  /// instance ids of the controllers connected at the last update
  std::vector<int> m_known_ids;
};

}  // namespace coop
