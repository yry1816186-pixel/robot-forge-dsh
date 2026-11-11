#include <unity.h>

#include "drive.h"
#include "protocol.h"

void setUp(void) {}
void tearDown(void) {}

void test_ping(void) {
  const rover::Command cmd = rover::parse_command("PING");
  TEST_ASSERT_EQUAL(static_cast<int>(rover::CmdType::kPing), static_cast<int>(cmd.type));
}

void test_stop(void) {
  const rover::Command cmd = rover::parse_command("S");
  TEST_ASSERT_EQUAL(static_cast<int>(rover::CmdType::kStop), static_cast<int>(cmd.type));
}

void test_velocity(void) {
  const rover::Command cmd = rover::parse_command("V 200 -300");
  TEST_ASSERT_EQUAL(static_cast<int>(rover::CmdType::kVelocity), static_cast<int>(cmd.type));
  TEST_ASSERT_EQUAL_INT(200, cmd.linear_mm_s);
  TEST_ASSERT_EQUAL_INT(-300, cmd.angular_mrad_s);
}

void test_trim_crlf(void) {
  const rover::Command cmd = rover::parse_command("V 100 0\r");
  TEST_ASSERT_EQUAL_INT(100, cmd.linear_mm_s);
}

void test_wrong_count(void) {
  TEST_ASSERT_EQUAL_INT(3, rover::parse_command("V 100").error);
  TEST_ASSERT_EQUAL_INT(3, rover::parse_command("V 100 0 9").error);
}

void test_not_a_number(void) {
  TEST_ASSERT_EQUAL_INT(4, rover::parse_command("V fast 0").error);
}

void test_out_of_range(void) {
  TEST_ASSERT_EQUAL_INT(5, rover::parse_command("V 401 0").error);
  TEST_ASSERT_EQUAL_INT(5, rover::parse_command("V 0 -1201").error);
}

void test_too_long(void) {
  TEST_ASSERT_EQUAL_INT(1, rover::parse_command(std::string(60, 'V')).error);
}

void test_unknown(void) {
  TEST_ASSERT_EQUAL_INT(2, rover::parse_command("FLY").error);
  TEST_ASSERT_EQUAL_INT(2, rover::parse_command("").error);
}

void test_telemetry_format(void) {
  char out[64];
  const size_t n = rover::format_telemetry(out, sizeof(out), 0, 0, 410, 15, 7810);
  TEST_ASSERT_GREATER_THAN(0, n);
  TEST_ASSERT_EQUAL_STRING("T 0 0 410 15 7810", out);
}

void test_telemetry_small_buffer(void) {
  char out[8];
  TEST_ASSERT_EQUAL_UINT32(0, rover::format_telemetry(out, sizeof(out), 0, 0, 410, 15, 7810));
}

void test_mix_straight(void) {
  const rover::WheelSpeeds s = rover::mix_differential(0.2f, 0.0f, 0.16f, 0.45f);
  TEST_ASSERT_FLOAT_WITHIN(0.001f, 0.2f, s.left_mps);
  TEST_ASSERT_FLOAT_WITHIN(0.001f, 0.2f, s.right_mps);
}

void test_mix_spin(void) {
  const rover::WheelSpeeds s = rover::mix_differential(0.0f, 1.0f, 0.16f, 0.45f);
  TEST_ASSERT_LESS_THAN(0.0f, s.left_mps);
  TEST_ASSERT_GREATER_THAN(0.0f, s.right_mps);
}

void test_mix_clamps(void) {
  const rover::WheelSpeeds s = rover::mix_differential(0.4f, 1.2f, 0.16f, 0.3f);
  const float peak = fmaxf(fabsf(s.left_mps), fabsf(s.right_mps));
  TEST_ASSERT_FLOAT_WITHIN(0.001f, 0.3f, peak);
}

void test_mix_invalid(void) {
  const rover::WheelSpeeds s = rover::mix_differential(0.1f, 0.1f, 0.0f, 0.3f);
  TEST_ASSERT_FLOAT_WITHIN(0.0001f, 0.0f, s.left_mps);
  TEST_ASSERT_FLOAT_WITHIN(0.0001f, 0.0f, s.right_mps);
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_ping);
  RUN_TEST(test_stop);
  RUN_TEST(test_velocity);
  RUN_TEST(test_trim_crlf);
  RUN_TEST(test_wrong_count);
  RUN_TEST(test_not_a_number);
  RUN_TEST(test_out_of_range);
  RUN_TEST(test_too_long);
  RUN_TEST(test_unknown);
  RUN_TEST(test_telemetry_format);
  RUN_TEST(test_telemetry_small_buffer);
  RUN_TEST(test_mix_straight);
  RUN_TEST(test_mix_spin);
  RUN_TEST(test_mix_clamps);
  RUN_TEST(test_mix_invalid);
  return UNITY_END();
}
