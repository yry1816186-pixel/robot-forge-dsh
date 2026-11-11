#include "sensors.h"

#include <Adafruit_VL53L0X.h>
#include <Wire.h>
#include <cmath>
#include <driver/i2s.h>

#include "config.h"

namespace {

Adafruit_VL53L0X vl53;
constexpr i2s_port_t kMicPort = I2S_NUM_0;
constexpr int kSamples = 320;  // 20 ms at 16 kHz
int32_t samples[kSamples];

}  // namespace

void Sensors::begin() {
  pinMode(cfg::kTouchHeadPin, INPUT);
  pinMode(cfg::kTouchChinPin, INPUT);
  Wire.begin(cfg::kI2cSda, cfg::kI2cScl);
  vl53Ready_ = vl53.begin();
  if (!vl53Ready_) {
    Serial.println("ERR vl53");
  }

  i2s_config_t micConfig = {};
  micConfig.mode = static_cast<i2s_mode_t>(I2S_MODE_MASTER | I2S_MODE_RX);
  micConfig.sample_rate = 16000;
  micConfig.bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT;
  micConfig.channel_format = I2S_CHANNEL_FMT_ONLY_LEFT;
  micConfig.communication_format = I2S_COMM_FORMAT_STAND_I2S;
  micConfig.intr_alloc_flags = ESP_INTR_FLAG_LEVEL1;
  micConfig.dma_buf_count = 4;
  micConfig.dma_buf_len = 256;
  i2s_driver_install(kMicPort, &micConfig, 0, nullptr);

  i2s_pin_config_t pins = {};
  pins.bck_io_num = cfg::kMicBclk;
  pins.ws_io_num = cfg::kMicWs;
  pins.data_out_num = I2S_PIN_NO_CHANGE;
  pins.data_in_num = cfg::kMicDin;
  i2s_set_pin(kMicPort, &pins);
}

void Sensors::micOn() {
  if (micOn_) return;
  i2s_start(kMicPort);
  micOn_ = true;
}

void Sensors::micOff() {
  if (!micOn_) return;
  i2s_stop(kMicPort);
  micOn_ = false;
}

bool Sensors::touchHead() {
  return digitalRead(cfg::kTouchHeadPin) == HIGH;
}

bool Sensors::touchChin() {
  return digitalRead(cfg::kTouchChinPin) == HIGH;
}

int Sensors::distanceMm() {
  if (!vl53Ready_) return -1;
  VL53L0X_RangingMeasurementData_t measure;
  vl53.rangingTest(&measure, false);
  if (measure.RangeStatus != 4) {
    return measure.RangeMilliMeter;
  }
  return -1;
}

int Sensors::micLevel() {
  if (!micOn_) return -1;
  size_t bytesRead = 0;
  esp_err_t err = i2s_read(kMicPort, samples, sizeof(samples), &bytesRead, pdMS_TO_TICKS(50));
  if (err != ESP_OK || bytesRead == 0) return -1;
  int64_t sum = 0;
  int count = static_cast<int>(bytesRead / sizeof(int32_t));
  for (int i = 0; i < count; ++i) {
    int32_t value = samples[i] >> 14;  // INMP441 puts 24 bits in the high half
    sum += static_cast<int64_t>(value) * value;
  }
  if (count == 0) return -1;
  double rms = sqrt(static_cast<double>(sum) / count);
  int level = static_cast<int>(rms / 200.0);
  if (level < 0) level = 0;
  if (level > 100) level = 100;
  return level;
}