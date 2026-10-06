#include "transceiver.h"

#include <Arduino.h>

#include "eeprom_store.h"

namespace {
  enum ParseState {
    IDLE,               // looking for the first 'm'
    READING_ID,         // digits or '*', dispatches command on first non-digit
    READING_CMD,        // reading a single character which corresponds to the command
    READING_DATA_CHAR,  // reading a single character for the char to display
    READING_DATA_INT,   // reading in multiple digits for one of many commands
  };

  // How a command's data is read, and for numbers, the accepted range.
  // Checking ranges here, in one place, is much smaller than a check in each
  // setter in the .ino.
  enum ArgKind : uint8_t {
    ARG_NONE,         // no data: the command is complete once its letter is read
    ARG_CHAR,         // a single character
    ARG_ANY,          // 0-65535
    ARG_BOOLEAN,      // 0-1
    ARG_BYTE,         // 0-255
    ARG_DELAY,        // 1-255: 0 would remove the step delay entirely
    ARG_TOTAL_STEPS,  // 1-65535: 0 breaks the movement math
    ARG_BELOW_TOTAL,  // 0 to total steps - 1
  };

  struct CommandSpec {
    char code;    // the command's letter on the wire
    ArgKind arg;
  };

  // Every command's letter and data, indexed by CommandType (keep it in the
  // same order as the enum).
  const CommandSpec COMMANDS[] = {
    {'\0', ARG_NONE},         // UNKNOWN_COMMAND
    {'-', ARG_CHAR},          // DISPLAY_CHAR
    {'+', ARG_BYTE},          // DISPLAY_INDEX: moveToIndex() ignores indexes past the last flap
    {'h', ARG_NONE},          // HOME
    {'c', ARG_NONE},          // CALIBRATE
    {'o', ARG_BELOW_TOTAL},   // SET_OFFSET
    {'t', ARG_TOTAL_STEPS},   // SET_TOTAL_STEPS
    {'b', ARG_ANY},           // SET_DEBOUNCE_MS
    {'s', ARG_BELOW_TOTAL},   // NUDGE
    {'g', ARG_BELOW_TOTAL},   // MOVE_TO_STEP
    {'i', ARG_BYTE},          // SET_MODULE_ID
    {'a', ARG_BOOLEAN},       // SET_AUTO_HOME
    {'d', ARG_NONE},          // DUMP_STATE
    {'w', ARG_BOOLEAN},       // SET_MOTOR_CW
    {'r', ARG_BOOLEAN},       // SET_MOTOR_RELEASE
    {'j', ARG_BOOLEAN},       // SET_RECALCULATE_HOME
    {'k', ARG_DELAY},         // SET_STEP_DELAY
    {'l', ARG_DELAY},         // SET_HOMING_STEP_DELAY
    {'x', ARG_NONE},          // STOP
    {'u', ARG_DELAY},         // SET_RAMP_START_DELAY
    {'n', ARG_BYTE},          // SET_RAMP_STEPS
    {'e', ARG_BYTE},          // SET_SETTLE_MS
    {'y', ARG_BYTE},          // SET_STAGGER_MS
    {'f', ARG_NONE},          // IDENTIFY
    {'z', ARG_NONE},          // REBOOT
    {'q', ARG_NONE},          // RESET_SETTINGS
    {'v', ARG_BYTE},          // EXERCISE
    {'\0', ARG_NONE},         // FRAME: only reached through the frame header
  };
  static_assert(sizeof(COMMANDS) / sizeof(COMMANDS[0]) == FRAME + 1,
                "COMMANDS needs one entry per CommandType");

  CommandType toCommandType(char c) {
    // UNKNOWN_COMMAND and FRAME have no letter, so they're skipped.
    for (uint8_t type = UNKNOWN_COMMAND + 1; type < FRAME; type++) {
      if (COMMANDS[type].code == c) return (CommandType)type;
    }
    return UNKNOWN_COMMAND;
  }

  // Finishes a numeric command, rejecting it if it had no digits (a truncated
  // "m05k" must not set a 0 ms delay) or its value is out of range.
  bool finishDataInt(Command& command, uint16_t value, bool hasDigits) {
    if (!hasDigits) return false;
    uint16_t max = 0xFFFF;
    switch (COMMANDS[command.type].arg) {
      case ARG_BOOLEAN:     max = 1; break;
      case ARG_DELAY:       if (value == 0) return false;  // fall through
      case ARG_BYTE:        max = 255; break;
      case ARG_TOTAL_STEPS: if (value == 0) return false; break;
      case ARG_BELOW_TOTAL: max = EepromStore::getTotalSteps() - 1; break;
      case ARG_ANY:
      case ARG_NONE:
      case ARG_CHAR:        break;
    }
    if (value > max) return false;
    command.data.dataInt = value;
    return true;
  }

  __attribute__((noinline)) bool toCommand(Command& command, const char* buffer, uint8_t bufferLen) {
    command.data.dataInt = 0;
    command.type = UNKNOWN_COMMAND;
    command.broadcast = false;
    ParseState parseState = IDLE;
    // Wider than a module ID so an ID above 255 can't wrap around and match
    // a real module (e.g. "m261" must not reach module 5).
    uint16_t id = 0;
    uint16_t value = 0;
    bool hasDigits = false;
    for (uint8_t i = 0; i < bufferLen; i++) {
      char c = buffer[i];
      switch (parseState) {
        // Idle — watch for 'm' start-of-message marker.
        case IDLE:
          if (c == 'm') {
            parseState = READING_ID;
          }
          break;

        // Accumulate the module ID field (digits or '*'), then start reading
        // the command on the first character that's neither.
        case READING_ID:
          if (c == '*') {
            command.broadcast = true;
            parseState = READING_CMD;
            break;
          } else if (isDigit(c)) {
            if (id <= 255) {
              id *= 10;
              id += c - '0';
            }
            break;
          } else {
            if (id != EepromStore::getModuleId()) {
              return false;
            }
            parseState = READING_CMD;
          }
          // fall through: this character is the command

        case READING_CMD:
          command.type = toCommandType(c);
          // A broadcast ID change would give every module the same ID, so
          // only an unprovisioned module accepts one.
          if (command.type == SET_MODULE_ID && command.broadcast &&
              EepromStore::getModuleId() != EepromStore::UNPROVISIONED_ID) {
            return false;
          }
          switch (COMMANDS[command.type].arg) {
            case ARG_NONE:
              return command.type != UNKNOWN_COMMAND;
            case ARG_CHAR:
              parseState = READING_DATA_CHAR;
              break;
            default:
              parseState = READING_DATA_INT;
              break;
          }
          break;

        // Numeric commands — accumulate digits, execute on any non-digit
        // terminator (typically '\n'). Values that don't fit in 16 bits are
        // rejected.
        case READING_DATA_INT:
          if (isDigit(c)) {
            uint8_t digit = c - '0';
            // Reject anything above 65535 rather than wrapping.
            if (value > 6553 || (value == 6553 && digit > 5)) {
              return false;
            }
            value = value * 10 + digit;
            hasDigits = true;
          } else {
            return finishDataInt(command, value, hasDigits);
          }
          break;

        case READING_DATA_CHAR:
          command.data.dataChar = c;
          return true;
      }
    }
    // The buffer ended without a terminator (the '\n' is stripped by poll(),
    // and the 50ms timeout path never has one).
    if (parseState == READING_DATA_INT) {
      return finishDataInt(command, value, hasDigits);
    }
    return true;
  }
}

void Transceiver::begin(long baud) {
  // Swap pins, since I'm using PA1, PA2, and PA4, which are secondary
  Serial.swap(1);
  // The megaTinyCore library natively supports RS-485, which removes the need
  // to manually set the DE pin high or low, as long as you're using the
  // default XDIR pin (which is PA4 after Serial.swap(1)).
  Serial.begin(baud, SERIAL_8N1 | SERIAL_RS485);
}

namespace {
  // Prints ":<value>". One call per field keeps dump() small.
  void printField(uint16_t value) {
    Serial.print(':');
    Serial.print(value);
  }
}

void Transceiver::dump(uint32_t revolutions, int16_t drift) {
  Serial.print("m");
  uint8_t id = EepromStore::getModuleId();
  if (id < 10) Serial.print("0");
  Serial.print(id);
  Serial.print("d");
  printField(EepromStore::getHomeOffset());
  printField(EepromStore::getTotalSteps());
  printField(EepromStore::getDebounceMs());
  printField(EepromStore::getStepDelay());
  printField(EepromStore::getHomingStepDelay());
  printField(EepromStore::isMotorClockwise());
  printField(EepromStore::autoHomeEnabled());
  printField(EepromStore::releaseMotorEnabled());
  printField(EepromStore::recalculateHome());
  printField(EepromStore::getRampStartDelay());
  printField(EepromStore::getRampSteps());
  printField(EepromStore::getSettleMs());
  printField(EepromStore::getStaggerMs());
  Serial.print(':');
  Serial.print(revolutions);
  Serial.print(':');
  Serial.println(drift);
}

const char* Transceiver::message() const { return buffer; }

bool Transceiver::parseBuffer(Command& command) {
  buffer[bufferLen] = '\0';  // for message()
  bool gotCommand = toCommand(command, buffer, bufferLen);
  bufferLen = 0;
  return gotCommand;
}

void Transceiver::checkFrameHeader() {
  // "m*F" then at least one digit then ':'
  if (bufferLen < 5 || buffer[0] != 'm' || buffer[1] != '*' || buffer[2] != 'F') return;
  uint16_t interval = 0;
  for (uint8_t i = 3; i < bufferLen - 1; i++) {
    if (!isDigit(buffer[i])) return;
    interval = interval * 10 + (buffer[i] - '0');
    if (interval > 255) return;
  }
  inFrame = true;
  framePos = 0;
  frameInterval = interval;
  frameHit = false;
}

bool Transceiver::frameByte(char c, Command& command) {
  if (c == '\n') {
    inFrame = false;
    buffer[bufferLen] = '\0';  // the header, for message()
    bufferLen = 0;
    if (!frameHit) return false;
    command.type = FRAME;
    command.broadcast = true;
    command.data.dataChar = frameChar;
    command.frameDelayMs = (uint16_t)frameRank * frameInterval;
    return true;
  }
  uint8_t id = EepromStore::getModuleId();
  if (id != EepromStore::UNPROVISIONED_ID && framePos / 2 == id) {
    if (framePos & 1) {
      frameRank = c > '!' ? c - '!' : 0;
      frameHit = true;
    } else {
      frameChar = c;
    }
  }
  if (framePos < 0xFFFF) framePos++;
  return false;
}

bool Transceiver::poll(Command& command) {
  uint32_t safety = millis();
  while (Serial.available() > 0) {
    char c = Serial.read();
    lastSerialTime = millis();
    if (inFrame) {
      if (frameByte(c, command)) return true;
      continue;
    }
    // Command is complete
    if (c == '\n') return parseBuffer(command);
    if (bufferLen < BUFFER_SIZE - 1) {
      buffer[bufferLen++] = c;
      if (c == ':') checkFrameHeader();
    }

    if (lastSerialTime - safety > 500) {
      bufferLen = 0;
      inFrame = false;
      return false;
    }
  }

  // Timeout: if we're mid-command and no byte has arrived in 50ms, treat
  // whatever is in the buffer as complete and return it. Handles messages
  // that don't have an explicit terminator or whose terminator was missed.
  if (bufferLen > 0 && millis() - lastSerialTime > 50) {
    if (inFrame) {
      // A frame that stalls is dropped rather than half-applied.
      inFrame = false;
      bufferLen = 0;
      return false;
    }
    return parseBuffer(command);
  }

  return false;
}

