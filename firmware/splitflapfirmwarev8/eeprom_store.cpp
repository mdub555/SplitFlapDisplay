#include "eeprom_store.h"

#include <Arduino.h>
#include <EEPROM.h>

namespace {
  const uint16_t TOTAL_STEPS = 4096;
  const uint16_t NUM_FLAPS = 64;
  const uint16_t STEPS_PER_FLAP = TOTAL_STEPS/NUM_FLAPS;
  const uint16_t DEBOUNCE_MS = 100;
  // Ramp, settle and stagger defaults reproduce the behavior from before
  // they were configurable: no ramp, no settle, 150 ms per module ID.
  const uint8_t RAMP_START_DELAY = 3;
  const uint8_t RAMP_STEPS = 0;
  const uint8_t SETTLE_MS = 0;
  const uint8_t STAGGER_MS = 150;
  // With the wire-based home sensor, home is detected immediatly when the
  // blank flap is visible. Home is on the white flap, which is 7 flaps
  // from the black flap. Set the home 7.5 flaps past home, making each
  // flap right in the middle of their expected position.
  const uint16_t HOME_OFFSET = STEPS_PER_FLAP*7 + STEPS_PER_FLAP/2;
  const uint8_t MASK_AUTO_HOME = 1;
  const uint8_t MASK_MOTOR_CW = 1<<1;
  const uint8_t MASK_RELEASE_MOTOR = 1<<2;
  const uint8_t MASK_RECALCULATE_HOME = 1<<3;

  struct Config {
    uint16_t homeOffset = 0;   // Steps past magnet trigger to reach flap 0
    uint16_t totalSteps = 0;   // Total steps for one full reel revolution
    uint16_t debounceMs = 0;   // Debounce time for the home sensor
    uint8_t  moduleId = 0;     // This module's bus ID (0–254; 255 = unset)
    uint8_t  stepDelay = 1;    // The time between each motor step during normal rotation
    uint8_t  homingStepDelay = 1; // The time between each motor step during homing
    bool     autoHome = false; // Whether to home on every boot
    bool     motorClockwise = true; // Whether the motor defaults to rotating clockwise
    bool     releaseMotor = true;   // Whether the motor defaults to rotating clockwise
    bool     recalculateHome = true; // Whether home is recalculated each rotation
    uint8_t  rampStartDelay = 3; // Step delay (ms) at the start and end of a move
    uint8_t  rampSteps = 0;      // Steps to ramp between rampStartDelay and stepDelay
    uint8_t  settleMs = 0;       // Time to hold the coils after a move before releasing
    uint8_t  staggerMs = 150;    // Startup delay per module ID
  };

  // ---- EEPROM Address Map ----
  // Each of these is the previous address + sizeof(previous data type)
  const uint16_t ADDR_INIT        = 0;   // 1 byte  — Magic number to detect valid EEPROM data
  const uint16_t ADDR_HOME_OFFSET = 1;   // 2 bytes — Steps past magnet trigger to reach flap 0
  const uint16_t ADDR_TOTAL_STEPS = 3;   // 2 bytes — Total steps for one full reel revolution
  const uint16_t ADDR_MODULE_ID   = 5;   // 1 byte  — This module's bus ID (0–254; 255 = unset)
  const uint16_t ADDR_BOOLEANS    = 6;   // 1 byte  — boolean configs, see masks above
  const uint16_t ADDR_STEP_DELAY  = 7;   // 1 byte — ms delay between each motor step
  const uint16_t ADDR_HOMING_STEP_DELAY = 8;  // 1 byte — ms delay between each motor step
                                              // during homing
  const uint16_t ADDR_DEBOUNCE_MS = 9;  // 2 bytes — ms debounce timing for the home sensor
  const uint16_t ADDR_RAMP_START_DELAY = 11;  // 1 byte — ms step delay at the ends of a move
  const uint16_t ADDR_RAMP_STEPS  = 12;  // 1 byte — steps to ramp over at each end of a move
  const uint16_t ADDR_SETTLE_MS   = 13;  // 1 byte — ms to hold the coils before releasing
  const uint16_t ADDR_STAGGER_MS  = 14;  // 1 byte — ms startup delay per module ID
  const uint16_t ADDR_FLIP_COUNT  = 15;  // 4 bytes — reserved for the flip counter

  // Magic value written to ADDR_INIT to indicate EEPROM has been initialized.
  // Changing this value forces all modules to reset to defaults on next boot.
  const uint8_t INIT_VALUE = 0x06;

  Config config;

  void load() {
    EEPROM.get(ADDR_HOME_OFFSET, config.homeOffset);
    EEPROM.get(ADDR_TOTAL_STEPS, config.totalSteps);
    EEPROM.get(ADDR_DEBOUNCE_MS, config.debounceMs);
    config.moduleId = EEPROM.read(ADDR_MODULE_ID);
    config.stepDelay = EEPROM.read(ADDR_STEP_DELAY);
    config.homingStepDelay = EEPROM.read(ADDR_HOMING_STEP_DELAY);
    config.rampStartDelay = EEPROM.read(ADDR_RAMP_START_DELAY);
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
    uint8_t booleans =
      config.autoHome
      | config.motorClockwise<<1
      | config.releaseMotor<<2
      | config.recalculateHome<<3;
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
  saveDebounceMs(DEBOUNCE_MS);
  saveModuleId(hardcodedId);
  saveStepDelay(1);
  saveHomingStepDelay(1);
  saveAutoHome(false);
  saveMotorDir(/* clockwise= */ true);
  saveReleaseMotor(true);
  saveRecalculateHome(true);
  saveRampStartDelay(RAMP_START_DELAY);
  saveRampSteps(RAMP_STEPS);
  saveSettleMs(SETTLE_MS);
  saveStaggerMs(STAGGER_MS);
  EEPROM.put(ADDR_FLIP_COUNT, (uint32_t)0);
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

void saveStepDelay(uint8_t delay) {
  config.stepDelay = delay;
  EEPROM.write(ADDR_STEP_DELAY, delay);
}

uint8_t getStepDelay() {
  return config.stepDelay;
}

void saveHomingStepDelay(uint8_t delay) {
  config.homingStepDelay = delay;
  EEPROM.write(ADDR_HOMING_STEP_DELAY, delay);
}

uint8_t getHomingStepDelay() {
  return config.homingStepDelay;
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

void saveRampStartDelay(uint8_t delay) {
  config.rampStartDelay = delay;
  EEPROM.write(ADDR_RAMP_START_DELAY, delay);
}

uint8_t getRampStartDelay() { return config.rampStartDelay; }

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
}

