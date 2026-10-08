// The simulated hardware around the firmware: a clock, and a reel that the
// real motor.cpp turns and the real home_sensor.cpp reads.
#ifndef FAKE_HARDWARE_H
#define FAKE_HARDWARE_H

#include <stdint.h>

#include <vector>

namespace FakeClock {
  // Moves time forward. Nothing else does: the firmware only sees time pass
  // between calls to loop().
  void advanceUs(uint32_t us);
  uint32_t nowUs();
  // Back to 0, as millis() and micros() are at every power-on.
  void resetForBoot();
}

// The reel as the motor and home sensor see it. The motor's coil pattern is
// decoded into steps: the reel advances one half-step for each step the
// firmware takes in the direction it's wired for, and goes back for each
// step the other way.
struct FakeReel {
  uint16_t stepsPerRev = 4096;   // the real revolution, whatever the firmware has saved
  uint16_t position = 1000;      // half-steps from where the home contact starts
  uint16_t contactSteps = 200;   // how long the home contact stays closed
  bool sensorConnected = true;   // false: the home sensor never triggers
  bool forwardWhenClockwise = true;  // how the motor is wired
  uint16_t stepsToMiss = 0;      // the next N steps don't move the reel (a stall)

  // What the coils have done.
  bool energized = false;
  uint32_t forwardSteps = 0;
  uint32_t backwardSteps = 0;
  std::vector<uint32_t> stepTimesUs;  // micros() of each step that moved the reel

  bool homeContactClosed() const { return sensorConnected && position < contactSteps; }

  // Half-steps the reel is past the start of the home contact.
  uint16_t stepsPastHome() const { return position; }

  void coilsChanged(uint8_t coils);

 private:
  uint8_t phase = 0;  // index in the half-step sequence; motor.cpp starts at 0
  void move(int8_t direction);
};
extern FakeReel reel;

// The pins that aren't the motor's: the status LED's level.
namespace FakePins {
  extern uint8_t statusLed;
}

// Set by the firmware writing the software reset register.
extern bool rebootRequested;

// Puts the fake hardware back as it is at power-on (the EEPROM keeps its
// contents, as it would).
void resetFakeHardware();

#endif
