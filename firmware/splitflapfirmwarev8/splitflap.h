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
  uint16_t currentStepPos = 0;  // Current motor position in half-steps (0 = flap 0)
  int8_t currentFlapIdx = -1;   // Which flap is currently showing (-1 = unknown)
  SplitFlapError error = SPLITFLAP_OK;

  // Used for debug printing
  DebugSerial* debug = nullptr;  // not owned

  // Advances `steps` half-steps, correcting currentStepPos using the known
  // home offset whenever the home sensor's rising edge is crossed. This is
  // the one place motor movement and split-flap position tracking meet.
  bool stepAdvance();

  // Move the motor `steps` steps at the normal step delay.
  bool stepAdvance(uint16_t steps);

  uint16_t stepsToTarget(uint16_t targetStepPos) const;

  // Steps at the homing speed until the home sensor's rising edge, giving up
  // after a full revolution plus a margin. Returns whether the edge was found.
  bool advanceToHomeEdge();

  // Records a homing/calibration failure and marks the position unknown, so
  // the next move tries to home again instead of trusting a wrong position.
  void failHoming(SplitFlapError reason);

  // Advances the home offset from the home edge to flap 0 and marks the
  // module homed. Shared by home() and calibrate().
  void finishHoming();

 public:
  SplitFlap(DebugSerial* debugSerial);

  // Applies the staggered startup delay and homes the module.
  void begin();

  // Returns if the module is actively home (according to the home sensor).
  bool isHome();

  // Returns the current flap index, or -1 if it's unknown, or -2 if the step
  // is known but not the flap.
  int8_t currentFlapIndex() const;

  // Returns the current step position.
  uint16_t currentStepPosition() const;

  // Nudges the motor forward `steps` steps. The step position stays known,
  // but the flap index becomes -2 since the reel is no longer on a flap.
  void nudge(uint16_t steps);

  // Drives the reel to the physical zero position (flap 0 = blank space).
  // Returns false, and leaves the position unknown, if the home sensor isn't
  // found within a revolution.
  bool home();

  // Spins one full revolution to measure step count, saves it, and re-homes.
  // Returns the measured step count, or 0 if the home sensor wasn't found or
  // the measurement was outside the plausible range (nothing is saved then).
  // Does not report back to the Raspberry Pi; read the result with a dump.
  uint16_t calibrate();

  // The reason the last homing or calibration failed, or SPLITFLAP_OK.
  SplitFlapError lastError() const;

  // Moves to a flap by index (0–63), using an even division of the revolution.
  void moveToIndex(uint8_t targetIndex);

  // Looks up a character's index in FLAP_CHARS and delegates to moveToIndex().
  // No-op if the character isn't on this reel.
  void moveToChar(char targetChar);

  // Moves to an absolute raw step position, bypassing character/index logic.
  void goToRawStep(uint16_t targetStep);
};

#endif

