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

  CommandType toCommandType(char c) {
    switch (c) {
      case '-':
        return DISPLAY_CHAR;
      case '+':
        return DISPLAY_INDEX;
      case 'h':
        return HOME;
      case 'c':
        return CALIBRATE;
      case 'o':
        return SET_OFFSET;
      case 't':
        return SET_TOTAL_STEPS;
      case 's':
        return NUDGE;
      case 'g':
        return MOVE_TO_STEP;
      case 'i':
        return SET_MODULE_ID;
      case 'a':
        return SET_AUTO_HOME;
      case 'd':
        return DUMP_STATE;
      default:
        return UNKNOWN_COMMAND;
    }
  }

  bool toCommand(Command& command, const char* buffer, uint8_t bufferLen) {
    command.data.dataInt = 0;
    command.type = UNKNOWN_COMMAND;
    ParseState parseState = IDLE;
    uint8_t id = 0;
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
            parseState = READING_CMD;
            break;
          } else if (isDigit(c)) {
            id *= 10;
            id += c - '0';
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
            case DISPLAY_INDEX:
            case SET_OFFSET:
            case SET_TOTAL_STEPS:
            case NUDGE:
            case MOVE_TO_STEP:
            case SET_MODULE_ID:
            case SET_AUTO_HOME:
              parseState = READING_DATA_INT;
              break;
            case HOME:
            case CALIBRATE:
            case DUMP_STATE:
              return true;
            case UNKNOWN_COMMAND:
              return false;
          }
          break;

        // 'o','t','s','g','i','a','+' commands — accumulate digits, execute
        // on any non-digit terminator (typically '\n').
        case READING_DATA_INT:
          if (isDigit(c)) {
            command.data.dataInt *= 10;
            command.data.dataInt += c - '0';
          } else {
            return true;
          }
          break;

        case READING_DATA_CHAR:
          command.data.dataChar = c;
          return true;
      }
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

void Tranceiver::dump() {
  Serial.print("m");
  uint8_t id = EepromStore::getModuleId();
  if (id < 10) Serial.print("0");
  Serial.print(id);
  Serial.print("d:");
  Serial.print(EepromStore::getHomeOffset());
  Serial.print(":");
  Serial.println(EepromStore::getTotalSteps());
}

bool Tranceiver::poll(Command& command) {
  uint32_t safety = millis();
  while (Serial.available() > 0) {
    char c = Serial.read();
    lastSerialTime = millis();
    // Command is complete
    if (c == '\n') {
      buffer[bufferLen] = '\0';
      bool gotCommand = toCommand(command, buffer, bufferLen);
      bufferLen = 0;
      return gotCommand;
    }
    if (bufferLen < BUFFER_SIZE - 1) {
      buffer[bufferLen++] = c;
    }

    if (lastSerialTime - safety > 500) {
      bufferLen = 0;
      return false;
    }
  }

  // Timeout: if we're mid-command and no byte has arrived in 50ms, treat
  // whatever is in the buffer as complete and return it. Handles messages
  // that don't have an explicit terminator or whose terminator was missed.
  if (bufferLen > 0 && millis() - lastSerialTime > 50) {
    buffer[bufferLen] = '\0';
    bool gotCommand = toCommand(command, buffer, bufferLen);
    bufferLen = 0;
    return gotCommand;
  }

  return false;
}

