#pragma once

// Signal pins. Must match forge/robot.yaml -> buses/pins.
#define PIN_I2C_SDA 13
#define PIN_I2C_SCL 14
#define PIN_LEFT_PWM 4
#define PIN_LEFT_IN1 5
#define PIN_LEFT_IN2 6
#define PIN_RIGHT_PWM 7
#define PIN_RIGHT_IN1 8
#define PIN_RIGHT_IN2 9
#define PIN_MOTOR_STBY 10
#define PIN_SONAR_TRIG 11
#define PIN_SONAR_ECHO 12
#define PIN_BATTERY_SENSE 1
#define PIN_STATUS_LED 2

// Motor wiring can differ per build; flip here instead of rewiring.
#define LEFT_INVERT 0
#define RIGHT_INVERT 0

// Safety limits. Must match forge/robot.yaml -> motion.
#define MAX_LINEAR_MM_S 400
#define MAX_ANGULAR_MRAD_S 1200
#define STOP_DISTANCE_MM 300
#define STOP_CONFIRM_COUNT 3
#define HEARTBEAT_TIMEOUT_MS 500
#define TELEMETRY_PERIOD_MS 20
#define SONAR_PERIOD_MS 60
#define DISPLAY_PERIOD_MS 100
#define STALL_WINDOW_MS 2000
#define STALL_PWM_THRESHOLD 153  // 60% of 255

// Battery divider: 100k top, 33k bottom; 8.4V -> ~2.08V at the ADC.
#define BATTERY_DIVIDER 4.03f

#define OLED_ADDR 0x3C
#define MPU_ADDR 0x68
