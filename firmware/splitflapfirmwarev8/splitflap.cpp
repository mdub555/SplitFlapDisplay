#include "splitflap.h"

#include <SoftwareSerial.h>

#include "eeprom_store.h"
#include "home_sensor.h"
#include "motor.h"

namespace {
  // The ordered set of 64 characters this reel can display. Position 0 is
  // blank (the "home" flap). The index corresponds to a physical flap.
  // PROGMEM puts this into flash and doesn't consume SRAM (good since this is
  // so limited). This requires using pgm_read_byte() to read from flash.
  const char FLAP_CHARS[] PROGMEM = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789?!,.\":@#$&()+-*/=\%dhwroygbp";
  // -1 removes the trailing null
  const uint8_t NUM_FLAPS = sizeof(FLAP_CHARS) - 1;
}


SplitFlap::SplitFlap(SoftwareSerial* debugSerial) : debug(debugSerial) {}

void SplitFlap::begin() {
  // Staggered startup: delay proportional to module ID so all motors in a
  // large display don't surge current at the same instant.
  if (EepromStore::getModuleId() != 255) {
    delay(EepromStore::getModuleId() * 150);
  }

  home();
}

void SplitFlap::stepAdvance(uint16_t steps) {
  for (uint16_t k = 0; k < steps; k++) {
    Motor::step();
    bool edge = HomeSensor::detectRisingEdge();
    if (edge) {
      currentStepPos = EepromStore::getTotalSteps() - EepromStore::getHomeOffset();
    }
    currentStepPos++;
    if (currentStepPos >= EepromStore::getTotalSteps()) currentStepPos = 0;
  }
}

int8_t SplitFlap::currentFlapIndex() const { return currentFlapIdx; }

bool SplitFlap::isHome() {
  return HomeSensor::homeActive();
}

void SplitFlap::home() {
  debug->println("[Splitflap] homing");
  uint16_t safety = 0;

  // Step until the Hall sensor triggers, or bail after slightly more than
  // one full revolution (prevents infinite loops if sensor is broken/missing).
  while (!HomeSensor::homeActive() && safety < (EepromStore::getTotalSteps() + 500)) {
    stepAdvance(1);
    safety++;
  }

  // Advance the calibrated offset to reach flap 0
  stepAdvance(EepromStore::getHomeOffset());

  currentStepPos = 0;
  currentFlapIdx = 0;
  Motor::release();
}

uint16_t SplitFlap::calibrate() {
  debug->println("[Splitflap] calibrating");
  // Phase 1: If already on the home sensor, move off it first
  uint16_t safety = 0;
  while (HomeSensor::homeActive() && safety < 4000) {
    stepAdvance(1);
    safety++;
    delay(5);
  }

  // Phase 2: Find the leading edge of the home sensor
  safety = 0;
  while (!HomeSensor::homeActive() && safety < 5000) {
    stepAdvance(1);
    safety++;
  }

  // Phase 3: Find the trailing edge (start counting from a clean edge)
  while (HomeSensor::homeActive()) {
    stepAdvance(1);
  }

  // Phase 4: Count steps for one full revolution (trailing edge → next trailing edge)
  uint16_t measuredSteps = 0;
  while (!HomeSensor::homeActive() && measuredSteps < 5000) {
    stepAdvance(1);
    measuredSteps++;
  }
  while (HomeSensor::homeActive()) {
    stepAdvance(1);
    measuredSteps++;
  }

  EepromStore::saveTotalSteps(measuredSteps);
  home();
  return measuredSteps;
}

void SplitFlap::moveToIndex(uint8_t targetIndex) {
  debug->print("[Splitflap] moving to index: ");
  debug->println(targetIndex);
  if (targetIndex < 0 || targetIndex >= NUM_FLAPS) return;

  // Already showing the right flap — nothing to do
  if (currentFlapIdx == targetIndex) return;

  // If position is unknown, home first to get a reliable starting point
  if (currentFlapIdx == -1) {
    home();
  }

  uint16_t targetStepPos =
      (uint16_t)(((uint32_t)targetIndex * (uint32_t)EepromStore::getTotalSteps()) / NUM_FLAPS);
  uint16_t stepsToMove;
  if (targetStepPos < currentStepPos) {
    // Wrap around to the beginning
    stepsToMove = EepromStore::getTotalSteps() + targetStepPos - currentStepPos;
  } else {
    stepsToMove = targetStepPos - currentStepPos;
  }

  stepAdvance(stepsToMove);
  Motor::release();
  currentFlapIdx = targetIndex;
}

void SplitFlap::moveToChar(char targetChar) {
  debug->print("[Splitflap] moving to char: ");
  debug->println(targetChar);
  uint8_t targetIndex = 255;
  for (uint8_t i = 0; i < NUM_FLAPS; i++) {
    if ((char)pgm_read_byte(&FLAP_CHARS[i]) == targetChar) {
      targetIndex = i;
      break;
    }
  }
  if (targetIndex == 255) return; // Character not on this reel
  moveToIndex(targetIndex);
}

void SplitFlap::goToRawStep(uint16_t targetStep) {
  debug->print("[Splitflap] going to step: ");
  debug->println(targetStep);
  uint16_t stepsToMove = targetStep - currentStepPos;
  if (stepsToMove < 0) stepsToMove += EepromStore::getTotalSteps(); // Wrap

  stepAdvance(stepsToMove);
  Motor::release();
  currentFlapIdx = -2; // Position known in steps but not as a named character
}

