#pragma once

#include <stddef.h>
#include <string>

namespace rover {

enum class CmdType { kVelocity, kStop, kPing, kInvalid };

struct Command {
  CmdType type = CmdType::kInvalid;
  int linear_mm_s = 0;
  int angular_mrad_s = 0;
  int error = 0;
};

// Parse one line (without the trailing newline). Never throws.
Command parse_command(const std::string& line);

// Format a telemetry line. Returns the number of bytes written (excluding NUL),
// or 0 when the buffer is too small.
size_t format_telemetry(char* out, size_t capacity, int enc_l, int enc_r,
                        int distance_mm, int yaw_mdeg, int battery_mv);

// Human-readable error code, useful in logs.
const char* error_text(int code);

}  // namespace rover
