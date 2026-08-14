#include "motor.h"

#include <Arduino.h>

#define IN1 PIN_PB2  // 7
#define IN2 PIN_PB3  // 6
#define IN3 PIN_PB4  // 5
#define IN4 PIN_PB5  // 4

namespace {
  const int STEP_DELAY = 1;  // Milliseconds between each half-step pulse
  int  currentPhase  = 0;    // Index into halfStepSequence[8]

  // Half-step sequence for a 4-wire stepper motor. Each row energizes the
  // coils in the order needed to step forward; walking the table backward
  // (decrementing the index) steps the motor in the flap-advancing direction.
  const uint8_t halfStepSequence[8][4] = {
    {1, 0, 0, 0},   // Phase 0: coil A only
    {1, 1, 0, 0},   // Phase 1: coils A+B
    {0, 1, 0, 0},   // Phase 2: coil B only
    {0, 1, 1, 0},   // Phase 3: coils B+C
    {0, 0, 1, 0},   // Phase 4: coil C only
    {0, 0, 1, 1},   // Phase 5: coils C+D
    {0, 0, 0, 1},   // Phase 6: coil D only
    {1, 0, 0, 1}    // Phase 7: coils D+A
  };

  void applyStep(const uint8_t *step) {
    digitalWrite(IN1, step[0]);
    digitalWrite(IN2, step[1]);
    digitalWrite(IN3, step[2]);
    digitalWrite(IN4, step[3]);
  }
}

namespace Motor{
  void begin() {
    pinMode(IN1, OUTPUT);
    pinMode(IN2, OUTPUT);
    pinMode(IN3, OUTPUT);
    pinMode(IN4, OUTPUT);
  }

  void step() {
    currentPhase++;
    if (currentPhase >= 8) currentPhase = 0;

    applyStep(halfStepSequence[currentPhase]);
    delay(STEP_DELAY);
  }

  void release() {
    digitalWrite(IN1, 0);
    digitalWrite(IN2, 0);
    digitalWrite(IN3, 0);
    digitalWrite(IN4, 0);
  }
}

