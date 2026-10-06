#ifndef TRANCEIVER_H
#define TRANCEIVER_H

#include <Arduino.h>

// The buffer used to read in from the RS-485. The longest expected command
// would be on the order of 'm64t4096\n', 9 characters, so 32 should be
// adequate without taking too much of the 512B SRAM available on an ATTiny816.
#define BUFFER_SIZE 32

// =============================================================================
// RS-485 link and message parser.
//
// Wire format: "m<ID><CMD>[data]\n"
//
// Numeric data is an unsigned 16-bit value (0–65535). The parser rejects a
// number that doesn't fit, a numeric command with no digits, or a value
// outside the command's range (see LIMITS in tranceiver.cpp), instead of
// wrapping, defaulting to 0, or truncating it.
//   - ID
//         *, wildcard, all modules targeted
//         N, the ID of the specific module targeted
//   - CMD
//         -, Display a character. data must be a single character
//         +, Display an index. data must be a number
//         h, Home the module. No data expected
//         c, Calibrate the module, calculating the number of steps in a full
//            rotation. No data expected
//         o, Set the offset number of steps from where home is detected to the
//            blank flap. data must be a number
//         t, Set the number of steps in a full rotation. data must be a number
//         b, Set the debounce delay for the home sensor. data must be a number
//         s, Nudge the stepper motor forward N steps. Doesn't change the home
//            offset; use 'o0' afterwards to save the new position as the
//            offset. data must be a number
//         g, Goto a specific motor step. data must be a number
//         i, Set the module ID. data must be a number. A broadcast ('m*i')
//            is only accepted by unprovisioned modules (ID 255), so it can't
//            give every module on the bus the same ID
//         a, Enable or disable auto-home. data must be 0 for disable, 1 for
//            enable
//         w, Set the motor direction. data must be 1 for clockwise, 0 for
//            counter-clockwise
//         r, Enable or disable releasing the motor coils when idle. data must
//            be 1 to release, 0 to keep them energized
//         d, Dump the module state back to the Raspberry Pi in the format
//            m<ID>d:<homeOffset>:<totalSteps>:<motorDir>:<autoHome>:<releaseMotor>.
//            No data expected
//         j, Enable or disable recalculating home. 1 to continuously recalculate,
//            0 to only calculate on home.
//         k, Set the delay between each motor step during normal operation, in
//            milliseconds.
//         l, Set the delay between each motor step during homing and calibration
//            operations, in milliseconds.
// =============================================================================
enum CommandType {
  UNKNOWN_COMMAND,
  DISPLAY_CHAR,           // '-'
  DISPLAY_INDEX,          // '+'
  HOME,                   // 'h'
  CALIBRATE,              // 'c'
  SET_OFFSET,             // 'o'
  SET_TOTAL_STEPS,        // 't'
  SET_DEBOUNCE_MS,        // 'b'
  NUDGE,                  // 's'
  MOVE_TO_STEP,           // 'g'
  SET_MODULE_ID,          // 'i'
  SET_AUTO_HOME,          // 'a'
  DUMP_STATE,             // 'd'
  SET_MOTOR_CW,           // 'w'
  SET_MOTOR_RELEASE,      // 'r'
  SET_RECALCULATE_HOME,   // 'j'
  SET_STEP_DELAY,         // 'k'
  SET_HOMING_STEP_DELAY,  // 'l'
};

struct Command {
  CommandType type = UNKNOWN_COMMAND;
  union Data {
    char dataChar;
    uint16_t dataInt;
  };
  Data data = {'0'};
};

class Tranceiver {
 private:
  char buffer[BUFFER_SIZE];
  uint8_t bufferLen = 0;
  uint32_t lastSerialTime = 0;

 public:
  // Sets up the DE pin and RS-485 serial link. Call once from setup().
  Tranceiver() = default;

  // Setup the RX, TX, and DE pins and begin the serial library.
  void begin(long baud);

  // Call every loop() iteration. Reads any available bytes and populates a
  // buffer. If it detects a complete command in this loop, it parses and
  // populates the given command, and returns true. If no command has completed
  // this loop, it leaves the given command alone and returns false.
  // Also flushes stalled numeric commands after a short timeout (handles
  // messages with a missed or absent terminator).
  bool poll(Command& poll);

  // Sends: m<ID>d:<homeOffset>:<totalSteps>:<debounceMs>:<stepDelay>
  //              :<homingStepDelay>:<clockwise>:<autoHome>:<releaseMotor>
  //              :<recalculateHome>
  void dump();
};

#endif

