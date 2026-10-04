#include "eeprom_store.h"

#include <Arduino.h>
#include <EEPROM.h>

namespace {
  const uint16_t TOTAL_STEPS = 4096;
  const uint16_t NUM_FLAPS = 64;
  const uint16_t STEPS_PER_FLAP = TOTAL_STEPS/NUM_FLAPS;
  // With the wire-based home sensor, home is detected immediatly when the
  // blank flap is visible. Home is on the white flap, which is 7 flaps
  // from the black flap. Set the home 7.5 flaps past home, making each
  // flap right in the middle of their expected position.
  const uint16_t HOME_OFFSET = STEPS_PER_FLAP*7 + STEPS_PER_FLAP/2;
  const uint8_t MASK_AUTO_HOME = 1;
  const uint8_t MASK_MOTOR_CW = 1<<1;
  const uint8_t MASK_RELEASE_MOTOR = 1<<2;

  struct Config {
    uint16_t homeOffset = 0;   // Steps past magnet trigger to reach flap 0
    uint16_t totalSteps = 0;   // Total steps for one full reel revolution
    uint8_t  moduleId = 0;     // This module's bus ID (0–254; 255 = unset)
    bool     autoHome = false; // Whether to home on every boot
    bool     motorClockwise = true; // Whether the motor defaults to rotating clockwise
    bool     releaseMotor = true;   // Whether the motor defaults to rotating clockwise
  };

  // ---- EEPROM Address Map ----
  // Each of these is the previous address + sizeof(previous data type)
  const uint16_t ADDR_INIT        = 0;   // 1 byte  — Magic number to detect valid EEPROM data
  const uint16_t ADDR_HOME_OFFSET = 1;   // 2 bytes — Steps past magnet trigger to reach flap 0
  const uint16_t ADDR_TOTAL_STEPS = 3;   // 2 bytes — Total steps for one full reel revolution
  const uint16_t ADDR_MODULE_ID   = 5;   // 1 byte  — This module's bus ID (0–254; 255 = unset)
  const uint16_t ADDR_BOOLEANS    = 6;   // 1 byte  — boolean configs, see masks above

  // Magic value written to ADDR_INIT to indicate EEPROM has been initialized.
  // Changing this value forces all modules to reset to defaults on next boot.
  const uint8_t INIT_VALUE = 0x04;

  Config config;

  void load() {
    EEPROM.get(ADDR_HOME_OFFSET, config.homeOffset);
    EEPROM.get(ADDR_TOTAL_STEPS, config.totalSteps);
    config.moduleId = EEPROM.read(ADDR_MODULE_ID);
    uint8_t booleans = EEPROM.read(ADDR_BOOLEANS);
    config.autoHome = booleans & MASK_AUTO_HOME;
    config.motorClockwise = booleans & MASK_MOTOR_CW;
    config.releaseMotor = booleans & MASK_RELEASE_MOTOR;
  }

  void saveBooleans() {
    uint8_t booleans =
      config.autoHome
      | config.motorClockwise<<1
      | config.releaseMotor<<2;
    EEPROM.write(ADDR_BOOLEANS, booleans);
  }
}

namespace EepromStore {
void begin(uint8_t hardcodedId) {
  if (!isInitialized()) {
    writeDefaults(hardcodedId);
  }
  load();
}

void writeDefaults(uint8_t hardcodedId) {
  EEPROM.write(ADDR_INIT, INIT_VALUE);
  saveHomeOffset(HOME_OFFSET);
  saveTotalSteps(TOTAL_STEPS);
  saveModuleId(hardcodedId);
  saveAutoHome(false);
  saveMotorDir(/* clockwise= */ true);
  saveReleaseMotor(true);
}

bool isInitialized() {
  return EEPROM.read(ADDR_INIT) == INIT_VALUE;
}

void saveHomeOffset(uint16_t offset) {
  config.homeOffset = offset;
  EEPROM.put(ADDR_HOME_OFFSET, offset);
}

uint16_t getHomeOffset() {
  return config.homeOffset;
}

void saveTotalSteps(uint16_t steps) {
  config.totalSteps = steps;
  EEPROM.put(ADDR_TOTAL_STEPS, steps);
}

uint16_t getTotalSteps() {
  return config.totalSteps;
}

void saveModuleId(uint8_t id) {
  config.moduleId = id;
  EEPROM.write(ADDR_MODULE_ID, id);
}

uint8_t getModuleId() {
  return config.moduleId;
}

void saveAutoHome(bool enabled) {
  config.autoHome = enabled;
  saveBooleans();
}

void saveMotorDir(bool clockwise) {
  config.motorClockwise = clockwise;
  saveBooleans();
}

void saveReleaseMotor(bool releaseMotor) {
  config.releaseMotor = releaseMotor;
  saveBooleans();
}

bool autoHomeEnabled() { return config.autoHome; }

bool isMotorClockwise() { return config.motorClockwise; }

bool releaseMotorEnabled() { return config.releaseMotor; }
}

