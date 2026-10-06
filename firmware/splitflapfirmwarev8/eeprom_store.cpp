#include "eeprom_store.h"

#include <Arduino.h>
#include <EEPROM.h>

namespace {
  // ---- Defaults, written on first boot and by a settings reset ----
  const uint16_t DEFAULT_TOTAL_STEPS = 4096;
  const uint16_t STEPS_PER_FLAP = DEFAULT_TOTAL_STEPS / 64;  // 64 flaps on the reel
  // With the wire-based home sensor, home is detected immediatly when the
  // blank flap is visible. Home is on the white flap, which is 7 flaps
  // from the black flap. Set the home 7.5 flaps past home, making each
  // flap right in the middle of their expected position.
  const uint16_t DEFAULT_HOME_OFFSET = STEPS_PER_FLAP * 7 + STEPS_PER_FLAP / 2;
  const uint16_t DEFAULT_DEBOUNCE_MS = 100;
  const uint16_t DEFAULT_STEP_DELAY_US = 1000;
  const uint16_t DEFAULT_HOMING_STEP_DELAY_US = 1000;
  const bool DEFAULT_AUTO_HOME = false;
  const bool DEFAULT_MOTOR_CW = true;
  const bool DEFAULT_RELEASE_MOTOR = true;
  const bool DEFAULT_RECALCULATE_HOME = true;
  // Ramp, settle and stagger defaults reproduce the behavior from before
  // they were configurable: no ramp, no settle, 150 ms per module ID.
  const uint16_t DEFAULT_RAMP_START_DELAY_US = 3000;
  const uint8_t DEFAULT_RAMP_STEPS = 0;
  const uint8_t DEFAULT_SETTLE_MS = 0;
  const uint8_t DEFAULT_STAGGER_MS = 150;

  // The boolean settings share one byte, one bit each.
  const uint8_t MASK_AUTO_HOME = 1;
  const uint8_t MASK_MOTOR_CW = 1 << 1;
  const uint8_t MASK_RELEASE_MOTOR = 1 << 2;
  const uint8_t MASK_RECALCULATE_HOME = 1 << 3;

  // The RAM copy of every setting except the revolution count. Filled by
  // load(), so it holds nothing meaningful before begin().
  struct Config {
    uint16_t homeOffset;       // Steps past the home edge to reach flap 0
    uint16_t totalSteps;       // Total steps for one full reel revolution
    uint16_t debounceMs;       // Debounce time for the home sensor
    uint8_t  moduleId;         // This module's bus ID (0–254; 255 = unset)
    uint16_t stepDelayUs;      // The time between each motor step during normal rotation
    uint16_t homingStepDelayUs;  // The time between each motor step during homing
    bool     autoHome;         // Whether to home on every boot
    bool     motorClockwise;   // Whether the motor rotates clockwise
    bool     releaseMotor;     // Whether to release the coils when idle
    bool     recalculateHome;  // Whether home is recalculated each rotation
    uint16_t rampStartDelayUs; // Step delay at the start and end of a move
    uint8_t  rampSteps;        // Steps to ramp between rampStartDelayUs and stepDelayUs
    uint8_t  settleMs;         // Time to hold the coils after a move before releasing
    uint8_t  staggerMs;        // Startup delay per module ID
  };

  // ---- EEPROM Address Map ----
  // Each of these is the previous address + sizeof(previous data type)
  const uint16_t ADDR_INIT        = 0;   // 1 byte  — Magic number to detect valid EEPROM data
  const uint16_t ADDR_HOME_OFFSET = 1;   // 2 bytes — Steps past the home edge to reach flap 0
  const uint16_t ADDR_TOTAL_STEPS = 3;   // 2 bytes — Total steps for one full reel revolution
  const uint16_t ADDR_MODULE_ID   = 5;   // 1 byte  — This module's bus ID (0–254; 255 = unset)
  const uint16_t ADDR_BOOLEANS    = 6;   // 1 byte  — boolean configs, see masks above
  const uint16_t ADDR_STEP_DELAY_US = 7;  // 2 bytes — µs delay between each motor step
  const uint16_t ADDR_HOMING_STEP_DELAY_US = 9;  // 2 bytes — µs delay between each motor
                                                 // step during homing
  const uint16_t ADDR_DEBOUNCE_MS = 11;  // 2 bytes — ms debounce timing for the home sensor
  const uint16_t ADDR_RAMP_START_DELAY_US = 13;  // 2 bytes — µs step delay at the ends of a move
  const uint16_t ADDR_RAMP_STEPS  = 15;  // 1 byte — steps to ramp over at each end of a move
  const uint16_t ADDR_SETTLE_MS   = 16;  // 1 byte — ms to hold the coils before releasing
  const uint16_t ADDR_STAGGER_MS  = 17;  // 1 byte — ms startup delay per module ID
  const uint16_t ADDR_REVOLUTIONS = 18;  // 4 bytes — lifetime revolution count

  // Magic value written to ADDR_INIT to indicate EEPROM has been initialized.
  // Changing this value forces all modules to reset to defaults on next boot.
  // 0x07: the step delays changed from 1-byte ms to 2-byte µs.
  const uint8_t INIT_VALUE = 0x07;

  Config config;

  void load() {
    EEPROM.get(ADDR_HOME_OFFSET, config.homeOffset);
    EEPROM.get(ADDR_TOTAL_STEPS, config.totalSteps);
    EEPROM.get(ADDR_DEBOUNCE_MS, config.debounceMs);
    config.moduleId = EEPROM.read(ADDR_MODULE_ID);
    EEPROM.get(ADDR_STEP_DELAY_US, config.stepDelayUs);
    EEPROM.get(ADDR_HOMING_STEP_DELAY_US, config.homingStepDelayUs);
    EEPROM.get(ADDR_RAMP_START_DELAY_US, config.rampStartDelayUs);
    config.rampSteps = EEPROM.read(ADDR_RAMP_STEPS);
    config.settleMs = EEPROM.read(ADDR_SETTLE_MS);
    config.staggerMs = EEPROM.read(ADDR_STAGGER_MS);
    uint8_t booleans = EEPROM.read(ADDR_BOOLEANS);
    config.autoHome = booleans & MASK_AUTO_HOME;
    config.motorClockwise = booleans & MASK_MOTOR_CW;
    config.releaseMotor = booleans & MASK_RELEASE_MOTOR;
    config.recalculateHome = booleans & MASK_RECALCULATE_HOME;
  }

  void saveBooleans() {
    uint8_t booleans = 0;
    if (config.autoHome) booleans |= MASK_AUTO_HOME;
    if (config.motorClockwise) booleans |= MASK_MOTOR_CW;
    if (config.releaseMotor) booleans |= MASK_RELEASE_MOTOR;
    if (config.recalculateHome) booleans |= MASK_RECALCULATE_HOME;
    EEPROM.write(ADDR_BOOLEANS, booleans);
  }
}

namespace EepromStore {
void begin(uint8_t hardcodedId) {
  if (!isInitialized()) {
    writeDefaults(hardcodedId);
    // Only on first initialization: the counter survives a settings reset.
    saveRevolutions(0);
  }
  load();
}

void writeDefaults(uint8_t hardcodedId) {
  EEPROM.write(ADDR_INIT, INIT_VALUE);
  saveHomeOffset(DEFAULT_HOME_OFFSET);
  saveTotalSteps(DEFAULT_TOTAL_STEPS);
  saveDebounceMs(DEFAULT_DEBOUNCE_MS);
  saveModuleId(hardcodedId);
  saveStepDelayUs(DEFAULT_STEP_DELAY_US);
  saveHomingStepDelayUs(DEFAULT_HOMING_STEP_DELAY_US);
  saveAutoHome(DEFAULT_AUTO_HOME);
  saveMotorDir(DEFAULT_MOTOR_CW);
  saveReleaseMotor(DEFAULT_RELEASE_MOTOR);
  saveRecalculateHome(DEFAULT_RECALCULATE_HOME);
  saveRampStartDelayUs(DEFAULT_RAMP_START_DELAY_US);
  saveRampSteps(DEFAULT_RAMP_STEPS);
  saveSettleMs(DEFAULT_SETTLE_MS);
  saveStaggerMs(DEFAULT_STAGGER_MS);
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

void saveStepDelayUs(uint16_t delayUs) {
  config.stepDelayUs = delayUs;
  EEPROM.put(ADDR_STEP_DELAY_US, delayUs);
}

uint16_t getStepDelayUs() {
  return config.stepDelayUs;
}

void saveHomingStepDelayUs(uint16_t delayUs) {
  config.homingStepDelayUs = delayUs;
  EEPROM.put(ADDR_HOMING_STEP_DELAY_US, delayUs);
}

uint16_t getHomingStepDelayUs() {
  return config.homingStepDelayUs;
}

void saveDebounceMs(uint16_t millis) {
  config.debounceMs = millis;
  EEPROM.put(ADDR_DEBOUNCE_MS, millis);
}

uint16_t getDebounceMs() {
  return config.debounceMs;
}

void saveAutoHome(bool enabled) {
  config.autoHome = enabled;
  saveBooleans();
}

bool autoHomeEnabled() { return config.autoHome; }

void saveMotorDir(bool clockwise) {
  config.motorClockwise = clockwise;
  saveBooleans();
}

bool isMotorClockwise() { return config.motorClockwise; }

void saveReleaseMotor(bool releaseMotor) {
  config.releaseMotor = releaseMotor;
  saveBooleans();
}

bool releaseMotorEnabled() { return config.releaseMotor; }

void saveRecalculateHome(bool recalculate) {
  config.recalculateHome = recalculate;
  saveBooleans();
}

bool recalculateHome() { return config.recalculateHome; }

void saveRampStartDelayUs(uint16_t delayUs) {
  config.rampStartDelayUs = delayUs;
  EEPROM.put(ADDR_RAMP_START_DELAY_US, delayUs);
}

uint16_t getRampStartDelayUs() { return config.rampStartDelayUs; }

void saveRampSteps(uint8_t steps) {
  config.rampSteps = steps;
  EEPROM.write(ADDR_RAMP_STEPS, steps);
}

uint8_t getRampSteps() { return config.rampSteps; }

void saveSettleMs(uint8_t ms) {
  config.settleMs = ms;
  EEPROM.write(ADDR_SETTLE_MS, ms);
}

uint8_t getSettleMs() { return config.settleMs; }

void saveStaggerMs(uint8_t ms) {
  config.staggerMs = ms;
  EEPROM.write(ADDR_STAGGER_MS, ms);
}

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

