#include <Arduino.h>
#include <FastLED.h>
#include <LovyanGFX.hpp>
#include <Wire.h>

#include "config.h"
#include "face.h"
#include "motion.h"
#include "protocol.h"
#include "sensors.h"

namespace {

class LGFX : public lgfx::LGFX_Device {
 public:
  LGFX() {
    {
      auto cfg = bus_.config();
      cfg.spi_host = SPI2_HOST;
      cfg.spi_mode = 0;
      cfg.freq_write = 40000000;
      cfg.freq_read = 16000000;
      cfg.spi_3wire = true;
      cfg.use_lock = true;
      cfg.pin_sclk = 12;
      cfg.pin_mosi = 11;
      cfg.pin_miso = -1;
      cfg.pin_dc = 13;
      bus_.config(cfg);
      panel_.setBus(&bus_);
    }
    {
      auto cfg = panel_.config();
      cfg.pin_cs = 10;
      cfg.pin_rst = 14;
      cfg.pin_busy = -1;
      cfg.panel_width = 240;
      cfg.panel_height = 240;
      cfg.offset_x = 0;
      cfg.offset_y = 0;
      cfg.invert = true;
      cfg.rgb_order = false;
      panel_.config(cfg);
    }
    {
      auto cfg = light_.config();
      cfg.pin_bl = 21;
      cfg.invert = false;
      cfg.freq = 44100;
      cfg.pwm_channel = 7;
      light_.config(cfg);
      panel_.setLight(&light_);
    }
    setPanel(&panel_);
  }

 private:
  lgfx::Panel_GC9A01 panel_;
  lgfx::Bus_SPI bus_;
  lgfx::Light_PWM light_;
};

LGFX display;
Face face;
Motion motion;
Sensors sensors;
CRGB leds[cfg::kLedCount];

char lineBuffer[cfg::kMaxLine + 1];
size_t lineLength = 0;

bool lastHead = false;
bool lastChin = false;
uint32_t lastDistanceMs = 0;
uint32_t lastLevelMs = 0;

void sendLine(const char* text) {
  Serial.println(text);
}

void setRing(uint8_t red, uint8_t green, uint8_t blue) {
  fill_solid(leds, cfg::kLedCount, CRGB(red, green, blue));
  FastLED.setBrightness(80);
  FastLED.show();
}

void handleMessage(const Message& message) {
  if (!message.ok) {
    sendLine("ERR syntax");
    return;
  }
  switch (message.type) {
    case MsgType::Emo: {
      Emotion emotion = Emotion::Idle;
      if (strcmp(message.word, "happy") == 0) emotion = Emotion::Happy;
      else if (strcmp(message.word, "curious") == 0) emotion = Emotion::Curious;
      else if (strcmp(message.word, "sleepy") == 0) emotion = Emotion::Sleepy;
      else if (strcmp(message.word, "alert") == 0) emotion = Emotion::Alert;
      face.show(emotion);
      break;
    }
    case MsgType::Pose:
      motion.setTarget(message.a, message.b);
      break;
    case MsgType::Led:
      setRing(static_cast<uint8_t>(message.a), static_cast<uint8_t>(message.b),
              static_cast<uint8_t>(message.c));
      break;
    case MsgType::Mic:
      if (strcmp(message.word, "on") == 0) sensors.micOn();
      else sensors.micOff();
      break;
    case MsgType::Vol:
      // The MAX98357A has no volume register; host-side gain is the v0.2 path.
      break;
    default:
      break;
  }
}

}  // namespace

void setup() {
  Serial.begin(cfg::kSerialBaud);
  Serial.setTimeout(20);

  FastLED.addLeds<WS2812B, cfg::kLedPin, GRB>(leds, cfg::kLedCount);
  setRing(8, 12, 20);

  face.begin(&display);
  sensors.begin();
  motion.begin();
  motion.setTarget(cfg::kPanHome, cfg::kTiltHome);

  delay(300);
  sendLine("READY");
}

void loop() {
  while (Serial.available() > 0) {
    char ch = static_cast<char>(Serial.read());
    if (ch == '\n' || ch == '\r') {
      if (lineLength > 0) {
        lineBuffer[lineLength] = '\0';
        handleMessage(parseLine(lineBuffer, lineLength));
        lineLength = 0;
      }
      continue;
    }
    if (lineLength < cfg::kMaxLine) {
      lineBuffer[lineLength++] = ch;
    } else {
      lineLength = 0;
      sendLine("ERR syntax");
    }
  }

  uint32_t now = millis();
  motion.update(now);
  face.update(now);

  bool head = sensors.touchHead();
  bool chin = sensors.touchChin();
  if (head && !lastHead) sendLine("TOUCH head");
  if (chin && !lastChin) sendLine("TOUCH chin");
  lastHead = head;
  lastChin = chin;

  if (now - lastDistanceMs > cfg::kDistancePeriodMs) {
    lastDistanceMs = now;
    int mm = sensors.distanceMm();
    if (mm >= 0) {
      char buffer[24];
      snprintf(buffer, sizeof(buffer), "DIST %d", mm);
      sendLine(buffer);
    }
  }

  if (sensors.micRunning() && now - lastLevelMs > 100) {
    lastLevelMs = now;
    int level = sensors.micLevel();
    if (level >= 0) {
      char buffer[16];
      snprintf(buffer, sizeof(buffer), "LEVEL %d", level);
      sendLine(buffer);
    }
  }

  if (motion.consumeStall()) {
    sendLine("ERR stall");
    face.show(Emotion::Alert);
  }
}