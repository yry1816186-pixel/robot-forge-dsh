#include "drive.h"

#include <math.h>

namespace rover {

WheelSpeeds mix_differential(float linear_mps, float angular_radps,
                             float wheel_base_m, float max_wheel_mps) {
  WheelSpeeds out;
  if (wheel_base_m <= 0.0f || max_wheel_mps <= 0.0f) {
    return out;
  }
  const float half = angular_radps * wheel_base_m * 0.5f;
  float left = linear_mps - half;
  float right = linear_mps + half;
  const float peak = fmaxf(fabsf(left), fabsf(right));
  if (peak > max_wheel_mps) {
    const float scale = max_wheel_mps / peak;
    left *= scale;
    right *= scale;
  }
  out.left_mps = left;
  out.right_mps = right;
  return out;
}

}  // namespace rover
