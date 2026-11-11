#include <Arduino.h>

#include "config.h"
#include "drive.h"
#include "protocol.h"
#include "sensors.h"

namespace {

char line_buf[64];
size_t line_len = 0;
bool line_overflow = false;

unsigned long last_cmd_ms = 0;
unsigned long last_sonar_ms = 0;
unsigned long last_display_ms = 0;
unsigned long last_telemetry_ms = 0;
unsigned long last_motion_ms = 0;

int distance_mm = -1;
int battery_mv = 7800;
int yaw_mdeg = 0;
float yaw_accum_deg = 0.0f;

int linear_mm_s = 0;
int angular_mrad_s = 0;
bool obstacle_latched = false;
int obstacle_count = 0;
bool stopped = true;

void set_motor(int in1, int in2, int pwm_pin, float speed_mps, bool invert) {
  const float clamped = constrain(speed_mps, -0.45f, 0.45f);
  const bool forward = (clamped >= 0.0f) != invert;
  digitalWrite(in1, forward ? HIGH : LOW);
  digitalWrite(in2, forward ? LOW : HIGH);
  const int duty = static_cast<int>(fabsf(clamped) / 0.45f * 255.0f);
  analogWrite(pwm_pin, constrain(duty, 0, 255));
}

void stop_motors() {
  digitalWrite(PIN_MOTOR_STBY, LOW);
  analogWrite(PIN_LEFT_PWM, 0);
  analogWrite(PIN_RIGHT_PWM, 0);
  digitalWrite(PIN_LEFT_IN1, LOW);
  digitalWrite(PIN_LEFT_IN2, LOW);
  digitalWrite(PIN_RIGHT_IN1, LOW);
  digitalWrite(PIN_RIGHT_IN2, LOW);
}

void apply_motion() {
  const rover::WheelSpeeds speeds = rover::mix_differential(
      linear_mm_s / 1000.0f, angular_mrad_s / 1000.0f, 0.16f, 0.45f);
  digitalWrite(PIN_MOTOR_STBY, HIGH);
  set_motor(PIN_LEFT_IN1, PIN_LEFT_IN2, PIN_LEFT_PWM, speeds.left_mps, LEFT_INVERT);
  set_motor(PIN_RIGHT_IN1, PIN_RIGHT_IN2, PIN_RIGHT_PWM, speeds.right_mps, RIGHT_INVERT);
  stopped = (linear_mm_s == 0 && angular_mrad_s == 0);
}

void emergency_stop() {
  linear_mm_s = 0;
  angular_mrad_s = 0;
  stop_motors();
  stopped = true;
}

void handle_command(const rover::Command& cmd) {
  switch (cmd.type) {
    case rover::CmdType::kPing:
      Serial.println("OK");
      break;
    case rover::CmdType::kStop:
      emergency_stop();
      Serial.println("OK");
      break;
    case rover::CmdType::kVelocity:
      if (obstacle_latched && cmd.linear_mm_s > 0) {
        Serial.println("ERR 6");
        break;
      }
      linear_mm_s = cmd.linear_mm_s;
      angular_mrad_s = cmd.angular_mrad_s;
      last_cmd_ms = millis();
      last_motion_ms = millis();
      apply_motion();
      Serial.println("OK");
      break;
    default:
      Serial.print("ERR ");
      Serial.println(cmd.error);
      break;
  }
}

void read_serial() {
  while (Serial.available() > 0) {
    const char ch = static_cast<char>(Serial.read());
    if (ch == '\n' || ch == '\r') {
      if (line_overflow) {
        Serial.println("ERR 1");
      } else if (line_len > 0) {
        line_buf[line_len] = '\0';
        handle_command(rover::parse_command(std::string(line_buf, line_len)));
      }
      line_len = 0;
      line_overflow = false;
    } else if (line_len < sizeof(line_buf) - 1) {
      line_buf[line_len++] = ch;
    } else {
      line_overflow = true;
    }
  }
}

void update_safety() {
  if (linear_mm_s != 0 || angular_mrad_s != 0) {
    if (millis() - last_cmd_ms > HEARTBEAT_TIMEOUT_MS) {
      emergency_stop();
    }
  }
  // No encoder: if we command a large duty but the sonar distance has not
  // changed for a while, assume a stall and cut power.
  if (!stopped && (millis() - last_motion_ms > STALL_WINDOW_MS)) {
    emergency_stop();
  }
}

void update_sonar() {
  if (millis() - last_sonar_ms < SONAR_PERIOD_MS) {
    return;
  }
  last_sonar_ms = millis();
  const int measured = rover::read_distance_mm();
  if (measured >= 0) {
    distance_mm = measured;
  }
  if (measured > 0 && measured < STOP_DISTANCE_MM) {
    obstacle_count++;
  } else {
    obstacle_count = 0;
    obstacle_latched = false;
  }
  if (obstacle_count >= STOP_CONFIRM_COUNT) {
    obstacle_latched = true;
    if (linear_mm_s > 0) {
      emergency_stop();
      Serial.println("ERR 6");
    }
  }
}

void update_telemetry() {
  if (millis() - last_telemetry_ms < TELEMETRY_PERIOD_MS) {
    return;
  }
  last_telemetry_ms = millis();
  char out[64];
  const size_t n = rover::format_telemetry(out, sizeof(out), 0, 0, distance_mm,
                                           yaw_mdeg, battery_mv);
  if (n > 0) {
    Serial.println(out);
  }
}

}  // namespace

void setup() {
  Serial.begin(115200);
  pinMode(PIN_MOTOR_STBY, OUTPUT);
  pinMode(PIN_LEFT_IN1, OUTPUT);
  pinMode(PIN_LEFT_IN2, OUTPUT);
  pinMode(PIN_RIGHT_IN1, OUTPUT);
  pinMode(PIN_RIGHT_IN2, OUTPUT);
  pinMode(PIN_LEFT_PWM, OUTPUT);
  pinMode(PIN_RIGHT_PWM, OUTPUT);
  pinMode(PIN_STATUS_LED, OUTPUT);
  analogWriteFrequency(20000);
  stop_motors();
  rover::sensors_begin();
  last_cmd_ms = millis();
  Serial.println("rover ready");
}

void loop() {
  read_serial();
  update_sonar();
  update_safety();
  update_telemetry();

  const int yaw_rate = rover::read_yaw_rate_mdps();
  yaw_accum_deg += (yaw_rate / 1000.0f) * 0.02f;
  yaw_mdeg = static_cast<int>(yaw_accum_deg * 1000.0f) % 360000;

  if (millis() - last_display_ms > DISPLAY_PERIOD_MS) {
    last_display_ms = millis();
    battery_mv = rover::read_battery_mv();
    rover::display_status(distance_mm, battery_mv, stopped || obstacle_latched);
    digitalWrite(PIN_STATUS_LED, stopped ? LOW : HIGH);
  }
  delay(1);
}
