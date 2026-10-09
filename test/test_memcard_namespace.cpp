// Save folder namespace used by Jak 1 local co-op (AI-assisted).
#include "game/kernel/common/kmemcard.h"
#include "gtest/gtest.h"

TEST(MemcardNamespace, AcceptsPlainNames) {
  kmemcard_init_globals();
  EXPECT_EQ(mc_set_namespace("coop"), 1);
  EXPECT_EQ(mc_set_namespace("coop_2-b"), 1);
  EXPECT_EQ(mc_set_namespace(""), 1);
}

TEST(MemcardNamespace, RejectsPaths) {
  kmemcard_init_globals();
  EXPECT_EQ(mc_set_namespace(".."), -1);
  EXPECT_EQ(mc_set_namespace("../saves"), -1);
  EXPECT_EQ(mc_set_namespace("a/b"), -1);
  EXPECT_EQ(mc_set_namespace("a\\b"), -1);
  EXPECT_EQ(mc_set_namespace("/abs"), -1);
  EXPECT_EQ(mc_set_namespace(std::string(33, 'a')), -1);
}
