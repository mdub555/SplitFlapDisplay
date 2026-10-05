#ifndef SPLITFLAP_H
#define SPLITFLAP_H

#include <Arduino.h>
#include <SoftwareSerial.h>

// =============================================================================
// SplitFlap — flap/character-level logic for one display module.
//
// This is where "index 7 means the letter G" and "home means find the
// home sensor, then advance the calibrated offset" live. It drives Motor for
// raw movement, but owns the actual decisions (homing sequence, calibration
// sequence, index resolution).
// =============================================================================
class SplitFlap {
 private:
  uint16_t currentStepPos = 0;  // Current motor position in half-steps (0 = flap 0)
  int8_t currentFlapIdx = -1;   // Which flap is currently showing (-1 = unknown)

  // Used for debug printing
  SoftwareSerial* debug = nullptr;  // not owned

  // Advances `steps` half-steps, correcting currentStepPos using the known
  // home offset whenever the home sensor's rising edge is crossed. This is
  // the one place motor movement and split-flap position tracking meet.
  bool stepAdvance();

  uint16_t stepsToTarget(uint16_t targetStepPos) const;

 public:
  SplitFlap(SoftwareSerial* debugSerial);

  // Applies the staggered startup delay and homes the module.
  void begin();

  // Returns if the module is actively home (according to the home sensor).
  bool isHome();

  // Returns the current flap index, or -1 if it's unknown, or -2 if the step
  // is known but not the flap.
  int8_t currentFlapIndex() const;

  // Returns the current step position.
  uint16_t currentStepPosition() const;

  // Move the motor `steps` steps.
  bool stepAdvance(uint16_t steps);

  // Drives the reel to the physical zero position (flap 0 = blank space).
  void home();

  // Spins one full revolution to measure step count, saves it, and re-homes.
  // Returns the measured step count. Does not report back to the Raspberry Pi.
  uint16_t calibrate();

  // Moves to a flap by index (0–63), using an even division of the revolution.
  void moveToIndex(uint8_t targetIndex);

  // Looks up a character's index in FLAP_CHARS and delegates to moveToIndex().
  // No-op if the character isn't on this reel.
  void moveToChar(char targetChar);

  // Moves to an absolute raw step position, bypassing character/index logic.
  void goToRawStep(uint16_t targetStep);
};

#endif

