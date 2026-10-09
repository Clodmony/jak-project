#include "coop_slots.h"

namespace coop {

bool SlotAssigner::assign_keyboard(int slot) {
  if (!valid_slot(slot)) {
    return false;
  }
  const int current = keyboard_slot();
  if (current >= 0 && current != slot) {
    // keyboard/mouse already belongs to the other player
    return false;
  }
  m_slots[slot] = SlotState{DeviceKind::KEYBOARD_MOUSE, -1, "", true};
  if (m_joining_slot == slot) {
    m_joining_slot = -1;
  }
  return true;
}

bool SlotAssigner::assign_controller(int slot, int instance_id, const std::string& guid) {
  if (!valid_slot(slot) || instance_id < 0) {
    return false;
  }
  const int current = slot_for_controller(instance_id);
  if (current >= 0 && current != slot) {
    // this controller already belongs to the other player
    return false;
  }
  m_slots[slot] = SlotState{DeviceKind::CONTROLLER, instance_id, guid, true};
  if (m_joining_slot == slot) {
    m_joining_slot = -1;
  }
  return true;
}

void SlotAssigner::unassign(int slot) {
  if (valid_slot(slot)) {
    m_slots[slot] = SlotState{};
  }
}

void SlotAssigner::unassign_all() {
  for (int i = 0; i < kMaxPlayers; i++) {
    unassign(i);
  }
  m_joining_slot = -1;
}

void SlotAssigner::begin_join(int slot) {
  if (valid_slot(slot)) {
    m_joining_slot = slot;
  }
}

int SlotAssigner::first_claimable_slot() const {
  for (int i = 0; i < kMaxPlayers; i++) {
    const auto& s = m_slots[i];
    if (s.kind == DeviceKind::NONE || (s.kind == DeviceKind::CONTROLLER && !s.connected)) {
      return i;
    }
  }
  return -1;
}

bool SlotAssigner::on_controller_button(int instance_id, const std::string& guid) {
  if (instance_id < 0 || slot_for_controller(instance_id) >= 0) {
    return false;
  }
  const int target = valid_slot(m_joining_slot) ? m_joining_slot : first_claimable_slot();
  if (target < 0) {
    return false;
  }
  return assign_controller(target, instance_id, guid);
}

bool SlotAssigner::on_keyboard_key() {
  if (!valid_slot(m_joining_slot)) {
    return false;
  }
  return assign_keyboard(m_joining_slot);
}

bool SlotAssigner::on_controllers_changed(const std::vector<ConnectedController>& controllers) {
  bool changed = false;
  // 1. mark slots whose controller went away as disconnected, but keep their claim
  for (auto& s : m_slots) {
    if (s.kind != DeviceKind::CONTROLLER || !s.connected) {
      continue;
    }
    bool still_present = false;
    for (const auto& c : controllers) {
      if (c.instance_id == s.instance_id) {
        still_present = true;
        break;
      }
    }
    if (!still_present) {
      s.connected = false;
      s.instance_id = -1;
      changed = true;
    }
  }
  // 2. a newly connected, unassigned controller of the same model refills a disconnected slot
  // (an idle pad of the same model that was already connected doesn't take it over)
  for (const auto& c : controllers) {
    if (slot_for_controller(c.instance_id) >= 0) {
      continue;
    }
    bool known = false;
    for (int id : m_known_ids) {
      if (id == c.instance_id) {
        known = true;
        break;
      }
    }
    if (known) {
      continue;
    }
    for (int i = 0; i < kMaxPlayers; i++) {
      auto& s = m_slots[i];
      if (s.kind == DeviceKind::CONTROLLER && !s.connected && !s.guid.empty() && s.guid == c.guid) {
        s.instance_id = c.instance_id;
        s.connected = true;
        changed = true;
        break;
      }
    }
  }
  note_controllers(controllers);
  return changed;
}

void SlotAssigner::note_controllers(const std::vector<ConnectedController>& controllers) {
  m_known_ids.clear();
  for (const auto& c : controllers) {
    m_known_ids.push_back(c.instance_id);
  }
}

void SlotAssigner::auto_assign(const std::vector<ConnectedController>& controllers,
                               int player1_instance_id) {
  note_controllers(controllers);
  unassign_all();
  if (controllers.size() >= 2) {
    size_t first = 0;
    for (size_t i = 0; i < controllers.size(); i++) {
      if (player1_instance_id >= 0 && controllers[i].instance_id == player1_instance_id) {
        first = i;
        break;
      }
    }
    const size_t second = first == 0 ? 1 : 0;
    assign_controller(0, controllers[first].instance_id, controllers[first].guid);
    assign_controller(1, controllers[second].instance_id, controllers[second].guid);
  } else {
    assign_keyboard(0);
    if (controllers.size() == 1) {
      assign_controller(1, controllers[0].instance_id, controllers[0].guid);
    }
  }
}

int SlotAssigner::slot_for_controller(int instance_id) const {
  if (instance_id < 0) {
    return -1;
  }
  for (int i = 0; i < kMaxPlayers; i++) {
    const auto& s = m_slots[i];
    if (s.kind == DeviceKind::CONTROLLER && s.connected && s.instance_id == instance_id) {
      return i;
    }
  }
  return -1;
}

int SlotAssigner::keyboard_slot() const {
  for (int i = 0; i < kMaxPlayers; i++) {
    if (m_slots[i].kind == DeviceKind::KEYBOARD_MOUSE) {
      return i;
    }
  }
  return -1;
}

bool SlotAssigner::any_assigned() const {
  for (const auto& s : m_slots) {
    if (s.kind != DeviceKind::NONE) {
      return true;
    }
  }
  return false;
}

u32 SlotAssigner::status_bits(int slot) const {
  if (!valid_slot(slot)) {
    return 0;
  }
  const auto& s = m_slots[slot];
  u32 bits = (u32)s.kind & KIND_MASK;
  if (s.connected) {
    bits |= CONNECTED;
  }
  if (m_joining_slot == slot) {
    bits |= JOINING;
  }
  return bits;
}

}  // namespace coop
