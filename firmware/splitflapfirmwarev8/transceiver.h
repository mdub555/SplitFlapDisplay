#ifndef TRANSCEIVER_H
#define TRANSCEIVER_H

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
// outside the command's range (see COMMANDS in transceiver.cpp), instead of
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
//         d, Dump the module state back to the Raspberry Pi (format at
//            Transceiver::dump() below). If the module is moving, homing or
//            calibrating, the reply is sent once that finishes. A broadcast
//            ('m*d') is answered by every provisioned module in turn: each
//            waits ID x 75 ms (after finishing anything in progress) so the
//            replies don't collide. Unprovisioned modules don't answer a
//            broadcast. No data expected
//         j, Enable or disable recalculating home. 1 to continuously recalculate,
//            0 to only calculate on home.
//         k, Set the delay between each motor step during normal operation, in
//            milliseconds.
//         l, Set the delay between each motor step during homing and calibration
//            operations, in milliseconds.
//         x, Stop whatever the motor is doing. A stopped move keeps its step
//            position; a stopped home or calibration leaves the position
//            unknown, so the next move homes first. No data expected
//         u, Set the step delay at the start and end of a move, in
//            milliseconds (1-255). Moves ramp between this and the step delay.
//         n, Set how many steps the ramp takes at each end of a move (0-255,
//            0 = no ramp).
//         e, Set how long to hold the coils after a move before releasing
//            them, in milliseconds (0-255). Only used when release is on.
//         y, Set the startup stagger: the auto-home waits this many
//            milliseconds per module ID after power-on (0-255). Takes effect
//            on the next boot.
//         f, Identify: blink the status LED quickly for 10 seconds, to find
//            which physical module has this ID. No data expected
//         z, Reboot the module. No data expected
//         q, Reset every setting to its default, keeping the module ID, then
//            reboot. No data expected
//         v, Exercise: step through every flap one at a time, N times round
//            the reel (1-255; 0 does nothing). Any other motion command or
//            'x' ends it.
//
// Frame broadcast: "m*F<interval>:<pairs>\n" sets every module at once.
//   <pairs> has two bytes per module, for IDs 0, 1, 2, ... in order: the
//   character to show, then its place in the animation as a printable byte,
//   '!' + rank (rank 0 starts first). A module starts moving rank x
//   <interval> ms (0-255) after the frame ends, so the display can still
//   cascade in any order without a message per module. A module whose ID has
//   no pair ignores the frame. The pairs are read as they arrive rather than
//   buffered, so a frame can be longer than BUFFER_SIZE; up to 94 modules
//   (the printable ranks).
// =============================================================================

// Each command's letter and accepted data are in COMMANDS in transceiver.cpp,
// which is indexed by this enum: keep the two in the same order.
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
  STOP,                   // 'x'
  SET_RAMP_START_DELAY,   // 'u'
  SET_RAMP_STEPS,         // 'n'
  SET_SETTLE_MS,          // 'e'
  SET_STAGGER_MS,         // 'y'
  IDENTIFY,               // 'f'
  REBOOT,                 // 'z'
  RESET_SETTINGS,         // 'q'
  EXERCISE,               // 'v'
  FRAME,                  // 'F' (broadcast only, see above)
};

struct Command {
  CommandType type = UNKNOWN_COMMAND;
  bool broadcast = false;  // addressed with '*' rather than this module's ID
  union Data {
    char dataChar;
    uint16_t dataInt;
  };
  Data data = {'0'};
  uint16_t frameDelayMs = 0;  // FRAME: wait before moving to dataChar
};

class Transceiver {
 private:
  char buffer[BUFFER_SIZE];
  uint8_t bufferLen = 0;
  uint32_t lastSerialTime = 0;

  // Frame broadcast in progress: the header "m*F<interval>:" is in the
  // buffer and the pairs are being counted as they arrive.
  bool inFrame = false;
  uint16_t framePos = 0;       // bytes of pairs received so far
  uint8_t frameInterval = 0;   // ms per rank
  char frameChar = ' ';        // this module's character, once received
  uint8_t frameRank = 0;       // and its rank
  bool frameHit = false;       // both of this module's bytes received

  // Parses the buffered message into `command`, then empties the buffer
  // (leaving the message for message()). Returns whether it was a valid
  // command for this module.
  bool parseBuffer(Command& command);

  // Starts frame mode if the buffer holds a complete frame header.
  void checkFrameHeader();

  // Handles one byte of a frame's pairs. Returns true with `command` filled
  // in when the frame ends with this module's pair received.
  bool frameByte(char c, Command& command);

 public:
  // Sets up the RX, TX and DE pins and begins the RS-485 serial link. Call
  // once from setup().
  void begin(long baud);

  // Call every loop() iteration. Reads any available bytes and populates a
  // buffer. If it detects a complete command in this loop, it parses and
  // populates the given command, and returns true. If no command has completed
  // this loop, it leaves the given command alone and returns false.
  // Also flushes stalled numeric commands after a short timeout (handles
  // messages with a missed or absent terminator).
  bool poll(Command& command);

  // Sends: m<ID>d:<homeOffset>:<totalSteps>:<debounceMs>:<stepDelay>
  //              :<homingStepDelay>:<clockwise>:<autoHome>:<releaseMotor>
  //              :<recalculateHome>:<rampStartDelay>:<rampSteps>:<settleMs>
  //              :<staggerMs>:<revolutions>:<drift>
  // where revolutions and drift come from SplitFlap, passed in by the
  // caller. Drift stays last; new fields go before it. Typically ~50 bytes.
  void dump(uint32_t revolutions, int16_t drift);

  // The last message poll() parsed, as received (without the '\n'). Only
  // valid until the next call to poll().
  const char* message() const;
};

#endif

