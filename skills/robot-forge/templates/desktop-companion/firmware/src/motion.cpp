#include "motion.h"

#include "config.h"

namespace {

int clampInt(int value, int low, int high) {
  if (value < low) return low;
  if (value > high) return high;
  return value;
}

int stepToward(int current, int target, int step) {
  if (current < target) {
    return current + (target - current < step ? target - current : step);
  }
  if (current > target) {
    return current - (current - target < step ? current - target : step);
  }
  return current;
}

}  // namespace

void Motion::begin() {
  panServo_.attach(cfg::kPanPin);
  tiltServo_.attach(cfg::kTiltPin);
  attached_ = true;
  targetPan_ = cfg::kPanHome;
  targetTilt_ = cfg::kTiltHome;
  posPan_ = cfg::kPanHome;
  posTilt_ = cfg::kTiltHome;
  lastMs_ = millis();
  apply();
}

void Motion::setTarget(int pan, int tilt) {
  targetPan_ = clampInt(pan, cfg::kPanMin, cfg::kPanMax);
  targetTilt_ = clampInt(tilt, cfg::kTiltMin, cfg::kTiltMax);
  straining_ = false;
  strainSince_ = 0;
}

void Motion::update(uint32_t nowMs) {
  if (!attached_) return;
  uint32_t dt = nowMs - lastMs_;
  lastMs_ = nowMs;
  if (dt > 200) dt = 200;
  int step = static_cast<int>((cfg::kSlewDegPerSec * dt) / 1000);
  if (step < 1) step = 1;
  int nextPan = stepToward(posPan_, targetPan_, step);
  int nextTilt = stepToward(posTilt_, targetTilt_, step);
  if (nextPan != posPan_ || nextTilt != posTilt_) {
    posPan_ = nextPan;
    posTilt_ = nextTilt;
    apply();
  }

  bool pushing = posPan_ != targetPan_ || posTilt_ != targetTilt_;
  if (pushing) {
    if (!straining_) {
      straining_ = true;
      strainSince_ = nowMs;
    } else if (nowMs - strainSince_ > cfg::kStallMs) {
      stalled_ = true;
      relax();
    }
  } else {
    straining_ = false;
  }
}

void Motion::relax() {
  if (attached_) {
    panServo_.detach();
    tiltServo_.detach();
    attached_ = false;
  }
}

bool Motion::consumeStall() {
  bool value = stalled_;
  stalled_ = false;
  return value;
}

void Motion::apply() {
  // 90 degrees is the mechanical centre of a standard hobby servo.
  panServo_.write(90 + posPan_);
  tiltServo_.write(90 + posTilt_);
}
