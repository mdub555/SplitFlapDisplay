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
// and lets a new target or a stop() take effect mid-move.
// =============================================================================

// Why the last homing or calibration failed. Cleared by the next successful
// home or calibration. Nothing is sent on the bus when this is set; it's
// surfaced by later features (status LED, dump).
enum SplitFlapError : uint8_t {
  SPLITFLAP_OK = 0,
  SPLITFLAP_HOME_NOT_FOUND = 1,              // home sensor never triggered
  SPLITFLAP_CALIBRATION_OUT_OF_RANGE = 2,    // measured steps were implausible
};

class SplitFlap {
 private:
  // What the motor is currently doing.
  enum Phase : uint8_t {
    PHASE_IDLE,       // not moving
    PHASE_MOVE,       // stepping toward targetStepPos at the normal speed
    PHASE_SEEK_HOME,  // stepping at the homing speed until the home edge
    PHASE_MEASURE,    // calibrating: counting steps to the next home edge
    PHASE_OFFSET,     // advancing the home offset from the edge to flap 0
    PHASE_SETTLE,     // holding the coils after a move before releasing them
  };

  uint16_t currentStepPos = 0;  // Current motor position in half-steps (0 = flap 0)
  int8_t currentFlapIdx = -1;   // Which flap is currently showing (-1 = unknown)
  SplitFlapError error = SPLITFLAP_OK;
  int16_t drift = 0;            // see lastDrift()
  uint32_t revolutions = 0;     // see revolutionCount()
  uint32_t savedRevolutions = 0; // the count last written to EEPROM
  uint16_t exerciseMoves = 0;   // single-flap moves left in an exercise
  bool charQueued = false;      // moveToCharAfter() is waiting to start
  char queuedChar = ' ';
  uint32_t queuedAtMs = 0;      // millis() to start moving to queuedChar

  Phase phase = PHASE_IDLE;
  bool calibrating = false;     // PHASE_SEEK_HOME leads to PHASE_MEASURE
  bool autoHomePending = false; // home once the startup stagger has passed
  int8_t targetFlapIdx = -2;    // flap index a PHASE_MOVE ends on (-2 = raw step)
  int8_t pendingFlapIdx = -1;   // flap to move to once homing finishes (-1 = none)
  uint16_t targetStepPos = 0;   // where a PHASE_MOVE stops
  uint16_t stepsRemaining = 0;  // steps left in PHASE_MOVE / PHASE_OFFSET
  uint16_t stepsTaken = 0;      // steps since the phase began
  uint32_t lastStepMs = 0;      // millis() of the last step

  // Used for debug printing
  DebugSerial* debug = nullptr;  // not owned

  // Takes one half-step, correcting currentStepPos using the known home
  // offset whenever the home sensor's rising edge is crossed. This is the one
  // place motor movement and split-flap position tracking meet. Returns
  // whether the step crossed the home edge.
  bool stepAdvance();

  // moveToIndex() without cancelling an exercise in progress.
  void moveTo(uint8_t targetIndex);

  // Ends an exercise and drops a character queued by moveToCharAfter().
  // Every public motion command calls this first.
  void cancelQueued();

  uint16_t stepsToTarget(uint16_t targetStepPos) const;

  // Starts stepping toward `stepPos`; the move ends on flap `flapIdx`
  // (-2 for a raw step position).
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

  // The delay before the next step of a PHASE_MOVE, ramping between the ramp
  // start delay and the step delay at each end of the move.
  uint8_t moveStepDelay() const;

 public:
  SplitFlap(DebugSerial* debugSerial);

  // Loads the revolution count, and schedules the auto-home (if enabled)
  // after the staggered startup delay, so all motors in a large display
  // don't surge current at the same instant.
  void begin();

  // Call every loop(). Takes the next step of the current operation when its
  // step delay has passed.
  void update();

  // True while an operation is in progress (the reel may be moving), or a
  // moveToCharAfter() is waiting to start.
  bool busy() const;

  // True while homing or calibrating (the position is being established).
  bool isHoming() const;

  // Stops the current operation where it is. A stopped move leaves the step
  // position known (flap index -2); a stopped home or calibration leaves the
  // position unknown (-1).
  void stop();

  // Returns if the module is actively home (according to the home sensor).
  bool isHome();

  // Returns the current flap index, or -1 if it's unknown, or -2 if the step
  // is known but not the flap (including while a move is in progress).
  int8_t currentFlapIndex() const;

  // Returns the current step position.
  uint16_t currentStepPosition() const;

  // Nudges the motor forward `steps` steps. The step position stays known,
  // but the flap index becomes -2 since the reel is no longer on a flap.
  // Ignored while homing or calibrating.
  void nudge(uint16_t steps);

  // Starts driving the reel to the physical zero position (flap 0 = blank
  // space). If the home sensor isn't found within a revolution, the position
  // is left unknown and lastError() says why.
  void home();

  // Starts a calibration: finds home, measures one full revolution, saves it
  // and finishes at flap 0. A measurement outside the plausible range is not
  // saved. Does not report back to the Raspberry Pi; read the result with a
  // dump, which is answered once the calibration finishes.
  void calibrate();

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

  // Burn-in: steps through every flap one at a time, `cycles` times round
  // the reel (each flap is its own move, with the ramp). Homes first if the
  // position is unknown. Any other motion command, or stop(), ends it.
  // 0 does nothing.
  void exercise(uint8_t cycles);

  // Moves to a flap by index (0–63), using an even division of the revolution.
  // Retargets a move in progress. If the position is unknown, homes first;
  // while homing, the index is remembered and moved to once homing finishes.
  void moveToIndex(uint8_t targetIndex);

  // Looks up a character's index in FLAP_CHARS and delegates to moveToIndex().
  // No-op if the character isn't on this reel.
  void moveToChar(char targetChar);

  // moveToChar() after `delayMs`, for a frame broadcast's cascade. Replaces
  // anything already queued; any other motion command, or stop(), cancels it.
  void moveToCharAfter(char targetChar, uint16_t delayMs);

  // Moves to an absolute raw step position, bypassing character/index logic.
  // Ignored while homing or calibrating.
  void goToRawStep(uint16_t targetStep);
};

#endif
