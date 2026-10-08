#include "home_sensor.h"

#include <Arduino.h>

#include "eeprom_store.h"
#include "pinout.h"

namespace {
  // millis() when the contact was last seen closed. Starts more than any
  // debounce time (65535 ms) before power-on, so the first edge counts
  // straight away.
  const uint32_t NEVER_CLOSED = 0xFFFF0000;
  bool lastHomeState = false;
  uint32_t lastClosedMillis = NEVER_CLOSED;
}

namespace HomeSensor {
  void begin() {
    pinMode(HOME_PIN, INPUT_PULLUP);
    lastHomeState = homeActive();
  }

  bool homeActive() {
    return digitalRead(HOME_PIN) == LOW;
  }

  bool detectRisingEdge() {
    bool homeNow = homeActive();
    bool risingEdge = false;
    if (homeNow) {
      uint32_t now = millis();
      // A rising edge only counts once the contact has been open for the
      // debounce time. Timing from the last accepted edge instead would let
      // a bounce count as a new edge when the contact had been closed for
      // longer than that, as it is when the reel stops on a flap inside it.
      risingEdge = !lastHomeState && now - lastClosedMillis >= EepromStore::getDebounceMs();
      lastClosedMillis = now;
    }
    lastHomeState = homeNow;
    return risingEdge;
  }
}
