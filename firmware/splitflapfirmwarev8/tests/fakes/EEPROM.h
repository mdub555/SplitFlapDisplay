// Stands in for megaTinyCore's EEPROM library: the ATtiny816's 128 bytes,
// kept in memory, and erased (0xFF) like a new chip.
#ifndef FAKE_EEPROM_H
#define FAKE_EEPROM_H

#include <stdint.h>
#include <string.h>

#define EEPROM_SIZE 128

class FakeEeprom {
 public:
  uint8_t bytes[EEPROM_SIZE];
  uint32_t writes = 0;  // bytes actually written, as update() and put() skip unchanged ones
  // How many more bytes get written before the power is cut: later writes
  // are lost. Unlimited unless a test sets it.
  uint32_t writesBeforePowerCut = UINT32_MAX;

  FakeEeprom() { erase(); }
  void erase() { memset(bytes, 0xFF, sizeof(bytes)); }

  uint8_t read(int address) { return bytes[address]; }
  void write(int address, uint8_t value) {
    if (writesBeforePowerCut == 0) return;
    if (writesBeforePowerCut != UINT32_MAX) writesBeforePowerCut--;
    bytes[address] = value;
    writes++;
  }
  void update(int address, uint8_t value) {
    if (bytes[address] != value) write(address, value);
  }
  template <typename T> T& get(int address, T& value) {
    memcpy(&value, &bytes[address], sizeof(T));
    return value;
  }
  template <typename T> const T& put(int address, const T& value) {
    const uint8_t* source = (const uint8_t*)&value;
    for (size_t i = 0; i < sizeof(T); i++) update(address + i, source[i]);
    return value;
  }
};
extern FakeEeprom EEPROM;

#endif
