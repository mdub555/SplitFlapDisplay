#include "motor.h"

#include <Arduino.h>

#include "eeprom_store.h"
#include "pinout.h"

namespace {
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
    digitalWrite(MOTOR_IN1, step[0]);
    digitalWrite(MOTOR_IN2, step[1]);
    digitalWrite(MOTOR_IN3, step[2]);
    digitalWrite(MOTOR_IN4, step[3]);
  }
}

namespace Motor{
  void begin() {
    pinMode(MOTOR_IN1, OUTPUT);
    pinMode(MOTOR_IN2, OUTPUT);
    pinMode(MOTOR_IN3, OUTPUT);
    pinMode(MOTOR_IN4, OUTPUT);
  }

  void step() {
    if (EepromStore::isMotorClockwise()) {
      currentPhase--;
    } else {
      currentPhase++;
    }
    if (currentPhase < 0) currentPhase = 7;
    if (currentPhase > 7) currentPhase = 0;

    applyStep(halfStepSequence[currentPhase]);
  }

  void release() {
    digitalWrite(MOTOR_IN1, 0);
    digitalWrite(MOTOR_IN2, 0);
    digitalWrite(MOTOR_IN3, 0);
    digitalWrite(MOTOR_IN4, 0);
  }

  void tense() {
    applyStep(halfStepSequence[currentPhase]);
  }
}

