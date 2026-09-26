#ifndef MOTOR_H
#define MOTOR_H

// ==============================================================================
// Motor — low-level stepper
// ==============================================================================

namespace Motor{
  // Initialize and pins necessary to control the motor.
  void begin();

  // Do a single step in the forward (advancing the flaps) direction.
  void step();

  // Release the power on all stepper pins. Friction and the magnets should
  // hold it in place well enough.
  void release();

  // Add power back to the stepper pins. This doesn't change which step
  // the motor is on.
  void tense();
}

#endif

