#ifndef SPLITFLAP_H
#define SPLITFLAP_H

#include <Arduino.h>
#include "debug_serial.h"

// =============================================================================
// SplitFlap — flap/character-level logic for one display module.
//
// This is where "index 7 means the letter G" and "home means find the
// home sensor, then advance the calibrated offset" live. It drives Motor for
// raw movement, but owns the actual decisions (homing sequence, calibration
// sequence, index resolution).
//
// Motion is non-blocking: moveToIndex(), home(), calibrate() and friends only
// start an operation, and update() (called every loop()) takes at most one
// step each time it's due. That keeps the bus serviced while the reel turns,
// and lets a new target or a stop() take effect mid-move. See the top of
// splitflap.cpp for the phases an operation goes through.
// =============================================================================

// Why the last homing or calibration failed. Cleared by the next successful
// home or calibration. Nothing is sent on the bus when this is set; it's
// surfaced by later features (status LED, dump).
enum SplitFlapError : uint8_t {
  SPLITFLAP_OK = 0,
  SPLITFLAP_HOME_NOT_FOUND = 1,              // home sensor never triggered
  SPLITFLAP_CALIBRATION_OUT_OF_RANGE = 2,    // measured steps were implausible
};

// Flap index values other than a flap number (0–63).
const int8_t FLAP_UNKNOWN = -1;  // the position is unknown; the reel needs homing
const int8_t FLAP_BETWEEN = -2;  // the step position is known, but not on a flap

class SplitFlap {
 public:
  // constexpr, so the global SplitFlap is built at compile time rather than
  // by start-up code storing each member (which costs far more flash).
  constexpr SplitFlap(DebugSerial* debugSerial) : debug(debugSerial) {}

  // ---- Setup and the update loop ----

  // Loads the revolution count, and schedules the auto-home (if enabled)
  // after the staggered startup delay, so all motors in a large display
  // don't surge current at the same instant.
  void begin();

  // Call every loop(). Starts any work that has come due, and takes the next
  // step of the current operation when its step delay has passed.
  void update();

  // ---- Motion commands ----
  // Each one replaces whatever the reel was doing, and cancels an exercise
  // or a queued character.

  // Moves to a flap by index (0–63): an even division of the revolution,
  // corrected by the flap's offset (see setFlapOffset()). Retargets a move
  // in progress. If the position is unknown, homes first; while homing, the
  // index is remembered and moved to once homing finishes.
  void moveToIndex(uint8_t targetIndex);

  // Looks up a character's index in FLAP_CHARS and delegates to moveToIndex().
  // No-op if the character isn't on this reel.
  void moveToChar(char targetChar);

  // moveToChar() after `delayMs`, for a frame broadcast's cascade. Replaces
  // anything already queued; any other motion command, or stop(), cancels it.
  void moveToCharAfter(char targetChar, uint16_t delayMs);

  // Burn-in: steps through every flap one at a time, `cycles` times round
  // the reel (each flap is its own move, with the ramp). Homes first if the
  // position is unknown. Any other motion command, or stop(), ends it.
  // 0 does nothing.
  void exercise(uint8_t cycles);

  // Starts driving the reel to the physical zero position (flap 0 = blank
  // space). If the home sensor isn't found within a revolution, the position
  // is left unknown and lastError() says why.
  void home();

  // Starts a calibration: finds home, measures one full revolution, saves it
  // and finishes at flap 0. A measurement outside the plausible range is not
  // saved. Does not report back to the Raspberry Pi; read the result with a
  // dump, which is answered once the calibration finishes.
  void calibrate();

  // Nudges the motor forward `steps` steps. The step position stays known,
  // but the flap index becomes FLAP_BETWEEN since the reel is no longer on a
  // flap. If the position is unknown it stays unknown.
  // Ignored while homing or calibrating.
  void nudge(uint16_t steps);

  // Moves to an absolute raw step position, bypassing character/index logic.
  // Ignored while homing or calibrating, or if the position is unknown.
  void goToRawStep(uint16_t targetStep);

  // Stops the current operation where it is. A stopped move leaves the step
  // position known (FLAP_BETWEEN); a stopped home or calibration leaves the
  // position unknown (FLAP_UNKNOWN).
  void stop();

  // ---- Settings that move flap 0 ----

  // Saves a new home offset. The current position was measured from the old
  // flap 0, so it becomes unknown and the next move homes first. Sent during
  // the offset phase of a home, the home starts over.
  void setHomeOffset(uint16_t offset);

  // Makes the current position flap 0, saving the matching home offset.
  // Ignored unless the position is known and the reel is standing still.
  void setHomeOffsetHere();

  // Saves a new number of steps per revolution. The current position was
  // counted in the old units, so it becomes unknown (stopping a move in
  // progress) and the next move homes first. No effect on a home or
  // calibration in progress.
  void setTotalSteps(uint16_t steps);

  // Saves the motor direction. A changed direction reverses the reel, so it
  // stops whatever the reel was doing (as stop()) and marks the position
  // unknown, and the next move homes first.
  void setMotorClockwise(bool clockwise);

  // ---- Per-flap correction ----

  // Saves the offset of the flap showing, as stored by EepromStore (steps +
  // FLAP_OFFSET_ZERO), then moves to the flap's new position. That's a short
  // move forward for a larger offset, and nearly a full revolution for a
  // smaller one, since the reel only turns forward. Ignored unless a flap
  // other than 0 is showing (flap 0 is where homing ends; the home offset
  // places it).
  void setFlapOffset(uint8_t offset);

  // ---- Status ----

  // True while an operation is in progress (the reel may be moving), or a
  // moveToCharAfter() is waiting to start.
  bool busy() const;

  // True while homing or calibrating (the position is being established).
  bool isHoming() const;

  // Returns the current flap index, or FLAP_UNKNOWN, or FLAP_BETWEEN if the step
  // is known but not the flap (including while a move is in progress).
  int8_t currentFlapIndex() const;

  // Returns the current step position.
  uint16_t currentStepPosition() const;

  // The reason the last homing or calibration failed, or SPLITFLAP_OK.
  SplitFlapError lastError() const;

  // How many steps the tracked position was off by the last time the home
  // edge was crossed with the position known. Positive means the tracked
  // position was ahead of the reel, i.e. the motor missed steps (usually a
  // step delay that's too short). Measured whether or not recalculateHome
  // is on; with it on, the position is corrected at each edge, so this is
  // the drift over one revolution. 0 until the first such edge.
  int16_t lastDrift() const;

  // Lifetime number of reel revolutions (home edges crossed), for
  // maintenance. Saved to EEPROM every 16 revolutions while idle, so up to
  // 15 can be lost at power-off.
  uint32_t revolutionCount() const;

 private:
  // What the motor is currently doing. See the top of splitflap.cpp for how
  // an operation moves between these.
  enum Phase : uint8_t {
    PHASE_IDLE,       // not moving
    PHASE_MOVE,       // stepping toward targetStepPos at the normal speed
    PHASE_SEEK_HOME,  // stepping at the homing speed until the home edge
    PHASE_MEASURE,    // calibrating: counting steps to the next home edge
    PHASE_OFFSET,     // advancing the home offset from the edge to flap 0
    PHASE_SETTLE,     // holding the coils after a move before releasing them
  };

  // pendingFlapIdx when no move is waiting on homing.
  static const int8_t NO_PENDING_FLAP = -1;

  // ---- Where the reel is ----
  uint16_t currentStepPos = 0;  // Current motor position in half-steps (0 = flap 0)
  int8_t currentFlapIdx = FLAP_UNKNOWN;  // Which flap is currently showing

  // ---- The operation in progress ----
  Phase phase = PHASE_IDLE;
  bool calibrating = false;     // PHASE_SEEK_HOME leads to PHASE_MEASURE
  uint16_t targetStepPos = 0;   // where a PHASE_MOVE stops
  int8_t targetFlapIdx = FLAP_BETWEEN;  // flap index a PHASE_MOVE ends on
  uint16_t stepsRemaining = 0;  // steps left in PHASE_MOVE / PHASE_OFFSET
  uint16_t stepsTaken = 0;      // steps since the phase began
  uint32_t lastStepUs = 0;      // micros() of the last step

  // ---- Work waiting to start ----
  int8_t pendingFlapIdx = NO_PENDING_FLAP;  // flap to move to once homing finishes
  uint16_t exerciseMoves = 0;   // single-flap moves left in an exercise
  bool charQueued = false;      // moveToCharAfter() is waiting to start
  char queuedChar = ' ';
  uint32_t queuedAtMs = 0;      // millis() to start moving to queuedChar
  bool autoHomePending = false; // home once the startup stagger has passed

  // ---- Results and statistics ----
  SplitFlapError error = SPLITFLAP_OK;
  int16_t drift = 0;             // see lastDrift()
  uint32_t revolutions = 0;      // see revolutionCount()
  uint32_t savedRevolutions = 0; // the count last written to EEPROM

  // Used for debug printing
  DebugSerial* debug = nullptr;  // not owned

  // ---- The update loop, one piece each ----

  // Starts a queued character or the auto-home once it's due.
  void startDueWork();

  // Writes the revolution count to EEPROM every 16 revolutions. Called while
  // idle, so the write doesn't stall a move.
  void saveRevolutionsIfDue();

  // The delay (µs) before the next step of the current phase.
  uint16_t stepDelayUs() const;

  // The delay (µs) before the next step of a PHASE_MOVE, ramping between the
  // ramp start delay and the step delay at each end of the move.
  uint16_t moveStepDelayUs() const;

  // Advances the current phase after a step. `edge` is whether the step
  // crossed the home edge.
  void afterStep(bool edge);
  void afterSeekStep(bool edge);
  void afterMeasureStep(bool edge);

  // ---- Starting and ending operations ----

  // moveToIndex() without cancelling an exercise in progress.
  void moveTo(uint8_t targetIndex);

  // Moves to a raw step position (see nudge() and goToRawStep()). Ignored
  // while homing or calibrating.
  void rawMove(uint16_t targetStep);

  // The step position of flap `flapIdx`, including its offset.
  uint16_t flapStepPos(uint8_t flapIdx) const;

  // Starts stepping toward `stepPos`; the move ends on flap `flapIdx`
  // (FLAP_BETWEEN for a raw step position).
  void startMove(uint16_t stepPos, int8_t flapIdx);

  // Starts a home (or, with `calibrate`, a calibration) from wherever the
  // reel is. The position is unknown until it finishes.
  void startHoming(bool calibrate);

  // Starts advancing the home offset from the home edge to flap 0.
  void startOffset();

  // Called when a PHASE_MOVE or PHASE_OFFSET has no steps left.
  void finishTravel();

  // Records a homing/calibration failure and marks the position unknown, so
  // the next move tries to home again instead of trusting a wrong position.
  void failHoming(SplitFlapError reason);

  // Ends an operation: holds the coils for the settle time, then releases
  // them, if release is enabled.
  void halt();

  // Stops immediately and releases the coils if release is enabled.
  void releaseNow();

  // Ends an exercise and drops a character queued by moveToCharAfter().
  // Every public motion command calls this first.
  void cancelQueued();

  // Marks the position unknown, including where a move in progress ends, so
  // the next move homes first.
  void forgetPosition();

  // True once the startup stagger for this module's ID has passed.
  bool staggerElapsed() const;

  // ---- Position tracking ----

  // Takes one half-step, keeping currentStepPos in step with it. This is the
  // one place motor movement and split-flap position tracking meet. Returns
  // whether the step crossed the home edge.
  bool stepAdvance();

  // Called when a step crosses the home edge: measures the drift, and
  // corrects currentStepPos using the home offset if recalculateHome is on.
  void onHomeEdge();

  // Steps from the current position forward to `targetStepPos`, wrapping
  // past the end of the revolution.
  uint16_t stepsToTarget(uint16_t targetStepPos) const;
};

#endif
