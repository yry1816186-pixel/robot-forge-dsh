#include <unity.h>

#include "protocol.h"

void test_parses_emotion() {
  Message m = parseLine("EMO happy", 9);
  TEST_ASSERT_TRUE(m.ok);
  TEST_ASSERT_EQUAL_INT(static_cast<int>(MsgType::Emo), static_cast<int>(m.type));
  TEST_ASSERT_EQUAL_STRING("happy", m.word);
}

void test_is_case_insensitive() {
  Message m = parseLine("emo HAPPY", 9);
  TEST_ASSERT_TRUE(m.ok);
  TEST_ASSERT_EQUAL_STRING("happy", m.word);
}

void test_parses_pose() {
  Message m = parseLine("POSE 30 -10", 11);
  TEST_ASSERT_TRUE(m.ok);
  TEST_ASSERT_EQUAL_INT(30, m.a);
  TEST_ASSERT_EQUAL_INT(-10, m.b);
}

void test_rejects_pose_out_of_range() {
  TEST_ASSERT_FALSE(parseLine("POSE 90 0", 9).ok);
  TEST_ASSERT_FALSE(parseLine("POSE 0 90", 9).ok);
}

void test_parses_led() {
  Message m = parseLine("LED 255 128 0", 13);
  TEST_ASSERT_TRUE(m.ok);
  TEST_ASSERT_EQUAL_INT(255, m.a);
  TEST_ASSERT_EQUAL_INT(128, m.b);
  TEST_ASSERT_EQUAL_INT(0, m.c);
}

void test_rejects_bad_led() {
  TEST_ASSERT_FALSE(parseLine("LED 300 0 0", 11).ok);
}

void test_parses_mic_and_vol() {
  TEST_ASSERT_TRUE(parseLine("MIC ON", 6).ok);
  TEST_ASSERT_TRUE(parseLine("VOL 60", 6).ok);
  TEST_ASSERT_FALSE(parseLine("VOL 101", 7).ok);
}

void test_parses_events() {
  TEST_ASSERT_TRUE(parseLine("TOUCH head", 10).ok);
  TEST_ASSERT_TRUE(parseLine("DIST 620", 8).ok);
  TEST_ASSERT_TRUE(parseLine("READY", 5).ok);
  TEST_ASSERT_TRUE(parseLine("ERR stall", 9).ok);
}

void test_rejects_unknown() {
  TEST_ASSERT_FALSE(parseLine("FLY 3", 5).ok);
  TEST_ASSERT_FALSE(parseLine("", 0).ok);
  TEST_ASSERT_FALSE(parseLine("EMO angry", 9).ok);
  TEST_ASSERT_FALSE(parseLine("READY now", 9).ok);
}

void test_rejects_overlong_and_garbage() {
  TEST_ASSERT_FALSE(parseLine("POSE 1 2 3", 10).ok);
  TEST_ASSERT_FALSE(parseLine("POSE x y", 8).ok);
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_parses_emotion);
  RUN_TEST(test_is_case_insensitive);
  RUN_TEST(test_parses_pose);
  RUN_TEST(test_rejects_pose_out_of_range);
  RUN_TEST(test_parses_led);
  RUN_TEST(test_rejects_bad_led);
  RUN_TEST(test_parses_mic_and_vol);
  RUN_TEST(test_parses_events);
  RUN_TEST(test_rejects_unknown);
  RUN_TEST(test_rejects_overlong_and_garbage);
  return UNITY_END();
}
