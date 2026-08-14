#include "home_sensor.h"

#include <Arduino.h>

#define HOME_PIN PIN_PA7  // Arduino Pin 3;

namespace {
  bool lastHomeState = false;
}

namespace HomeSensor {
  void begin() {
    pinMode(HOME_PIN, INPUT_PULLUP);
  }

  bool homeActive() {
    return digitalRead(HOME_PIN) == LOW;
  }

  bool detectRisingEdge() {
    bool homeNow     = homeActive();
    bool risingEdge  = homeNow && !lastHomeState;
    lastHomeState    = homeNow;

    return risingEdge;
  }
}

