#include "tranceiver.h"

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

  __attribute__((noinline)) CommandType toCommandType(char c) {
    switch (c) {
      case '-': return DISPLAY_CHAR;
      case '+': return DISPLAY_INDEX;
      case 'h': return HOME;
      case 'c': return CALIBRATE;
      case 'o': return SET_OFFSET;
      case 't': return SET_TOTAL_STEPS;
      case 's': return NUDGE;
      case 'g': return MOVE_TO_STEP;
      case 'i': return SET_MODULE_ID;
      case 'a': return SET_AUTO_HOME;
      case 'd': return DUMP_STATE;
      case 'w': return SET_MOTOR_CW;
      case 'r': return SET_MOTOR_RELEASE;
      case 'j': return SET_RECALCULATE_HOME;
      case 'k': return SET_STEP_DELAY;
      case 'l': return SET_HOMING_STEP_DELAY;
      case 'b': return SET_DEBOUNCE_MS;
      case 'x': return STOP;
      case 'u': return SET_RAMP_START_DELAY;
      case 'n': return SET_RAMP_STEPS;
      case 'e': return SET_SETTLE_MS;
      case 'y': return SET_STAGGER_MS;
      case 'f': return IDENTIFY;
      case 'z': return REBOOT;
      case 'q': return RESET_SETTINGS;
      case 'v': return EXERCISE;
      default:  return UNKNOWN_COMMAND;
    }
  }

  // Accepted range for each numeric command's value, indexed by CommandType
  // (keep LIMITS in the same order as the enum). Checking ranges here, in one
  // place, is much smaller than a check in each setter in the .ino.
  enum Limit : uint8_t {
    ANY,            // 0-65535
    BOOLEAN,        // 0-1
    BYTE,           // 0-255
    DELAY,          // 1-255: 0 would remove the step delay entirely
    TOTAL_STEPS,    // 1-65535: 0 breaks the movement math
    BELOW_TOTAL,    // 0 to total steps - 1
  };
  const Limit LIMITS[] = {
    ANY,          // UNKNOWN_COMMAND
    ANY,          // DISPLAY_CHAR
    BYTE,         // DISPLAY_INDEX: moveToIndex() ignores indexes past the last flap
    ANY,          // HOME
    ANY,          // CALIBRATE
    BELOW_TOTAL,  // SET_OFFSET
    TOTAL_STEPS,  // SET_TOTAL_STEPS
    ANY,          // SET_DEBOUNCE_MS
    BELOW_TOTAL,  // NUDGE
    BELOW_TOTAL,  // MOVE_TO_STEP
    BYTE,         // SET_MODULE_ID
    BOOLEAN,      // SET_AUTO_HOME
    ANY,          // DUMP_STATE
    BOOLEAN,      // SET_MOTOR_CW
    BOOLEAN,      // SET_MOTOR_RELEASE
    BOOLEAN,      // SET_RECALCULATE_HOME
    DELAY,        // SET_STEP_DELAY
    DELAY,        // SET_HOMING_STEP_DELAY
    ANY,          // STOP
    DELAY,        // SET_RAMP_START_DELAY
    BYTE,         // SET_RAMP_STEPS
    BYTE,         // SET_SETTLE_MS
    BYTE,         // SET_STAGGER_MS
    ANY,          // IDENTIFY
    ANY,          // REBOOT
    ANY,          // RESET_SETTINGS
    BYTE,         // EXERCISE
    ANY,          // FRAME
  };
  static_assert(sizeof(LIMITS) == FRAME + 1,
                "LIMITS needs one entry per CommandType");

  // Finishes a numeric command, rejecting it if it had no digits (a truncated
  // "m05k" must not set a 0 ms delay) or its value is out of range.
  bool finishDataInt(Command& command, uint16_t value, bool hasDigits) {
    if (!hasDigits) return false;
    uint16_t total = EepromStore::getTotalSteps();
    uint16_t max = 0xFFFF;
    switch (LIMITS[command.type]) {
      case BOOLEAN:     max = 1; break;
      case DELAY:       if (value == 0) return false;  // fall through
      case BYTE:        max = 255; break;
      case TOTAL_STEPS: if (value == 0) return false; break;
      case BELOW_TOTAL: max = total - 1; break;
      case ANY:         break;
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
    bool broadcast = false;
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
            broadcast = true;
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

        case READING_CMD:
          command.type = toCommandType(c);
          switch (command.type) {
            case DISPLAY_CHAR:
              parseState = READING_DATA_CHAR;
              break;
            case SET_MODULE_ID:
              // A broadcast ID change would give every module the same ID, so
              // only an unprovisioned module accepts one.
              if (broadcast && EepromStore::getModuleId() != 255) {
                return false;
              }
              // fall through
            case DISPLAY_INDEX:
            case SET_OFFSET:
            case SET_TOTAL_STEPS:
            case SET_DEBOUNCE_MS:
            case NUDGE:
            case MOVE_TO_STEP:
            case SET_AUTO_HOME:
            case SET_MOTOR_CW:
            case SET_MOTOR_RELEASE:
            case SET_RECALCULATE_HOME:
            case SET_HOMING_STEP_DELAY:
            case SET_STEP_DELAY:
            case SET_RAMP_START_DELAY:
            case SET_RAMP_STEPS:
            case SET_SETTLE_MS:
            case SET_STAGGER_MS:
            case EXERCISE:
              parseState = READING_DATA_INT;
              break;
            case HOME:
            case CALIBRATE:
            case DUMP_STATE:
            case STOP:
            case IDENTIFY:
            case REBOOT:
            case RESET_SETTINGS:
              return true;
            case UNKNOWN_COMMAND:
            case FRAME:  // only reached through the frame header, never here
              return false;
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

void Tranceiver::begin(long baud) {
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

void Tranceiver::dump(uint32_t revolutions, int16_t drift) {
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

const char* Tranceiver::message() const { return buffer; }

void Tranceiver::checkFrameHeader() {
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

bool Tranceiver::frameByte(char c, Command& command) {
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
  if (id != 255 && framePos / 2 == id) {
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

bool Tranceiver::poll(Command& command) {
  uint32_t safety = millis();
  while (Serial.available() > 0) {
    char c = Serial.read();
    lastSerialTime = millis();
    if (inFrame) {
      if (frameByte(c, command)) return true;
      continue;
    }
    // Command is complete
    if (c == '\n') {
      buffer[bufferLen] = '\0';
      bool gotCommand = toCommand(command, buffer, bufferLen);
      bufferLen = 0;
      return gotCommand;
    }
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
    buffer[bufferLen] = '\0';
    bool gotCommand = toCommand(command, buffer, bufferLen);
    bufferLen = 0;
    return gotCommand;
  }

  return false;
}

