#ifndef TRANSCEIVER_H
#define TRANSCEIVER_H

#include <Arduino.h>

// The buffer used to read in from the RS-485. The longest expected command
// would be on the order of 'm64T4096\n', 9 characters, so 32 should be
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
//         N, the ID of the specific module targeted (at least one digit)
//   - CMD, grouped by kind: lowercase letters (and - +) are actions,
//     punctuation is about the module itself, and uppercase letters are
//     settings saved to EEPROM, which always take a number.
//
//     Actions
//         -, Display a character. data must be a single character
//         +, Display a flap by index. data must be a number
//         h, Home the module. No data expected
//         c, Calibrate the module, calculating the number of steps in a full
//            rotation. No data expected
//         n, Nudge the stepper motor forward N steps. Doesn't change the home
//            offset; use 'O0' afterwards to save the new position as the
//            offset. data must be a number
//         g, Go to a specific motor step. data must be a number. Ignored until
//            the module has been homed
//         x, Stop whatever the motor is doing. A stopped move keeps its step
//            position; a stopped home or calibration leaves the position
//            unknown, so the next move homes first. No data expected
//         e, Exercise: step through every flap one at a time, N times round
//            the reel (1-255; 0 does nothing). Any other motion command or
//            'x' ends it.
//         b, Identify: blink the status LED quickly for 10 seconds, to find
//            which physical module has this ID. No data expected
//         r, Reboot the module. No data expected
//         f, Frame broadcast; see below.
//
//     Module
//         ?, Dump the module state back to the Raspberry Pi (format at
//            Transceiver::dump() below). If the module is moving, homing or
//            calibrating, the reply is sent once that finishes. A broadcast
//            ('m*?') is answered by every provisioned module in turn: each
//            waits ID x 105 ms (after finishing anything in progress) so the
//            replies don't collide. Unprovisioned modules don't answer a
//            broadcast. No data expected
//         !, Reset every setting to its default, keeping the module ID, then
//            reboot. No data expected
//         @, Set the module ID. data must be a number. A broadcast ('m*@')
//            is only accepted by unprovisioned modules (ID 255), so it can't
//            give every module on the bus the same ID
//         %, Dump the flap offsets (see 'J'): every flap's offset, as stored,
//            in two hex digits per flap from flap 0 (format at
//            Transceiver::dumpFlapOffsets() below). Sent once the module is
//            idle, as for '?'. Addressed to one module only; a broadcast is
//            ignored, as the replies would collide. No data expected
//
//     Settings
//         O, Set the offset number of steps from where home is detected to the
//            blank flap. data must be a number. 0 instead makes the current
//            position the blank flap (only while the position is known and
//            the reel is still). A changed offset marks the position unknown,
//            so the next move homes first
//         T, Set the number of steps in a full rotation. data must be a number.
//            A changed value stops any move and marks the position unknown,
//            so the next move homes first
//         D, Set the debounce delay for the home sensor, in milliseconds
//            (0-65535).
//         E, Enable or disable recalculating home at each home edge. 1 to
//            continuously recalculate, 0 to only calculate on home.
//         A, Enable or disable auto-home. data must be 0 for disable, 1 for
//            enable
//         C, Set the motor direction. data must be 1 for clockwise, 0 for
//            counter-clockwise
//         F, Enable or disable freeing (releasing) the motor coils when idle.
//            data must be 1 to release, 0 to keep them energized
//         S, Set the delay between each motor step during normal operation, in
//            microseconds (1-65535).
//         H, Set the delay between each motor step during homing and calibration
//            operations, in microseconds (1-65535).
//         R, Set the step delay at the start and end of a move (the ramp), in
//            microseconds (1-65535). Moves ramp between this and the step delay.
//         L, Set how many steps the ramp takes at each end of a move (0-255,
//            0 = no ramp).
//         W, Set how long to wait, holding the coils, after a move before
//            releasing them, in milliseconds (0-255). Only used when release
//            is on.
//         P, Set the power-on stagger: the auto-home waits this many
//            milliseconds per module ID after power-on (0-255). Takes effect
//            on the next boot.
//         J, Set the offset of the flap showing, for a flap that doesn't
//            land quite where an even division of the revolution puts it, in
//            steps plus 128 (0-255: 128 = none, 125 = 3 steps back, 131 = 3
//            forward), then move to its new position. Ignored unless a flap
//            other than 0 is showing (the home offset 'O' places flap 0).
//            Addressed to one module only; a broadcast is ignored. Read the
//            offsets back with '%'.
//
// Frame broadcast: "m*f<interval>:<pairs>\n" sets every module at once.
//   <pairs> has two bytes per module, for IDs 0, 1, 2, ... in order: the
//   character to show, then its place in the animation as a printable byte,
//   '!' + rank (rank 0 starts first). A module starts moving rank x
//   <interval> ms (0-255) after the frame ends, so the display can still
//   cascade in any order without a message per module. A module whose ID has
//   no pair ignores the frame. The pairs are read as they arrive rather than
//   buffered, so a frame can be longer than BUFFER_SIZE; up to 94 modules
//   (the printable ranks).
// =============================================================================

// Each command's letter and accepted data are in COMMANDS in transceiver.cpp.
enum CommandType : uint8_t {
  UNKNOWN_COMMAND,
  // Actions
  DISPLAY_CHAR,           // '-'
  DISPLAY_INDEX,          // '+'
  HOME,                   // 'h'
  CALIBRATE,              // 'c'
  NUDGE,                  // 'n'
  MOVE_TO_STEP,           // 'g'
  STOP,                   // 'x'
  EXERCISE,               // 'e'
  IDENTIFY,               // 'b'
  REBOOT,                 // 'r'
  FRAME,                  // 'f' (broadcast only, see above)
  // Module
  DUMP_STATE,             // '?'
  RESET_SETTINGS,         // '!'
  SET_MODULE_ID,          // '@'
  DUMP_FLAP_OFFSETS,      // '%'
  // Settings
  SET_OFFSET,             // 'O'
  SET_TOTAL_STEPS,        // 'T'
  SET_DEBOUNCE_MS,        // 'D'
  SET_RECALCULATE_HOME,   // 'E'
  SET_AUTO_HOME,          // 'A'
  SET_MOTOR_CW,           // 'C'
  SET_MOTOR_RELEASE,      // 'F'
  SET_STEP_DELAY,         // 'S'
  SET_HOMING_STEP_DELAY,  // 'H'
  SET_RAMP_START_DELAY,   // 'R'
  SET_RAMP_STEPS,         // 'L'
  SET_SETTLE_MS,          // 'W'
  SET_STAGGER_MS,         // 'P'
  SET_FLAP_OFFSET,        // 'J'
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

  // Frame broadcast in progress: the header "m*f<interval>:" is in the
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

  // Sends m<ID>? and then each field as a tab, a label and the value:
  //   m05?\tO480\tT4096\tD100\tS1000\tH1000\tC1\tA1\tF1\tE1\tR3000\tL0\tW0\tP150\t#12\t~-3
  // A setting is labelled with the letter that sets it (O = home offset,
  // T = total steps, and so on; see the command list above). The two
  // read-only fields are # = revolutions and ~ = drift, both from SplitFlap,
  // passed in by the caller. Fields can be read in any order. Typically ~75
  // bytes.
  void dump(uint32_t revolutions, int16_t drift);

  // Sends m<ID>% and then each flap's stored offset (see the 'J' command) as
  // two uppercase hex digits, from flap 0 to 63:
  //   m05%8080837D8080...
  // 133 bytes in all, about 140 ms at 9600 baud.
  void dumpFlapOffsets();

  // The last message poll() parsed, as received (without the '\n'). Only
  // valid until the next call to poll().
  const char* message() const;
};

#endif

