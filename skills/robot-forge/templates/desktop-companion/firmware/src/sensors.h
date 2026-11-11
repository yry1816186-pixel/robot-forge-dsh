#pragma once

#include <Arduino.h>

// Touch pads, time-of-flight distance and a coarse microphone level.
class Sensors {
 public:
  void begin();
  void micOn();
  void micOff();
  bool micRunning() const { return micOn_; }

  bool touchHead();
  bool touchChin();
  int distanceMm();
  int micLevel();

 private:
  bool vl53Ready_ = false;
  bool micOn_ = false;
};
