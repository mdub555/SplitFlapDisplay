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
  const char FLAP_CHARS[] PROGMEM = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789?!,.q:@#$&()+-*/=%dhwroygbp";
  // -1 removes the trailing null
  const uint8_t NUM_FLAPS = sizeof(FLAP_CHARS) - 1;

  // Extra steps allowed past one revolution when searching for home.
  const uint16_t HOME_SEARCH_MARGIN = 500;

  // A calibration measurement outside this window means the sensor missed or
  // double-triggered, so it is not saved.
  const uint16_t CALIBRATION_MIN_STEPS = 3500;
  const uint16_t CALIBRATION_MAX_STEPS = 4800;

  // flapIndexOf() for a character that isn't on the reel.
  const uint8_t NOT_ON_REEL = 255;

  // The index of `c` in FLAP_CHARS, or NOT_ON_REEL.
  uint8_t flapIndexOf(char c) {
    for (uint8_t i = 0; i < NUM_FLAPS; i++) {
      if ((char)pgm_read_byte(&FLAP_CHARS[i]) == c) return i;
    }
    return NOT_ON_REEL;
  }
}


SplitFlap::SplitFlap(DebugSerial* debugSerial) : debug(debugSerial) {}

void SplitFlap::begin() {
  revolutions = savedRevolutions = EepromStore::getRevolutions();
  autoHomePending = EepromStore::autoHomeEnabled();
}

void SplitFlap::update() {
  if (charQueued && (int32_t)(millis() - queuedAtMs) >= 0) {
    charQueued = false;
    moveToChar(queuedChar);
  }

  if (autoHomePending && staggerElapsed()) {
    // A move that arrived first has already homed (or is homing), which
    // makes this a no-op.
    autoHomePending = false;
    if (phase == PHASE_IDLE && currentFlapIdx == FLAP_UNKNOWN) {
      home();
    }
  }

  if (phase == PHASE_IDLE) {
    // Save the revolution count now and then, while idle so the EEPROM write
    // doesn't stall a move.
    if (revolutions - savedRevolutions >= 16) {
      EepromStore::saveRevolutions(revolutions);
      savedRevolutions = revolutions;
    }
    return;
  }
  uint32_t now = millis();
  if (phase == PHASE_SETTLE) {
    if (now - lastStepMs >= EepromStore::getSettleMs()) releaseNow();
    return;
  }
  if ((phase == PHASE_MOVE || phase == PHASE_OFFSET) && stepsRemaining == 0) {
    finishTravel();
    return;
  }

  uint8_t stepDelay;
  if (phase == PHASE_MOVE) {
    stepDelay = moveStepDelay();
  } else if (phase == PHASE_OFFSET) {
    stepDelay = EepromStore::getStepDelay();
  } else {
    stepDelay = EepromStore::getHomingStepDelay();
  }
  if (now - lastStepMs < stepDelay) return;
  lastStepMs = now;

  bool edge = stepAdvance();
  stepsTaken++;

  switch (phase) {
    case PHASE_MOVE:
      if (edge && EepromStore::recalculateHome()) {
        // currentStepPos was just snapped to ground truth, recompute the
        // remaining steps again to compensate for any drift.
        stepsRemaining = stepsToTarget(targetStepPos);
      } else {
        stepsRemaining--;
      }
      break;

    case PHASE_OFFSET:
      stepsRemaining--;
      break;

    case PHASE_SEEK_HOME: {
      if (edge) {
        if (calibrating) {
          // The step that lands on the next edge counts toward the revolution.
          phase = PHASE_MEASURE;
          stepsTaken = 0;
        } else {
          startOffset();
        }
        break;
      }
      // A revolution plus a margin, saturating at 65535 rather than wrapping
      // when total steps is near the top of its range.
      uint16_t total = EepromStore::getTotalSteps();
      uint16_t limit = total > 0xFFFF - HOME_SEARCH_MARGIN ? 0xFFFF : total + HOME_SEARCH_MARGIN;
      if (stepsTaken >= limit) {
        failHoming(SPLITFLAP_HOME_NOT_FOUND);
      }
      break;
    }

    case PHASE_MEASURE:
      if (edge) {
        debug->print("[Splitflap] steps measured: ");
        debug->println(stepsTaken);
        if (stepsTaken < CALIBRATION_MIN_STEPS || stepsTaken > CALIBRATION_MAX_STEPS) {
          failHoming(SPLITFLAP_CALIBRATION_OUT_OF_RANGE);
        } else {
          EepromStore::saveTotalSteps(stepsTaken);
          startOffset();
        }
      } else if (stepsTaken > CALIBRATION_MAX_STEPS) {
        failHoming(SPLITFLAP_CALIBRATION_OUT_OF_RANGE);
      }
      break;

    case PHASE_IDLE:
    case PHASE_SETTLE:
      break;
  }
}

uint8_t SplitFlap::moveStepDelay() const {
  uint8_t cruise = EepromStore::getStepDelay();
  uint8_t start = EepromStore::getRampStartDelay();
  uint8_t rampSteps = EepromStore::getRampSteps();
  // Distance from the nearer end of the move.
  uint16_t fromEnd = stepsTaken < stepsRemaining ? stepsTaken : stepsRemaining;
  if (fromEnd >= rampSteps || start <= cruise) return cruise;
  // Linear from `start` at the end of the move to `cruise` rampSteps in.
  return cruise + (uint16_t)(start - cruise) * (rampSteps - fromEnd) / rampSteps;
}

bool SplitFlap::staggerElapsed() const {
  uint8_t id = EepromStore::getModuleId();
  return id == EepromStore::UNPROVISIONED_ID ||
         millis() >= (uint32_t)id * EepromStore::getStaggerMs();
}

bool SplitFlap::busy() const { return phase != PHASE_IDLE || charQueued; }

void SplitFlap::cancelQueued() {
  exerciseMoves = 0;
  charQueued = false;
}

void SplitFlap::moveToCharAfter(char targetChar, uint16_t delayMs) {
  cancelQueued();
  queuedChar = targetChar;
  queuedAtMs = millis() + delayMs;
  charQueued = true;
}

bool SplitFlap::isHoming() const {
  return phase == PHASE_SEEK_HOME || phase == PHASE_MEASURE || phase == PHASE_OFFSET;
}

void SplitFlap::stop() {
  cancelQueued();  // also while idle: a frame's character may be waiting
  if (phase == PHASE_IDLE) return;
  // A move already marks the flap as FLAP_BETWEEN (and a settle is after the
  // move finished); homing or calibrating didn't establish the position.
  if (isHoming()) currentFlapIdx = FLAP_UNKNOWN;
  pendingFlapIdx = NO_PENDING_FLAP;
  releaseNow();
}

void SplitFlap::halt() {
  if (EepromStore::releaseMotorEnabled() && EepromStore::getSettleMs() > 0) {
    phase = PHASE_SETTLE;  // timed from the last step
  } else {
    releaseNow();
  }
}

void SplitFlap::releaseNow() {
  phase = PHASE_IDLE;
  if (EepromStore::releaseMotorEnabled()) {
    Motor::release();
  }
}

bool SplitFlap::stepAdvance() {
  Motor::step();
  currentStepPos++;
  // Wrap before checking the sensor, so the position is in range even when
  // this step lands on the home edge.
  if (currentStepPos >= EepromStore::getTotalSteps()) currentStepPos = 0;
  if (HomeSensor::detectRisingEdge()) {
    debug->println("[Splitflap] hit home sensor");
    revolutions++;
    uint16_t total = EepromStore::getTotalSteps();
    // Where the home edge should be, given the home offset. An offset of 0
    // puts the edge exactly on flap 0.
    uint16_t expected = total - EepromStore::getHomeOffset();
    if (expected >= total) expected = 0;
    if (currentFlapIdx != FLAP_UNKNOWN) {
      // How far the tracked position is past where the edge should be, in
      // the range -total/2..total/2. Skipped steps make this positive. Only
      // meaningful when the position was already known (not while homing).
      uint16_t ahead = currentStepPos >= expected ? currentStepPos - expected
                                                  : currentStepPos + total - expected;
      drift = ahead > total / 2 ? (int16_t)(ahead - total) : (int16_t)ahead;
    }
    if (EepromStore::recalculateHome()) {
      currentStepPos = expected;
    }
    return true;
  }
  return false;
}

int8_t SplitFlap::currentFlapIndex() const { return currentFlapIdx; }

SplitFlapError SplitFlap::lastError() const { return error; }

int16_t SplitFlap::lastDrift() const { return drift; }

uint32_t SplitFlap::revolutionCount() const { return revolutions; }

uint16_t SplitFlap::currentStepPosition() const { return currentStepPos; }

void SplitFlap::startMove(uint16_t stepPos, int8_t flapIdx) {
  // Retargeting a move in progress keeps its speed rather than ramping again.
  if (phase != PHASE_MOVE) stepsTaken = 0;
  phase = PHASE_MOVE;
  targetStepPos = stepPos;
  targetFlapIdx = flapIdx;
  stepsRemaining = stepsToTarget(stepPos);
  // Between flaps until the move finishes; an unknown position stays unknown.
  if (currentFlapIdx != FLAP_UNKNOWN) currentFlapIdx = FLAP_BETWEEN;
}

void SplitFlap::startHoming(bool calibrate) {
  phase = PHASE_SEEK_HOME;
  calibrating = calibrate;
  stepsTaken = 0;
  currentFlapIdx = FLAP_UNKNOWN;
}

void SplitFlap::startOffset() {
  // Advance the calibrated offset to reach flap 0
  phase = PHASE_OFFSET;
  stepsRemaining = EepromStore::getHomeOffset();
  stepsTaken = 0;
}

void SplitFlap::finishTravel() {
  if (phase == PHASE_OFFSET) {
    currentStepPos = 0;
    currentFlapIdx = 0;
    error = SPLITFLAP_OK;
    int8_t next = pendingFlapIdx;
    pendingFlapIdx = NO_PENDING_FLAP;
    phase = PHASE_IDLE;
    if (next > 0) {  // homing already ends on flap 0
      // A move arrived while homing; carry on to it without releasing.
      moveTo(next);
      return;
    }
  } else {
    currentFlapIdx = targetFlapIdx;
    if (exerciseMoves > 0 && currentFlapIdx >= 0) {
      // Next flap of an exercise, as a separate move so it ramps again.
      exerciseMoves--;
      phase = PHASE_IDLE;
      moveTo((currentFlapIdx + 1) % NUM_FLAPS);
      return;
    }
  }
  halt();
}

void SplitFlap::failHoming(SplitFlapError reason) {
  error = reason;
  currentFlapIdx = FLAP_UNKNOWN;
  pendingFlapIdx = NO_PENDING_FLAP;
  halt();
}

void SplitFlap::home() {
  debug->println("[Splitflap] homing");
  pendingFlapIdx = NO_PENDING_FLAP;
  cancelQueued();
  startHoming(false);
}

void SplitFlap::calibrate() {
  debug->println("[Splitflap] calibrating");
  pendingFlapIdx = NO_PENDING_FLAP;
  cancelQueued();
  startHoming(true);
}

void SplitFlap::moveToIndex(uint8_t targetIndex) {
  cancelQueued();
  moveTo(targetIndex);
}

void SplitFlap::exercise(uint8_t cycles) {
  cancelQueued();
  if (cycles == 0) return;
  // The first move is to the next flap (flap 1 if the position isn't known
  // as a flap: a home first if it's unknown, or straight there if it's
  // between flaps).
  exerciseMoves = (uint16_t)cycles * NUM_FLAPS - 1;
  moveTo(currentFlapIdx >= 0 ? (currentFlapIdx + 1) % NUM_FLAPS : 1);
}

void SplitFlap::moveTo(uint8_t targetIndex) {
  debug->print("[Splitflap] moving to index: ");
  debug->println(targetIndex);
  if (targetIndex >= NUM_FLAPS) return;

  // Homing in progress, or position unknown: move once homing finishes. If
  // homing fails, the move is dropped: the position would be a guess.
  if (isHoming() || currentFlapIdx == FLAP_UNKNOWN) {
    pendingFlapIdx = targetIndex;
    if (!isHoming()) startHoming(false);
    return;
  }

  // Already showing the right flap — nothing to do
  if (currentFlapIdx == targetIndex) return;

  startMove((uint16_t)(((uint32_t)targetIndex * (uint32_t)EepromStore::getTotalSteps()) / NUM_FLAPS),
            targetIndex);
}

void SplitFlap::moveToChar(char targetChar) {
  debug->print("[Splitflap] moving to char: ");
  debug->println(targetChar);
  uint8_t targetIndex = flapIndexOf(targetChar);
  if (targetIndex == NOT_ON_REEL) return;
  moveToIndex(targetIndex);
}

void SplitFlap::nudge(uint16_t steps) {
  // The target wraps past the end of the revolution without overflowing.
  uint16_t untilWrap = EepromStore::getTotalSteps() - currentStepPos;
  rawMove(steps < untilWrap ? currentStepPos + steps : steps - untilWrap);
}

void SplitFlap::goToRawStep(uint16_t targetStep) {
  debug->print("[Splitflap] going to step: ");
  debug->println(targetStep);
  // A step position only means something once the reel has been homed.
  if (currentFlapIdx == FLAP_UNKNOWN) return;
  rawMove(targetStep);
}

void SplitFlap::rawMove(uint16_t targetStep) {
  if (isHoming()) return;
  cancelQueued();
  // Known in steps but not as a flap, unless the position was unknown.
  startMove(targetStep, currentFlapIdx == FLAP_UNKNOWN ? FLAP_UNKNOWN : FLAP_BETWEEN);
}

void SplitFlap::forgetPosition() {
  currentFlapIdx = FLAP_UNKNOWN;
  targetFlapIdx = FLAP_UNKNOWN;  // so a move in progress doesn't restore it
}

void SplitFlap::setHomeOffset(uint16_t offset) {
  if (offset == EepromStore::getHomeOffset()) return;
  EepromStore::saveHomeOffset(offset);
  // Flap 0 has moved, so a position measured from the old one is wrong.
  if (phase == PHASE_OFFSET) {
    // Already advancing the old offset: find the home edge again.
    startHoming(false);
  } else if (!isHoming()) {
    forgetPosition();
  }
}

void SplitFlap::setHomeOffsetHere() {
  // The current position has to be known, and the reel standing still.
  if (currentFlapIdx == FLAP_UNKNOWN || (phase != PHASE_IDLE && phase != PHASE_SETTLE)) return;
  // currentStepPos counts from flap 0, which is the old offset past the edge.
  uint32_t offset = (uint32_t)EepromStore::getHomeOffset() + currentStepPos;
  EepromStore::saveHomeOffset(offset % EepromStore::getTotalSteps());
  currentStepPos = 0;
  currentFlapIdx = 0;
}

void SplitFlap::setTotalSteps(uint16_t steps) {
  if (steps == EepromStore::getTotalSteps()) return;
  EepromStore::saveTotalSteps(steps);
  // Homing establishes the position in the new units (and a calibration
  // measures the total itself). Otherwise the position, counted in the old
  // units, is no longer meaningful.
  if (isHoming()) return;
  if (phase == PHASE_MOVE) stop();  // its target is in the old units too
  forgetPosition();
  currentStepPos = 0;  // keep it below the new total
}

uint16_t SplitFlap::stepsToTarget(uint16_t targetStepPos) const {
  if (targetStepPos < currentStepPos) {
    // Wrap around to the beginning
    return EepromStore::getTotalSteps() + targetStepPos - currentStepPos;
  }
  return targetStepPos - currentStepPos;
}

