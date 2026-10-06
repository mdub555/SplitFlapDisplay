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
#include <avr/wdt.h>

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

Tranceiver tranceiver;
DebugSerial debugSerial;  // TX only, on DEBUG_PIN at 19200 baud
SplitFlap splitFlap(&debugSerial);
Command command;

// A dump requested while the module is busy (moving, homing, calibrating) is
// sent once it finishes, so a dump after a calibrate reports the result.
// A broadcast dump is answered in this module's slot: ID x DUMP_SLOT_MS after
// the request, or after the module goes idle if it was busy, so every
// module's reply has the bus to itself. A slot fits a ~50-byte dump at 9600
// baud (about 52 ms) with room for the line turnaround and timing skew.
const uint8_t DUMP_SLOT_MS = 75;
bool dumpPending = false;
uint16_t dumpDelayMs = 0;  // wait before replying, once idle
uint32_t dumpAtMs = 0;     // millis() to reply at

// millis() when identify ('f') was received, and whether it's still going.
uint32_t identifyStartMs = 0;
bool identifying = false;
const uint16_t IDENTIFY_MS = 10000;

// The status LED, in order of priority:
//   fast blink (8 Hz)  identify was requested in the last 10 seconds
//   4 Hz blink         the last home or calibration failed (see lastError())
//   1 Hz blink         unprovisioned (ID 255)
//   solid              homing or calibrating
//   off                otherwise
void updateStatusLed() {
  uint16_t now = millis();  // the low bits are all the blink phases need
  bool on;
  if (identifying && millis() - identifyStartMs < IDENTIFY_MS) {
    on = now & 64;
  } else {
    identifying = false;
    if (splitFlap.lastError() != SPLITFLAP_OK) {
      on = now & 128;
    } else if (EepromStore::getModuleId() == 255) {
      on = now & 512;
    } else {
      on = splitFlap.isHoming();
    }
  }
  digitalWriteFast(STATUS_LED, on);
}

// Restarts the module, the same as a power cycle apart from the brief delay.
void reboot() {
  _PROTECTED_WRITE(RSTCTRL.SWRR, RSTCTRL_SWRE_bm);
}

// Start up the various components inside the module.
void setup() {
  pinMode(STATUS_LED, OUTPUT);
  EepromStore::begin(HARDCODED_ID);
  HomeSensor::begin();
  Motor::begin();
  tranceiver.begin(RS485_BAUD);
  debugSerial.begin();
  splitFlap.begin();
  // Watchdog: if loop() stops running for about 2 seconds (a hang), the
  // module resets itself. loop() feeds it every iteration.
  _PROTECTED_WRITE(WDT.CTRLA, WDT_PERIOD_2KCLK_gc);
}

void loop() {
  wdt_reset();
  splitFlap.update();
  updateStatusLed();

  if (dumpPending) {
    if (splitFlap.busy()) {
      dumpAtMs = millis() + dumpDelayMs;  // the wait starts once idle
    } else if ((int32_t)(millis() - dumpAtMs) >= 0) {
      dumpPending = false;
      tranceiver.dump(splitFlap.revolutionCount(), splitFlap.lastDrift());
    }
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

      case DUMP_STATE: {
        uint8_t id = EepromStore::getModuleId();
        if (command.broadcast && id == 255) break;
        dumpDelayMs = command.broadcast ? id * DUMP_SLOT_MS : 0;
        dumpAtMs = millis() + dumpDelayMs;
        dumpPending = true;
        break;
      }

      case STOP:
        splitFlap.stop();
        break;

      case IDENTIFY:
        identifying = true;
        identifyStartMs = millis();
        break;

      case REBOOT:
        reboot();
        break;

      case FRAME:
        splitFlap.moveToCharAfter(command.data.dataChar, command.frameDelayMs);
        break;

      case EXERCISE:
        splitFlap.exercise(command.data.dataInt);
        break;

      case RESET_SETTINGS:
        EepromStore::writeDefaults(EepromStore::getModuleId());
        // Settings like total steps change under the current position, so
        // start clean.
        reboot();
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

