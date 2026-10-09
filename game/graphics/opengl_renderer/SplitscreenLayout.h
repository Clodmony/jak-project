#pragma once

/*!
 * @file SplitscreenLayout.h
 * Viewport layout for local split-screen co-op (Jak 1).
 *
 * Each view is rendered at the origin of its own framebuffer (so full-framebuffer effects and the
 * GS scissor emulation keep working unchanged), then copied into its rect of the game framebuffer.
 */

#include <algorithm>
#include <array>

namespace splitscreen {

constexpr int kMaxViews = 2;

enum class Layout : int {
  SIDE_BY_SIDE = 0,  // player 1 left, player 2 right
  TOP_BOTTOM = 1,    // player 1 top, player 2 bottom
};

/// A rectangle in OpenGL framebuffer coordinates (origin at the bottom left).
struct Rect {
  int x = 0;
  int y = 0;
  int w = 0;
  int h = 0;
};

/// Width in pixels of the black divider between the views.
inline int divider_size(int w, int h, Layout layout) {
  const int along = layout == Layout::TOP_BOTTOM ? h : w;
  return std::max(2, along / 480);
}

/// Rects of the two views inside a w x h framebuffer. View 0 is player 1.
inline std::array<Rect, kMaxViews> view_rects(int w, int h, Layout layout) {
  const int gap = divider_size(w, h, layout);
  if (layout == Layout::TOP_BOTTOM) {
    const int vh = std::max(1, (h - gap) / 2);
    return {Rect{0, h - vh, w, vh}, Rect{0, 0, w, vh}};
  }
  const int vw = std::max(1, (w - gap) / 2);
  return {Rect{0, 0, vw, h}, Rect{w - vw, 0, vw, h}};
}

inline Layout layout_from_int(int value) {
  return value == (int)Layout::TOP_BOTTOM ? Layout::TOP_BOTTOM : Layout::SIDE_BY_SIDE;
}

}  // namespace splitscreen
