// ==============================================================================
// Split-Flap Display Module Firmware
// ==============================================================================
// Each ATTiny runs this firmware to control one character cell of a split-flap
// display. The cell is driven by a 28BYJ-48 stepper motor which rotates a reel
// of physical flaps past a viewing window. Two wires detect the home flap when
// a strip of aluminum tape on the home flap comes in contact with them.
//
// Multiple modules are wired together on an RS-485 serial bus and addressed by
// a unique numeric ID. A Raspberry Pi sends commands over the bus; each module
// listens for its own ID and responds accordingly. See tranceiver.h for the
// full message grammar and command reference.
//
// This file wires together all of the individual components and handles the
// controlling logic for incoming requests on the bus.
// ==============================================================================

#include <Arduino.h>

#include "debug_serial.h"
#include "eeprom_store.h"
#include "home_sensor.h"
#include "motor.h"
#include "pinout.h"
#include "splitflap.h"
#include "tranceiver.h"

// Default unset ID, to be updated via the frontend on installation.
// This is burned into EEPROM on first boot if no saved ID exists.
const uint8_t HARDCODED_ID = 255;

const long RS485_BAUD = 9600;
const long DEBUG_BAUD = 19200;

Tranceiver tranceiver;
DebugSerial debugSerial(255, DEBUG_PIN);  // no RX needed; TX on pin 5 (PB4)
SplitFlap splitFlap(&debugSerial);
Command command;

// A dump requested while the module is busy (moving, homing, calibrating) is
// sent once it finishes, so a dump after a calibrate reports the result.
bool dumpPending = false;

// Start up the various components inside the module.
void setup() {
  pinMode(STATUS_LED, OUTPUT);
  EepromStore::begin(HARDCODED_ID);
  HomeSensor::begin();
  Motor::begin();
  tranceiver.begin(RS485_BAUD);
  debugSerial.begin(DEBUG_BAUD);
  splitFlap.begin();
}

void loop() {
  splitFlap.update();

  if (dumpPending && !splitFlap.busy()) {
    dumpPending = false;
    tranceiver.dump(splitFlap.lastDrift());
  }

  if (tranceiver.poll(command)) {
    // Log the message as received rather than a description per command,
    // which keeps the debug strings (and flash use) small.
    debugSerial.println(tranceiver.message());
    switch (command.type) {
      case DISPLAY_CHAR:
        splitFlap.moveToChar(command.data.dataChar);
        break;

      case DISPLAY_INDEX:
        splitFlap.moveToIndex(command.data.dataInt);
        break;

      case HOME:
        splitFlap.home();
        break;

      case CALIBRATE:
        splitFlap.calibrate();
        break;

      case SET_OFFSET:
        // 0 is a special case that means set the current position as the offset
        if (command.data.dataInt == 0) {
          EepromStore::saveHomeOffset(splitFlap.currentStepPosition());
        } else {
          EepromStore::saveHomeOffset(command.data.dataInt);
        }
        break;

      case SET_TOTAL_STEPS:
        EepromStore::saveTotalSteps(command.data.dataInt);
        break;

      case SET_DEBOUNCE_MS:
        EepromStore::saveDebounceMs(command.data.dataInt);
        break;

      case NUDGE:
        splitFlap.nudge(command.data.dataInt);
        break;

      case MOVE_TO_STEP:
        splitFlap.goToRawStep(command.data.dataInt);
        break;

      case SET_HOMING_STEP_DELAY:
        EepromStore::saveHomingStepDelay(command.data.dataInt);
        break;

      case SET_STEP_DELAY:
        EepromStore::saveStepDelay(command.data.dataInt);
        break;

      case SET_MODULE_ID:
        EepromStore::saveModuleId(command.data.dataInt);
        break;

      case SET_AUTO_HOME:
        EepromStore::saveAutoHome(command.data.dataInt);
        break;

      case SET_MOTOR_CW:
        EepromStore::saveMotorDir(/* clockwise= */ command.data.dataInt);
        break;

      case SET_MOTOR_RELEASE:
        EepromStore::saveReleaseMotor(command.data.dataInt);
        if (command.data.dataInt) {
          Motor::release();
        } else {
          Motor::tense();
        }
        break;

      case SET_RECALCULATE_HOME:
        EepromStore::saveRecalculateHome(command.data.dataInt);
        break;

      case DUMP_STATE:
        dumpPending = true;
        break;

      case STOP:
        splitFlap.stop();
        break;

      case SET_RAMP_START_DELAY:
        EepromStore::saveRampStartDelay(command.data.dataInt);
        break;

      case SET_RAMP_STEPS:
        EepromStore::saveRampSteps(command.data.dataInt);
        break;

      case SET_SETTLE_MS:
        EepromStore::saveSettleMs(command.data.dataInt);
        break;

      case SET_STAGGER_MS:
        EepromStore::saveStaggerMs(command.data.dataInt);
        break;

      default:
        break;
    }
  }
}

