#include "protocol.h"

#include <stdio.h>
#include <stdlib.h>

#include <sstream>

namespace rover {
namespace {

constexpr size_t kMaxLine = 48;

std::string trim(const std::string& in) {
  size_t begin = 0;
  size_t end = in.size();
  while (begin < end && (in[begin] == ' ' || in[begin] == '\t' || in[begin] == '\r')) {
    ++begin;
  }
  while (end > begin && (in[end - 1] == ' ' || in[end - 1] == '\t' || in[end - 1] == '\r')) {
    --end;
  }
  return in.substr(begin, end - begin);
}

bool parse_int(const std::string& token, int* value) {
  if (token.empty()) {
    return false;
  }
  char* end = nullptr;
  long parsed = strtol(token.c_str(), &end, 10);
  if (end == token.c_str() || *end != '\0') {
    return false;
  }
  if (parsed < -100000 || parsed > 100000) {
    return false;
  }
  *value = static_cast<int>(parsed);
  return true;
}

}  // namespace

Command parse_command(const std::string& raw) {
  Command cmd;
  if (raw.size() > kMaxLine) {
    cmd.error = 1;
    return cmd;
  }
  const std::string line = trim(raw);
  if (line.empty()) {
    cmd.error = 2;
    return cmd;
  }
  if (line == "S") {
    cmd.type = CmdType::kStop;
    return cmd;
  }
  if (line == "PING") {
    cmd.type = CmdType::kPing;
    return cmd;
  }
  std::istringstream stream(line);
  std::string name;
  stream >> name;
  if (name != "V") {
    cmd.error = 2;
    return cmd;
  }
  std::string a;
  std::string b;
  std::string extra;
  stream >> a >> b;
  if (!stream || (stream >> extra)) {
    cmd.error = 3;
    return cmd;
  }
  int lin = 0;
  int ang = 0;
  if (!parse_int(a, &lin) || !parse_int(b, &ang)) {
    cmd.error = 4;
    return cmd;
  }
  if (lin < -MAX_LINEAR_MM_S || lin > MAX_LINEAR_MM_S ||
      ang < -MAX_ANGULAR_MRAD_S || ang > MAX_ANGULAR_MRAD_S) {
    cmd.error = 5;
    return cmd;
  }
  cmd.type = CmdType::kVelocity;
  cmd.linear_mm_s = lin;
  cmd.angular_mrad_s = ang;
  return cmd;
}

size_t format_telemetry(char* out, size_t capacity, int enc_l, int enc_r,
                        int distance_mm, int yaw_mdeg, int battery_mv) {
  if (out == nullptr || capacity == 0) {
    return 0;
  }
  int written = snprintf(out, capacity, "T %d %d %d %d %d", enc_l, enc_r,
                         distance_mm, yaw_mdeg, battery_mv);
  if (written < 0 || static_cast<size_t>(written) >= capacity) {
    out[0] = '\0';
    return 0;
  }
  return static_cast<size_t>(written);
}

const char* error_text(int code) {
  switch (code) {
    case 1:
      return "line too long";
    case 2:
      return "unknown command";
    case 3:
      return "wrong argument count";
    case 4:
      return "argument is not a number";
    case 5:
      return "value out of range";
    case 6:
      return "obstacle stop";
    default:
      return "error";
  }
}

}  // namespace rover
