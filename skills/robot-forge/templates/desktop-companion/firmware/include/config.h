#pragma once

#include <stdint.h>

// Single source of truth for wiring is forge/robot.yaml. Keep this file in
// sync when the yaml changes; the forge checker compares the two.
namespace cfg {

// I2S microphone (INMP441)
constexpr int kMicBclk = 4;
constexpr int kMicWs = 5;
constexpr int kMicDin = 6;

// I2S speaker (MAX98357A)
constexpr int kSpkBclk = 7;
constexpr int kSpkLrc = 8;
constexpr int kSpkDout = 9;

// Round display (GC9A01 over SPI)
constexpr int kDispSck = 12;
constexpr int kDispMosi = 11;
constexpr int kDispCs = 10;
constexpr int kDispDc = 13;
constexpr int kDispRst = 14;
constexpr int kDispBl = 21;

// I2C distance sensor (VL53L0X)
constexpr int kI2cSda = 18;
constexpr int kI2cScl = 1;

// Servos
constexpr int kPanPin = 15;
constexpr int kTiltPin = 16;

// LED ring and touch pads
constexpr int kLedPin = 17;
constexpr int kTouchHeadPin = 47;
constexpr int kTouchChinPin = 48;
constexpr int kLedCount = 5;

// Mechanical limits, mirrored in robot.yaml mechanical.dims and docs/03.
constexpr int kPanMin = -45;
constexpr int kPanMax = 45;
constexpr int kTiltMin = -10;
constexpr int kTiltMax = 60;
constexpr int kPanHome = 0;
constexpr int kTiltHome = 8;

// Motion behaviour
constexpr int kSlewDegPerSec = 90;
constexpr uint32_t kStallMs = 5000;
constexpr uint32_t kDistancePeriodMs = 500;
constexpr int kNearMm = 1500;

// Serial protocol
constexpr uint32_t kSerialBaud = 921600;
constexpr size_t kMaxLine = 120;

}  // namespace cfg
