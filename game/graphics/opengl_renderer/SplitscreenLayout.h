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

/// Width in pixels of the divider between the views (half in each player's colour).
inline int divider_size(int w, int h, Layout layout) {
  const int along = layout == Layout::TOP_BOTTOM ? h : w;
  return std::max(4, along / 320);
}

/// The players' colours (RGB, 0-1), also used for their label in GOAL (coop-draw-player-labels).
constexpr std::array<std::array<float, 3>, kMaxViews> kPlayerColors = {{
    {0.25f, 0.55f, 1.0f},  // player 1: blue
    {1.0f, 0.55f, 0.0f},   // player 2: orange
}};

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

/// The divider between the views of a w x h framebuffer, split in two: the half next to player 1's
/// view, then the half next to player 2's (drawn in their colours). Empty rects if there is no gap.
inline std::array<Rect, kMaxViews> divider_rects(int w, int h, Layout layout) {
  const auto v = view_rects(w, h, layout);
  if (layout == Layout::TOP_BOTTOM) {
    // player 1 on top: the gap is between the top of view 1 and the bottom of view 0
    const int lo = v[1].y + v[1].h;
    const int hi = v[0].y;
    const int gap = std::max(0, hi - lo);
    const int p2 = gap / 2;
    return {Rect{0, lo + p2, w, gap - p2}, Rect{0, lo, w, p2}};
  }
  const int lo = v[0].x + v[0].w;
  const int hi = v[1].x;
  const int gap = std::max(0, hi - lo);
  const int p1 = gap - gap / 2;
  return {Rect{lo, 0, p1, h}, Rect{lo + p1, 0, gap - p1, h}};
}

inline Layout layout_from_int(int value) {
  return value == (int)Layout::TOP_BOTTOM ? Layout::TOP_BOTTOM : Layout::SIDE_BY_SIDE;
}

}  // namespace splitscreen
