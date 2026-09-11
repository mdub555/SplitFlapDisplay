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
#include <SoftwareSerial.h>

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
SoftwareSerial debugSerial(255, DEBUG_PIN);  // no RX needed; TX on pin 5 (PB4)
SplitFlap splitFlap(&debugSerial);
Command command;

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
  if (tranceiver.poll(command)) {
    switch (command.type) {
      case DISPLAY_CHAR:
        debugSerial.print("Display char: ");
        debugSerial.println(command.data.dataChar);
        splitFlap.moveToChar(command.data.dataChar);
        break;

      case DISPLAY_INDEX:
        debugSerial.print("Display index: ");
        debugSerial.println(command.data.dataInt);
        splitFlap.moveToIndex(command.data.dataInt);
        break;

      case HOME:
        debugSerial.println("Home");
        splitFlap.home();
        break;

      case CALIBRATE:
        debugSerial.println("Calibrate");
        splitFlap.calibrate();
        break;

      case SET_OFFSET:
        debugSerial.print("Set offset: ");
        debugSerial.println(command.data.dataInt);
        EepromStore::saveHomeOffset(command.data.dataInt);
        break;

      case SET_TOTAL_STEPS:
        debugSerial.print("Set total steps: ");
        debugSerial.println(command.data.dataInt);
        EepromStore::saveTotalSteps(command.data.dataInt);
        break;

      case NUDGE:
        debugSerial.print("Nudge: ");
        debugSerial.println(command.data.dataInt);
        break;

      case MOVE_TO_STEP:
        debugSerial.print("Move to step: ");
        debugSerial.println(command.data.dataInt);
        splitFlap.goToRawStep(command.data.dataInt);
        break;

      case SET_MODULE_ID:
        debugSerial.print("Set ID: ");
        debugSerial.println(command.data.dataInt);
        EepromStore::saveModuleId(command.data.dataInt);
        break;

      case SET_AUTO_HOME:
        debugSerial.print("Set Auto Home: ");
        debugSerial.println(command.data.dataInt);
        EepromStore::saveAutoHome(command.data.dataInt);
        break;

      case DUMP_STATE:
        debugSerial.println("Dump");
        tranceiver.dump();
        break;

      default:
        debugSerial.println("Unknown command");
        break;
    }
  }
}

