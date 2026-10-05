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
}

#endif
