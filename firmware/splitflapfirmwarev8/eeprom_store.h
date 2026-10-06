#ifndef EEPROM_STORE_H
#define EEPROM_STORE_H

#include <Arduino.h>

// ==============================================================================
// EepromStore — thin wrapper around EEPROM reads/writes.
// ==============================================================================

namespace EepromStore {
  void begin(uint8_t hardcodedId);
  // True once EEPROM has been written with the magic value.
  bool isInitialized();

  // Force write the default values.
  void writeDefaults(uint8_t hardcodedId);

  void saveHomeOffset(uint16_t offset);
  uint16_t getHomeOffset();

  void saveTotalSteps(uint16_t steps);
  uint16_t getTotalSteps();

  void saveModuleId(uint8_t id);
  uint8_t getModuleId();

  void saveStepDelay(uint8_t delay);
  uint8_t getStepDelay();

  void saveHomingStepDelay(uint8_t delay);
  uint8_t getHomingStepDelay();

  void saveDebounceMs(uint16_t millis);
  uint16_t getDebounceMs();

  void saveAutoHome(bool enabled);
  bool autoHomeEnabled();

  void saveMotorDir(bool clockwise);
  bool isMotorClockwise();

  void saveReleaseMotor(bool releaseMotor);
  bool releaseMotorEnabled();

  void saveRecalculateHome(bool recalculate);
  bool recalculateHome();

  // Step delay (ms) used at the start and end of a move. The delay ramps
  // between this and the step delay over rampSteps steps at each end.
  void saveRampStartDelay(uint8_t delay);
  uint8_t getRampStartDelay();

  // Number of steps to ramp over at each end of a move. 0 disables the ramp.
  void saveRampSteps(uint8_t steps);
  uint8_t getRampSteps();

  // Time (ms) to keep the coils energized after a move before releasing
  // them, so the flap stops swinging first. Only used when release is on.
  void saveSettleMs(uint8_t ms);
  uint8_t getSettleMs();

  // Startup delay (ms) per module ID, so a display's motors don't all start
  // homing at the same instant.
  void saveStaggerMs(uint8_t ms);
  uint8_t getStaggerMs();
}

#endif
