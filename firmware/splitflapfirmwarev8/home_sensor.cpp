#include "home_sensor.h"

#include <Arduino.h>

#include "eeprom_store.h"
#include "pinout.h"

namespace {
  bool lastHomeState = false;
  // When the contact was last seen closed, and whether it has been at all.
  // Until it has, the first rising edge counts straight away (even in the
  // first debounce period after power-on).
  uint32_t lastClosedMillis = 0;
  bool closedSeen = false;
}

namespace HomeSensor {
  void begin() {
    pinMode(HOME_PIN, INPUT_PULLUP);
    lastHomeState = homeActive();
    closedSeen = false;
  }

  bool homeActive() {
    return digitalRead(HOME_PIN) == LOW;
  }

  bool detectRisingEdge() {
    bool homeNow     = homeActive();
    bool risingEdge  = homeNow && !lastHomeState;
    lastHomeState    = homeNow;

    uint32_t now = millis();
    // A rising edge only counts once the contact has been open for the
    // debounce time. Timing from the last accepted edge instead would let a
    // bounce count as a new edge when the contact had been closed for longer
    // than that, as it is when the reel stops on a flap inside it.
    bool settled = !closedSeen || now - lastClosedMillis >= EepromStore::getDebounceMs();
    if (homeNow) {
      lastClosedMillis = now;
      closedSeen = true;
    }
    return risingEdge && settled;
  }
}
