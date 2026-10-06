#include "splitflap.h"

#include "debug_serial.h"
#include "eeprom_store.h"
#include "home_sensor.h"
#include "motor.h"

namespace {
  // The ordered set of 64 characters this reel can display. Position 0 is
  // blank (the "home" flap). The index corresponds to a physical flap.
  // PROGMEM puts this into flash and doesn't consume SRAM (good since this is
  // so limited). This requires using pgm_read_byte() to read from flash.
  const char FLAP_CHARS[] PROGMEM = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789?!,.q:@#$&()+-*/=\%dhwroygbp";
  // -1 removes the trailing null
  const uint8_t NUM_FLAPS = sizeof(FLAP_CHARS) - 1;

  // Extra steps allowed past one revolution when searching for home.
  const uint16_t HOME_SEARCH_MARGIN = 500;

  // A calibration measurement outside this window means the sensor missed or
  // double-triggered, so it is not saved.
  const uint16_t CALIBRATION_MIN_STEPS = 3500;
  const uint16_t CALIBRATION_MAX_STEPS = 4800;
}


SplitFlap::SplitFlap(DebugSerial* debugSerial) : debug(debugSerial) {}

void SplitFlap::begin() {
  // Staggered startup: delay proportional to module ID so all motors in a
  // large display don't surge current at the same instant.
  if (EepromStore::getModuleId() != 255) {
    delay(EepromStore::getModuleId() * 150);
  }

  if (EepromStore::autoHomeEnabled()) {
    home();
  }
}

bool SplitFlap::stepAdvance(uint16_t steps) {
  bool edgeHit = false;
  for (uint16_t k = 0; k < steps; k++) {
    if (stepAdvance()) {
      edgeHit = true;
    }
    delay(EepromStore::getStepDelay());
  }
  return edgeHit;
}

bool SplitFlap::stepAdvance() {
  Motor::step();
  currentStepPos++;
  // Wrap before checking the sensor, so the position is in range even when
  // this step lands on the home edge.
  if (currentStepPos >= EepromStore::getTotalSteps()) currentStepPos = 0;
  if (HomeSensor::detectRisingEdge()) {
    debug->println("[Splitflap] hit home sensor");
    if (EepromStore::recalculateHome()) {
      currentStepPos = EepromStore::getTotalSteps() - EepromStore::getHomeOffset();
      // An offset of 0 puts the edge exactly on flap 0.
      if (currentStepPos >= EepromStore::getTotalSteps()) currentStepPos = 0;
    }
    return true;
  }
  return false;
}

int8_t SplitFlap::currentFlapIndex() const { return currentFlapIdx; }

SplitFlapError SplitFlap::lastError() const { return error; }

uint16_t SplitFlap::currentStepPosition() const { return currentStepPos; }

bool SplitFlap::isHome() {
  return HomeSensor::homeActive();
}

bool SplitFlap::advanceToHomeEdge() {
  uint16_t limit;
  if (-1 - HOME_SEARCH_MARGIN < EepromStore::getTotalSteps()) {
    limit = EepromStore::getTotalSteps() + HOME_SEARCH_MARGIN;
  } else {
    limit = -1;
  }
  for (uint16_t taken = 0; taken < limit; taken++) {
    bool edge = stepAdvance();
    delay(EepromStore::getHomingStepDelay());
    if (edge) return true;
  }
  return false;
}

void SplitFlap::failHoming(SplitFlapError reason) {
  error = reason;
  currentFlapIdx = -1;
  if (EepromStore::releaseMotorEnabled()) {
    Motor::release();
  }
}

void SplitFlap::finishHoming() {
  // Advance the calibrated offset to reach flap 0
  stepAdvance(EepromStore::getHomeOffset());
  currentStepPos = 0;
  currentFlapIdx = 0;
  error = SPLITFLAP_OK;
  if (EepromStore::releaseMotorEnabled()) {
    Motor::release();
  }
}

bool SplitFlap::home() {
  debug->println("[Splitflap] homing");

  // Advance until the next leading edge
  if (!advanceToHomeEdge()) {
    failHoming(SPLITFLAP_HOME_NOT_FOUND);
    return false;
  }
  finishHoming();
  return true;
}

uint16_t SplitFlap::calibrate() {
  debug->println("[Splitflap] calibrating");

  // Advance until the first leading edge
  if (!advanceToHomeEdge()) {
    failHoming(SPLITFLAP_HOME_NOT_FOUND);
    return 0;
  }

  // Advance for one full rotation until the next leading edge. The step that
  // lands on the edge counts toward the revolution.
  uint16_t measuredSteps = 0;
  bool edge = false;
  while (!edge && measuredSteps <= CALIBRATION_MAX_STEPS) {
    edge = stepAdvance();
    measuredSteps++;
    delay(EepromStore::getHomingStepDelay());
  }

  debug->print("[Splitflap] steps measured: ");
  debug->println(measuredSteps);
  if (!edge || measuredSteps < CALIBRATION_MIN_STEPS || measuredSteps > CALIBRATION_MAX_STEPS) {
    failHoming(SPLITFLAP_CALIBRATION_OUT_OF_RANGE);
    return 0;
  }
  EepromStore::saveTotalSteps(measuredSteps);

  // Go to home flap
  finishHoming();
  return measuredSteps;
}

void SplitFlap::moveToIndex(uint8_t targetIndex) {
  debug->print("[Splitflap] moving to index: ");
  debug->println(targetIndex);
  if (targetIndex >= NUM_FLAPS) return;

  // Already showing the right flap — nothing to do
  if (currentFlapIdx == targetIndex) return;

  // If position is unknown, home first to get a reliable starting point. If
  // homing fails, don't move: the position would be a guess.
  if (currentFlapIdx == -1 && !home()) {
    return;
  }

  uint16_t targetStepPos =
      (uint16_t)(((uint32_t)targetIndex * (uint32_t)EepromStore::getTotalSteps()) / NUM_FLAPS);
  uint16_t stepsRemaining = stepsToTarget(targetStepPos);

  while (stepsRemaining > 0) {
    bool edge = stepAdvance();
    delay(EepromStore::getStepDelay());
    stepsRemaining--;
    if (edge && EepromStore::recalculateHome()) {
      // currentStepPos was just snapped to ground truth, recompute the
      // remaining steps again to compensate for any drift.
      stepsRemaining = stepsToTarget(targetStepPos);
    }
  }

  if (EepromStore::releaseMotorEnabled()) {
    Motor::release();
  }
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

void SplitFlap::nudge(uint16_t steps) {
  stepAdvance(steps);
  if (EepromStore::releaseMotorEnabled()) {
    Motor::release();
  }
  currentFlapIdx = -2; // Position known in steps but not as a named character
}

void SplitFlap::goToRawStep(uint16_t targetStep) {
  debug->print("[Splitflap] going to step: ");
  debug->println(targetStep);
  uint16_t stepsToMove = stepsToTarget(targetStep);

  stepAdvance(stepsToMove);
  if (EepromStore::releaseMotorEnabled()) {
    Motor::release();
  }
  currentFlapIdx = -2; // Position known in steps but not as a named character
}

uint16_t SplitFlap::stepsToTarget(uint16_t targetStepPos) const {
  if (targetStepPos < currentStepPos) {
    // Wrap around to the beginning
    return EepromStore::getTotalSteps() + targetStepPos - currentStepPos;
  }
  return targetStepPos - currentStepPos;
}

