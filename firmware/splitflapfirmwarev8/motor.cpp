#include "motor.h"

#include <Arduino.h>

#include "eeprom_store.h"
#include "pinout.h"

namespace {
  int  currentPhase  = 0;    // Index into halfStepSequence[8]

  // The four coil pins are PB2-PB5, so a whole step is written to the port in
  // one go instead of four digitalWrite() calls. digitalWrite() has to look
  // up the port and bit for a pin at runtime, which costs ~270 bytes of flash.
  static_assert(MOTOR_IN1 == PIN_PB2 && MOTOR_IN2 == PIN_PB3 &&
                MOTOR_IN3 == PIN_PB4 && MOTOR_IN4 == PIN_PB5,
                "motor.cpp writes the coils to PB2-PB5 directly");
  const uint8_t COIL_SHIFT = 2;
  const uint8_t COIL_MASK = 0x0F << COIL_SHIFT;

  // Half-step sequence for a 4-wire stepper motor. Each entry energizes the
  // coils in the order needed to step forward; walking the table backward
  // (decrementing the index) steps the motor in the flap-advancing direction.
  // Bit 0 is coil A (MOTOR_IN1) up to bit 3 for coil D (MOTOR_IN4).
  const uint8_t halfStepSequence[8] = {
    0b0001,   // Phase 0: coil A only
    0b0011,   // Phase 1: coils A+B
    0b0010,   // Phase 2: coil B only
    0b0110,   // Phase 3: coils B+C
    0b0100,   // Phase 4: coil C only
    0b1100,   // Phase 5: coils C+D
    0b1000,   // Phase 6: coil D only
    0b1001    // Phase 7: coils D+A
  };

  // Sets the four coil pins to `coils`, leaving the rest of port B alone.
  void applyCoils(uint8_t coils) {
    VPORTB.OUT = (VPORTB.OUT & ~COIL_MASK) | (coils << COIL_SHIFT);
  }
}

namespace Motor{
  void begin() {
    VPORTB.DIR |= COIL_MASK;
  }

  void step() {
    if (EepromStore::isMotorClockwise()) {
      currentPhase--;
    } else {
      currentPhase++;
    }
    if (currentPhase < 0) currentPhase = 7;
    if (currentPhase > 7) currentPhase = 0;

    applyCoils(halfStepSequence[currentPhase]);
  }

  void release() {
    applyCoils(0);
  }

  void tense() {
    applyCoils(halfStepSequence[currentPhase]);
  }
}

