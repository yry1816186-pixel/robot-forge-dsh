#pragma once

#include <LovyanGFX.hpp>

enum class Emotion { Idle, Happy, Curious, Sleepy, Alert };

class Face {
 public:
  void begin(lgfx::LovyanGFX* gfx);
  void show(Emotion emotion);
  void update(uint32_t nowMs);

 private:
  void draw(bool closed);

  lgfx::LovyanGFX* gfx_ = nullptr;
  Emotion emotion_ = Emotion::Idle;
  uint32_t lastBlink_ = 0;
  bool closed_ = false;
};
