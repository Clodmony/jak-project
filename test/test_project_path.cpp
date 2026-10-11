// Written with AI assistance (AI-assisted).
#include <fstream>

#include "common/util/FileUtil.h"

#include "gtest/gtest.h"



namespace {
fs::path make_repo(const fs::path& root) {
  fs::create_directories(root / "goal_src");
  fs::create_directories(root / "decompiler" / "config");
  fs::create_directories(root / "build" / "goalc");
  fs::ofstream(root / "build" / "goalc" / "goalc") << "";
  return root;
}
}  // namespace

TEST(ProjectPath, FoundByMarkersUnderAnotherFolderName) {
  const auto tmp = fs::temp_directory_path() / "opengoal-project-path-test";
  fs::remove_all(tmp);
  const auto repo = make_repo(tmp / "opengoal-coop");
  const auto found = file_util::try_get_project_path_by_markers(repo / "build" / "goalc" / "goalc");
  ASSERT_TRUE(found.has_value());
  EXPECT_EQ(fs::path(*found), repo);
  fs::remove_all(tmp);
}

TEST(ProjectPath, NoRepoAbove) {
  const auto tmp = fs::temp_directory_path() / "opengoal-project-path-test-none";
  fs::remove_all(tmp);
  fs::create_directories(tmp / "bin");
  EXPECT_FALSE(file_util::try_get_project_path_by_markers(tmp / "bin" / "goalc").has_value());
  fs::remove_all(tmp);
}

TEST(ProjectPath, NameRuleUnchanged) {
  EXPECT_EQ(*file_util::try_get_project_path_from_path("/home/u/jak-project/build/goalc/goalc"),
            "/home/u/jak-project");
  EXPECT_FALSE(file_util::try_get_project_path_from_path("/home/u/opengoal-coop/build/goalc/goalc")
                   .has_value());
}
