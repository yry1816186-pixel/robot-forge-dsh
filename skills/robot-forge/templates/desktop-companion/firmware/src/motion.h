#pragma once

#include <Arduino.h>
#include <Servo.h>

// Rate-limited servo control with software end stops and a stall guard.
class Motion {
 public:
  void begin();
  void setTarget(int pan, int tilt);
  void update(uint32_t nowMs);
  void relax();

  bool stalled() const { return stalled_; }
  bool consumeStall();
  int pan() const { return posPan_; }
  int tilt() const { return posTilt_; }

 private:
  void apply();

  Servo panServo_;
  Servo tiltServo_;
  int targetPan_ = 0;
  int targetTilt_ = 8;
  int posPan_ = 0;
  int posTilt_ = 8;
  uint32_t lastMs_ = 0;
  uint32_t strainSince_ = 0;
  bool straining_ = false;
  bool stalled_ = false;
  bool attached_ = false;
};
