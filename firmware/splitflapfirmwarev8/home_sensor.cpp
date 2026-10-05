#include "home_sensor.h"

#include <Arduino.h>

#include "eeprom_store.h"
#include "pinout.h"

namespace {
  bool lastHomeState = false;
  uint32_t lastEdgeMillis = 0;
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
    bool homeNow     = homeActive();
    bool risingEdge  = homeNow && !lastHomeState;
    lastHomeState    = homeNow;

    if (risingEdge) {
      uint32_t now = millis();
      if (now - lastEdgeMillis < EepromStore::getDebounceMs()) {
        return false;
      }
      lastEdgeMillis = now;
    }
    return risingEdge;
  }
}

