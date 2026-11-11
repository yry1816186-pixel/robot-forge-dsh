#pragma once

namespace rover {

struct WheelSpeeds {
  float left_mps = 0.0f;
  float right_mps = 0.0f;
};

// Differential-drive mix. The result is scaled proportionally when a wheel
// would exceed max_wheel_mps. Returns {0,0} for invalid parameters.
WheelSpeeds mix_differential(float linear_mps, float angular_radps,
                             float wheel_base_m, float max_wheel_mps);

}  // namespace rover
