#include "game/graphics/opengl_renderer/SplitscreenLayout.h"
#include "gtest/gtest.h"

using namespace splitscreen;

TEST(SplitscreenLayout, SideBySide1080p) {
  auto r = view_rects(1920, 1080, Layout::SIDE_BY_SIDE);
  // player 1 on the left, player 2 on the right, same size, full height
  EXPECT_EQ(r[0].x, 0);
  EXPECT_EQ(r[0].y, 0);
  EXPECT_EQ(r[0].h, 1080);
  EXPECT_EQ(r[1].h, 1080);
  EXPECT_EQ(r[0].w, r[1].w);
  EXPECT_EQ(r[1].x + r[1].w, 1920);
  // a divider, and no overlap
  EXPECT_GT(r[1].x, r[0].x + r[0].w);
  EXPECT_LE(r[1].x - (r[0].x + r[0].w), 6);
}

TEST(SplitscreenLayout, TopBottom1080p) {
  auto r = view_rects(1920, 1080, Layout::TOP_BOTTOM);
  // GL origin is the bottom left: player 1 (top) has the larger y
  EXPECT_EQ(r[0].y + r[0].h, 1080);
  EXPECT_EQ(r[1].y, 0);
  EXPECT_EQ(r[0].w, 1920);
  EXPECT_EQ(r[1].w, 1920);
  EXPECT_EQ(r[0].h, r[1].h);
  EXPECT_GT(r[0].y, r[1].y + r[1].h);
}

TEST(SplitscreenLayout, ViewsStayInsideFramebuffer) {
  for (int w : {1, 2, 3, 320, 641, 1280, 2560, 3840}) {
    for (int h : {1, 2, 3, 240, 481, 720, 1440, 2160}) {
      for (auto layout : {Layout::SIDE_BY_SIDE, Layout::TOP_BOTTOM}) {
        for (const auto& v : view_rects(w, h, layout)) {
          EXPECT_GE(v.w, 1);
          EXPECT_GE(v.h, 1);
          EXPECT_GE(v.x, 0);
          EXPECT_GE(v.y, 0);
          // tiny framebuffers may not fit two views plus a divider, but never exceed the buffer
          EXPECT_LE(v.x + v.w, std::max(w, 1));
          EXPECT_LE(v.y + v.h, std::max(h, 1));
        }
      }
    }
  }
}

TEST(SplitscreenLayout, LayoutFromInt) {
  EXPECT_EQ(layout_from_int(0), Layout::SIDE_BY_SIDE);
  EXPECT_EQ(layout_from_int(1), Layout::TOP_BOTTOM);
  EXPECT_EQ(layout_from_int(42), Layout::SIDE_BY_SIDE);
}
