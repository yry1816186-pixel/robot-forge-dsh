#include "sensors.h"

#include <Arduino.h>
#include <Wire.h>

#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#include "config.h"

namespace rover {
namespace {

Adafruit_SSD1306 display(128, 64, &Wire, -1);

void write_reg(uint8_t addr, uint8_t reg, uint8_t value) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.write(value);
  Wire.endTransmission();
}

bool read_regs(uint8_t addr, uint8_t reg, uint8_t* buf, uint8_t len) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) {
    return false;
  }
  if (Wire.requestFrom(addr, len) != len) {
    return false;
  }
  for (uint8_t i = 0; i < len; ++i) {
    buf[i] = Wire.read();
  }
  return true;
}

}  // namespace

void sensors_begin() {
  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
  Wire.setClock(400000);

  pinMode(PIN_SONAR_TRIG, OUTPUT);
  pinMode(PIN_SONAR_ECHO, INPUT);
  digitalWrite(PIN_SONAR_TRIG, LOW);

  // Wake the MPU6050 and set the gyro range to +/-500 deg/s.
  write_reg(MPU_ADDR, 0x6B, 0x00);
  write_reg(MPU_ADDR, 0x1B, 0x08);

  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
    Serial.println("OLED not found at 0x3C");
  } else {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, 0);
    display.println("rover boot");
    display.display();
  }
}

int read_distance_mm() {
  digitalWrite(PIN_SONAR_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_SONAR_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_SONAR_TRIG, LOW);
  const unsigned long us = pulseIn(PIN_SONAR_ECHO, HIGH, 30000UL);
  if (us == 0) {
    return -1;
  }
  return static_cast<int>(us / 5.8f);
}

int read_battery_mv() {
  const int pin_mv = analogReadMilliVolts(PIN_BATTERY_SENSE);
  return static_cast<int>(pin_mv * BATTERY_DIVIDER);
}

int read_yaw_rate_mdps() {
  uint8_t raw[2] = {0, 0};
  if (!read_regs(MPU_ADDR, 0x47, raw, 2)) {
    return 0;
  }
  const int16_t value = static_cast<int16_t>((raw[0] << 8) | raw[1]);
  // +/-500 deg/s => 65.5 LSB/(deg/s). Output in milli-degrees/s.
  return static_cast<int>(value * 1000.0f / 65.5f);
}

void display_status(int distance_mm, int battery_mv, bool stopped) {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.print("BATT ");
  display.print(battery_mv / 1000.0f, 2);
  display.println("V");
  display.setCursor(0, 18);
  display.print("DIST ");
  if (distance_mm < 0) {
    display.println("---");
  } else {
    display.print(distance_mm);
    display.println("mm");
  }
  display.setCursor(0, 36);
  display.println(stopped ? "STOP" : "TELEOP");
  display.display();
}

}  // namespace rover
