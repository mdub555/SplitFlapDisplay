#include "eeprom_store.h"

#include <Arduino.h>
#include <EEPROM.h>

namespace {
  struct Config {
    uint16_t homeOffset = 0;   // Steps past magnet trigger to reach flap 0
    uint16_t totalSteps = 0;   // Total steps for one full reel revolution
    uint8_t  moduleId = 0;     // This module's bus ID (0–254; 255 = unset)
    bool     autoHome = false; // Whether to home on every boot
  };

  // ---- EEPROM Address Map ----
  // Each of these is the previous address + sizeof(previous data type)
  const uint16_t ADDR_INIT        = 0;   // 1 byte  — Magic number to detect valid EEPROM data
  const uint16_t ADDR_HOME_OFFSET = 1;   // 2 bytes — Steps past magnet trigger to reach flap 0
  const uint16_t ADDR_TOTAL_STEPS = 3;   // 2 bytes — Total steps for one full reel revolution
  const uint16_t ADDR_MODULE_ID   = 5;   // 1 byte  — This module's bus ID (0–254; 255 = unset)
  const uint16_t ADDR_AUTO_HOME   = 6;   // 1 byte  — 1 = home on boot, 0 = restore saved position

  // Magic value written to ADDR_INIT to indicate EEPROM has been initialized.
  // Changing this value forces all modules to reset to defaults on next boot.
  const uint8_t INIT_VALUE = 0x1B;

  Config config;

  void load() {
    EEPROM.get(ADDR_HOME_OFFSET, config.homeOffset);
    EEPROM.get(ADDR_TOTAL_STEPS, config.totalSteps);
    config.moduleId = EEPROM.read(ADDR_MODULE_ID);
    config.autoHome = (EEPROM.read(ADDR_AUTO_HOME) == 1);
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
  // With the wire-based home sensor, home is detected immediatly when the
  // blank flap is visible. 32 steps is half way to the next flap, making
  // each flap right in the middle of their expected position.
  saveHomeOffset(32);
  saveTotalSteps(4096);
  saveModuleId(hardcodedId);
  saveAutoHome(true);
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
  EEPROM.write(ADDR_AUTO_HOME, enabled ? 1 : 0);
}

bool autoHomeEnabled() { return config.autoHome; }
}

