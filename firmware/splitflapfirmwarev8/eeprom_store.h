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

  void saveAutoHome(bool enabled);
  bool autoHomeEnabled();
}

#endif
