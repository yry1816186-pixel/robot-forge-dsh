#include "face.h"

namespace {

constexpr int kScreen = 240;
constexpr int kEyeY = 110;
constexpr int kLeftX = 96;
constexpr int kRightX = 144;

uint16_t eyeColor(Emotion emotion) {
  switch (emotion) {
    case Emotion::Happy: return 0x07E0;    // green
    case Emotion::Curious: return 0xA81F;  // purple
    case Emotion::Sleepy: return 0x2104;   // dim grey
    case Emotion::Alert: return 0xFD20;    // orange
    default: return 0x04BF;                // calm blue
  }
}

int eyeRadius(Emotion emotion) {
  switch (emotion) {
    case Emotion::Curious: return 30;
    case Emotion::Alert: return 28;
    case Emotion::Sleepy: return 18;
    default: return 24;
  }
}

}  // namespace

void Face::begin(lgfx::LovyanGFX* gfx) {
  gfx_ = gfx;
  if (!gfx_) return;
  gfx_->fillScreen(TFT_BLACK);
  draw(false);
}

void Face::show(Emotion emotion) {
  emotion_ = emotion;
  draw(emotion == Emotion::Sleepy);
}

void Face::update(uint32_t nowMs) {
  if (!gfx_ || emotion_ == Emotion::Sleepy) return;
  if (nowMs - lastBlink_ > 4200) {
    lastBlink_ = nowMs;
    closed_ = !closed_;
    draw(closed_);
    if (closed_) {
      // Reopen on the next tick; keep the frame cheap.
      delay(90);
      closed_ = false;
      draw(false);
    }
  }
}

void Face::draw(bool closed) {
  if (!gfx_) return;
  gfx_->fillScreen(TFT_BLACK);
  uint16_t color = eyeColor(emotion_);
  int radius = eyeRadius(emotion_);
  if (closed) {
    gfx_->fillRect(kLeftX - radius, kEyeY - 3, radius * 2, 6, color);
    gfx_->fillRect(kRightX - radius, kEyeY - 3, radius * 2, 6, color);
    return;
  }
  gfx_->fillCircle(kLeftX, kEyeY, radius, color);
  gfx_->fillCircle(kRightX, kEyeY, radius, color);
  if (emotion_ == Emotion::Happy) {
    // A small mouth keeps the happy expression readable at 1.28 inch.
    gfx_->drawCircle(kScreen / 2, 160, 22, color);
  }
}
