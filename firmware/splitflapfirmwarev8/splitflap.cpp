#include "splitflap.h"

#include "debug_serial.h"
#include "eeprom_store.h"
#include "home_sensor.h"
#include "motor.h"

// =============================================================================
// How an operation runs
//
// Every operation is a sequence of phases. A command starts the first phase,
// and update() steps the motor and moves on to the next phase as each one
// finishes:
//
//   move:       MOVE -> SETTLE -> IDLE
//   home:       SEEK_HOME -edge-> OFFSET -> SETTLE -> IDLE
//   calibrate:  SEEK_HOME -edge-> MEASURE -edge-> OFFSET -> SETTLE -> IDLE
//
// A move while the position is unknown homes first: the target waits in
// pendingFlapIdx, and OFFSET carries straight on into MOVE. An exercise is a
// chain of MOVEs, one per flap. SETTLE is skipped unless the coils are
// released when idle and the settle time is above 0. A home or calibration
// that fails goes to SETTLE with the position unknown.
//
// The file is laid out in the same order as the header: setup and the update
// loop, the motion commands, settings that move flap 0, status, then the
// private helpers that start and end operations and track the position.
// =============================================================================

namespace {
  // The ordered set of 64 characters this reel can display. Position 0 is
  // blank (the "home" flap). The index corresponds to a physical flap.
  // PROGMEM puts this into flash and doesn't consume SRAM (good since this is
  // so limited). This requires using pgm_read_byte() to read from flash.
  const char FLAP_CHARS[] PROGMEM = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789?!,.q:@#$&()+-*/=%dhwroygbp";
  // -1 removes the trailing null
  const uint8_t NUM_FLAPS = sizeof(FLAP_CHARS) - 1;
  static_assert(NUM_FLAPS == 64, "FLAP_CHARS needs one character per flap (64)");
  static_assert(NUM_FLAPS == EepromStore::NUM_FLAP_OFFSETS, "EEPROM needs one offset per flap");

  // Extra steps allowed past one revolution when searching for home.
  const uint16_t HOME_SEARCH_MARGIN = 500;

  // A calibration measurement outside this window means the sensor missed or
  // double-triggered, so it is not saved.
  const uint16_t CALIBRATION_MIN_STEPS = 3500;
  const uint16_t CALIBRATION_MAX_STEPS = 4800;

  // The revolution count is saved to EEPROM after this many revolutions.
  const uint8_t REVOLUTIONS_PER_SAVE = 16;

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

// =============================================================================
// Setup and the update loop
// =============================================================================

void SplitFlap::begin() {
  revolutions = savedRevolutions = EepromStore::getRevolutions();
  autoHomePending = EepromStore::autoHomeEnabled();
}

void SplitFlap::update() {
  startDueWork();

  if (phase == PHASE_IDLE) {
    saveRevolutionsIfDue();
    return;
  }
  if (phase == PHASE_SETTLE) {
    if (micros() - lastStepUs >= EepromStore::getSettleMs() * 1000UL) releaseNow();
    return;
  }
  if ((phase == PHASE_MOVE || phase == PHASE_OFFSET) && stepsRemaining == 0) {
    finishTravel();
    return;
  }

  uint32_t now = micros();
  if (now - lastStepUs < stepDelayUs()) return;
  lastStepUs = now;

  bool edge = stepAdvance();
  stepsTaken++;
  afterStep(edge);
}

void SplitFlap::startDueWork() {
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
}

void SplitFlap::saveRevolutionsIfDue() {
  if (revolutions - savedRevolutions >= REVOLUTIONS_PER_SAVE) {
    EepromStore::saveRevolutions(revolutions);
    savedRevolutions = revolutions;
  }
}

uint16_t SplitFlap::stepDelayUs() const {
  switch (phase) {
    case PHASE_MOVE:   return moveStepDelayUs();
    case PHASE_OFFSET: return EepromStore::getStepDelayUs();
    default:           return EepromStore::getHomingStepDelayUs();
  }
}

uint16_t SplitFlap::moveStepDelayUs() const {
  uint16_t cruise = EepromStore::getStepDelayUs();
  uint16_t start = EepromStore::getRampStartDelayUs();
  uint8_t rampSteps = EepromStore::getRampSteps();
  // Distance from the nearer end of the move.
  uint16_t fromEnd = stepsTaken < stepsRemaining ? stepsTaken : stepsRemaining;
  if (fromEnd >= rampSteps || start <= cruise) return cruise;
  // Linear from `start` at the end of the move to `cruise` rampSteps in.
  // 32-bit, since the difference times the ramp length can pass 65535.
  return cruise + (uint32_t)(start - cruise) * (rampSteps - fromEnd) / rampSteps;
}

void SplitFlap::afterStep(bool edge) {
  switch (phase) {
    case PHASE_MOVE:
      stepsRemaining--;
      // currentStepPos was just snapped to ground truth: recompute the
      // remaining steps to compensate for any drift. Not for a raw move from
      // an unknown position (a nudge), whose target is a distance rather
      // than a place, nor for a move whose position was forgotten mid-way.
      if (edge && EepromStore::recalculateHome() && targetFlapIdx != FLAP_UNKNOWN) {
        // A negative drift means the edge came early and the snap moved the
        // position forward by -drift. If that jumped over the target, the
        // move has arrived; recomputing would wrap round a whole revolution.
        uint16_t remaining = stepsToTarget(targetStepPos);
        stepsRemaining = drift < 0 && remaining > stepsRemaining ? 0 : remaining;
      }
      break;
    case PHASE_OFFSET:
      stepsRemaining--;
      break;
    case PHASE_SEEK_HOME:
      afterSeekStep(edge);
      break;
    case PHASE_MEASURE:
      afterMeasureStep(edge);
      break;
    case PHASE_IDLE:
    case PHASE_SETTLE:
      break;
  }
}

void SplitFlap::afterSeekStep(bool edge) {
  if (edge) {
    if (calibrating) {
      // The step that lands on the next edge counts toward the revolution.
      phase = PHASE_MEASURE;
      stepsTaken = 0;
    } else {
      startOffset();
    }
    return;
  }
  // A revolution plus a margin, compared without adding them so it can't
  // wrap, and giving up at the last count before stepsTaken would wrap when
  // total steps is near the top of its range. A calibration searches the
  // longest revolution it accepts instead, since it may be measuring
  // because total steps is wrong (say, 2048 for a 4096-step reel).
  uint16_t total = calibrating ? CALIBRATION_MAX_STEPS : EepromStore::getTotalSteps();
  if (stepsTaken >= total && (stepsTaken - total >= HOME_SEARCH_MARGIN || stepsTaken == 0xFFFF)) {
    failHoming(SPLITFLAP_HOME_NOT_FOUND);
  }
}

void SplitFlap::afterMeasureStep(bool edge) {
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
}

// =============================================================================
// Motion commands
// =============================================================================

void SplitFlap::moveToIndex(uint8_t targetIndex) {
  cancelQueued();
  moveTo(targetIndex);
}

void SplitFlap::moveToChar(char targetChar) {
  debug->print("[Splitflap] moving to char: ");
  debug->println(targetChar);
  uint8_t targetIndex = flapIndexOf(targetChar);
  if (targetIndex == NOT_ON_REEL) return;
  moveToIndex(targetIndex);
}

void SplitFlap::moveToCharAfter(char targetChar, uint16_t delayMs) {
  cancelQueued();
  queuedChar = targetChar;
  queuedAtMs = millis() + delayMs;
  charQueued = true;
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

void SplitFlap::stop() {
  cancelQueued();  // also while idle: a frame's character may be waiting
  if (phase == PHASE_IDLE) return;
  // A move already marks the flap as FLAP_BETWEEN (and a settle is after the
  // move finished); homing or calibrating didn't establish the position.
  if (isHoming()) currentFlapIdx = FLAP_UNKNOWN;
  pendingFlapIdx = NO_PENDING_FLAP;
  releaseNow();
}

// =============================================================================
// Settings that move flap 0
// =============================================================================

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

void SplitFlap::setMotorClockwise(bool clockwise) {
  if (clockwise == EepromStore::isMotorClockwise()) return;
  EepromStore::saveMotorDir(clockwise);
  // The reel now turns the other way, so whatever it was doing, and the
  // position it was counted to, no longer hold.
  stop();
  forgetPosition();
}

// =============================================================================
// Per-flap correction
// =============================================================================

void SplitFlap::setFlapOffset(uint8_t offset) {
  // Only while a flap is showing: during a move it's FLAP_BETWEEN, while
  // homing FLAP_UNKNOWN.
  int8_t flapIdx = currentFlapIdx;
  if (flapIdx <= 0) return;
  cancelQueued();
  EepromStore::saveFlapOffset(flapIdx, offset);
  startMove(flapStepPos(flapIdx), flapIdx);
}

// =============================================================================
// Status
// =============================================================================

bool SplitFlap::busy() const { return phase != PHASE_IDLE || charQueued; }

bool SplitFlap::isHoming() const {
  return phase == PHASE_SEEK_HOME || phase == PHASE_MEASURE || phase == PHASE_OFFSET;
}

int8_t SplitFlap::currentFlapIndex() const { return currentFlapIdx; }

uint16_t SplitFlap::currentStepPosition() const { return currentStepPos; }

SplitFlapError SplitFlap::lastError() const { return error; }

int16_t SplitFlap::lastDrift() const { return drift; }

uint32_t SplitFlap::revolutionCount() const { return revolutions; }

// =============================================================================
// Starting and ending operations
// =============================================================================

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

  startMove(flapStepPos(targetIndex), targetIndex);
}

uint16_t SplitFlap::flapStepPos(uint8_t flapIdx) const {
  uint16_t total = EepromStore::getTotalSteps();
  int32_t stepPos = ((uint32_t)flapIdx * total) / NUM_FLAPS +
                    EepromStore::getFlapOffset(flapIdx) - EepromStore::FLAP_OFFSET_ZERO;
  // An offset can put a flap past either end of the revolution (more than
  // once, for a total steps set implausibly low).
  while (stepPos < 0) stepPos += total;
  while (stepPos >= total) stepPos -= total;
  return stepPos;
}

void SplitFlap::rawMove(uint16_t targetStep) {
  if (isHoming()) return;
  cancelQueued();
  // Known in steps but not as a flap, unless the position was unknown.
  startMove(targetStep, currentFlapIdx == FLAP_UNKNOWN ? FLAP_UNKNOWN : FLAP_BETWEEN);
}

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
    // Homing is done: the reel is on flap 0.
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

void SplitFlap::cancelQueued() {
  exerciseMoves = 0;
  charQueued = false;
}

void SplitFlap::forgetPosition() {
  currentFlapIdx = FLAP_UNKNOWN;
  targetFlapIdx = FLAP_UNKNOWN;  // so a move in progress doesn't restore it
}

bool SplitFlap::staggerElapsed() const {
  uint8_t id = EepromStore::getModuleId();
  return id == EepromStore::UNPROVISIONED_ID ||
         millis() >= (uint32_t)id * EepromStore::getStaggerMs();
}

// =============================================================================
// Position tracking
// =============================================================================

bool SplitFlap::stepAdvance() {
  Motor::step();
  currentStepPos++;
  // Wrap before checking the sensor, so the position is in range even when
  // this step lands on the home edge.
  if (currentStepPos >= EepromStore::getTotalSteps()) currentStepPos = 0;
  if (!HomeSensor::detectRisingEdge()) return false;
  onHomeEdge();
  return true;
}

void SplitFlap::onHomeEdge() {
  debug->println("[Splitflap] hit home sensor");
  revolutions++;
  uint16_t total = EepromStore::getTotalSteps();
  // Where the home edge should be, given the home offset. An offset of 0
  // puts the edge exactly on flap 0.
  // An offset of a revolution or more (after total steps was lowered) lands
  // where its remainder does. Subtracting rather than %, which would link in
  // a division routine.
  uint16_t offset = EepromStore::getHomeOffset();
  while (offset >= total) offset -= total;
  uint16_t expected = offset ? total - offset : 0;
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
}

uint16_t SplitFlap::stepsToTarget(uint16_t targetStepPos) const {
  if (targetStepPos < currentStepPos) {
    // Wrap around to the beginning
    return EepromStore::getTotalSteps() + targetStepPos - currentStepPos;
  }
  return targetStepPos - currentStepPos;
}
