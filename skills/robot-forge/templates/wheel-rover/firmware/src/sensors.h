#pragma once

#include <stdint.h>

namespace rover {

void sensors_begin();
int read_distance_mm();      // -1 when there is no echo
int read_battery_mv();
int read_yaw_rate_mdps();    // milli-degrees per second around Z
void display_status(int distance_mm, int battery_mv, bool stopped);

}  // namespace rover
