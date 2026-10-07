#include "eeprom_store.h"

#include <Arduino.h>
#include <EEPROM.h>

namespace {
  // Every setting except the revolution count. The whole struct is stored as
  // one block in EEPROM and kept in RAM: getters read the RAM copy, and each
  // saver updates it and writes the block back. EEPROM.put() only rewrites
  // the bytes that changed, so a save costs one byte's (or two's) write.
  struct Config {
    uint16_t homeOffset;         // Steps past the home edge to reach flap 0
    uint16_t totalSteps;         // Total steps for one full reel revolution
    uint16_t debounceMs;         // Debounce time for the home sensor
    uint16_t stepDelayUs;        // Time between motor steps during normal moves
    uint16_t homingStepDelayUs;  // Time between motor steps while homing
    uint16_t rampStartDelayUs;   // Step delay at the start and end of a move
    uint8_t  moduleId;           // This module's bus ID (0–254; 255 = unset)
    uint8_t  rampSteps;          // Steps to ramp between rampStartDelayUs and stepDelayUs
    uint8_t  settleMs;           // Time to hold the coils after a move before releasing
    uint8_t  staggerMs;          // Startup delay per module ID
    bool     autoHome;           // Whether to home on every boot
    bool     motorClockwise;     // Whether the motor rotates clockwise
    bool     releaseMotor;       // Whether to release the coils when idle
    bool     recalculateHome;    // Whether home is recalculated each rotation
  };

  const uint16_t DEFAULT_TOTAL_STEPS = 4096;
  const uint16_t STEPS_PER_FLAP = DEFAULT_TOTAL_STEPS / 64;  // 64 flaps on the reel

  // Written on first boot and by a settings reset (moduleId is filled in
  // by writeDefaults()).
  const Config DEFAULTS = {
    // With the wire-based home sensor, home is detected immediatly when the
    // blank flap is visible. Home is on the white flap, which is 7 flaps
    // from the black flap. Set the home 7.5 flaps past home, making each
    // flap right in the middle of their expected position.
    /* homeOffset */        STEPS_PER_FLAP * 7 + STEPS_PER_FLAP / 2,
    /* totalSteps */        DEFAULT_TOTAL_STEPS,
    /* debounceMs */        100,
    /* stepDelayUs */       1000,
    /* homingStepDelayUs */ 1000,
    // Ramp, settle and stagger defaults reproduce the behavior from before
    // they were configurable: no ramp, no settle, 150 ms per module ID.
    /* rampStartDelayUs */  3000,
    /* moduleId */          EepromStore::UNPROVISIONED_ID,
    /* rampSteps */         0,
    /* settleMs */          0,
    /* staggerMs */         150,
    /* autoHome */          false,
    /* motorClockwise */    true,
    /* releaseMotor */      true,
    /* recalculateHome */   true,
  };

  // ---- EEPROM Address Map ----
  const uint16_t ADDR_INIT        = 0;                     // 1 byte — magic number, see INIT_VALUE
  const uint16_t ADDR_CONFIG      = 1;                     // sizeof(Config) bytes — the settings
  const uint16_t ADDR_REVOLUTIONS = 1 + sizeof(Config);    // 4 bytes — lifetime revolution count

  // Magic value written to ADDR_INIT to indicate EEPROM has been initialized.
  // Changing this value forces all modules to reset to defaults on next boot,
  // so change it whenever Config changes.
  // 0x08: the settings are stored as one Config block.
  const uint8_t INIT_VALUE = 0x08;

  Config config;

  void save() {
    EEPROM.put(ADDR_CONFIG, config);
  }
}

namespace EepromStore {
void begin(uint8_t hardcodedId) {
  if (!isInitialized()) {
    writeDefaults(hardcodedId);
    // Only on first initialization: the counter survives a settings reset.
    saveRevolutions(0);
  }
  EEPROM.get(ADDR_CONFIG, config);
}

void writeDefaults(uint8_t hardcodedId) {
  config = DEFAULTS;
  config.moduleId = hardcodedId;
  save();
  // Last, so a power cut part way through leaves the module uninitialized
  // and it starts again from the defaults on the next boot.
  EEPROM.write(ADDR_INIT, INIT_VALUE);
}

bool isInitialized() {
  return EEPROM.read(ADDR_INIT) == INIT_VALUE;
}

void saveHomeOffset(uint16_t offset) { config.homeOffset = offset; save(); }
uint16_t getHomeOffset() { return config.homeOffset; }

void saveTotalSteps(uint16_t steps) { config.totalSteps = steps; save(); }
uint16_t getTotalSteps() { return config.totalSteps; }

void saveModuleId(uint8_t id) { config.moduleId = id; save(); }
uint8_t getModuleId() { return config.moduleId; }

void saveStepDelayUs(uint16_t delayUs) { config.stepDelayUs = delayUs; save(); }
uint16_t getStepDelayUs() { return config.stepDelayUs; }

void saveHomingStepDelayUs(uint16_t delayUs) { config.homingStepDelayUs = delayUs; save(); }
uint16_t getHomingStepDelayUs() { return config.homingStepDelayUs; }

void saveDebounceMs(uint16_t ms) { config.debounceMs = ms; save(); }
uint16_t getDebounceMs() { return config.debounceMs; }

void saveAutoHome(bool enabled) { config.autoHome = enabled; save(); }
bool autoHomeEnabled() { return config.autoHome; }

void saveMotorDir(bool clockwise) { config.motorClockwise = clockwise; save(); }
bool isMotorClockwise() { return config.motorClockwise; }

void saveReleaseMotor(bool releaseMotor) { config.releaseMotor = releaseMotor; save(); }
bool releaseMotorEnabled() { return config.releaseMotor; }

void saveRecalculateHome(bool recalculate) { config.recalculateHome = recalculate; save(); }
bool recalculateHome() { return config.recalculateHome; }

void saveRampStartDelayUs(uint16_t delayUs) { config.rampStartDelayUs = delayUs; save(); }
uint16_t getRampStartDelayUs() { return config.rampStartDelayUs; }

void saveRampSteps(uint8_t steps) { config.rampSteps = steps; save(); }
uint8_t getRampSteps() { return config.rampSteps; }

void saveSettleMs(uint8_t ms) { config.settleMs = ms; save(); }
uint8_t getSettleMs() { return config.settleMs; }

void saveStaggerMs(uint8_t ms) { config.staggerMs = ms; save(); }
uint8_t getStaggerMs() { return config.staggerMs; }

void saveRevolutions(uint32_t revolutions) {
  EEPROM.put(ADDR_REVOLUTIONS, revolutions);
}

uint32_t getRevolutions() {
  uint32_t revolutions;
  EEPROM.get(ADDR_REVOLUTIONS, revolutions);
  return revolutions;
}
}
