#ifndef EEPROM_STORE_H
#define EEPROM_STORE_H

#include <Arduino.h>

// ==============================================================================
// EepromStore — the module's persistent settings.
//
// Settings are cached in RAM: getters read the cache, and savers update both
// the cache and EEPROM.
// ==============================================================================

namespace EepromStore {
  // The module ID of a module that hasn't been given one yet. It isn't
  // addressable on its own, and doesn't answer broadcast dumps or frames.
  const uint8_t UNPROVISIONED_ID = 255;

  // Writes the defaults on first boot (with `hardcodedId` as the module ID),
  // then loads the settings into RAM.
  void begin(uint8_t hardcodedId);

  // True once EEPROM has been written with the magic value.
  bool isInitialized();

  // Force write the default values for every setting, with `hardcodedId` as
  // the module ID. Doesn't touch the revolution counter.
  void writeDefaults(uint8_t hardcodedId);

  void saveHomeOffset(uint16_t offset);
  uint16_t getHomeOffset();

  void saveTotalSteps(uint16_t steps);
  uint16_t getTotalSteps();

  void saveModuleId(uint8_t id);
  uint8_t getModuleId();

  // Time (µs) between motor steps during normal moves.
  void saveStepDelayUs(uint16_t delayUs);
  uint16_t getStepDelayUs();

  // Time (µs) between motor steps while homing and calibrating.
  void saveHomingStepDelayUs(uint16_t delayUs);
  uint16_t getHomingStepDelayUs();

  void saveDebounceMs(uint16_t ms);
  uint16_t getDebounceMs();

  void saveAutoHome(bool enabled);
  bool autoHomeEnabled();

  void saveMotorDir(bool clockwise);
  bool isMotorClockwise();

  void saveReleaseMotor(bool releaseMotor);
  bool releaseMotorEnabled();

  void saveRecalculateHome(bool recalculate);
  bool recalculateHome();

  // Step delay (µs) used at the start and end of a move. The delay ramps
  // between this and the step delay over rampSteps steps at each end.
  void saveRampStartDelayUs(uint16_t delayUs);
  uint16_t getRampStartDelayUs();

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

  // Lifetime count of reel revolutions, for maintenance. Read from and
  // written to EEPROM directly (not cached); SplitFlap keeps the live count
  // and saves it now and then.
  void saveRevolutions(uint32_t revolutions);
  uint32_t getRevolutions();
}

#endif
