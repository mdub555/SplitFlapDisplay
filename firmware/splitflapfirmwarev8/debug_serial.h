#ifndef DEBUG_SERIAL_H
#define DEBUG_SERIAL_H

#include <Arduino.h>

// =============================================================================
// Debug output on DEBUG_PIN (see pinout.h).
//
// Set DEBUG_OUTPUT to 0 to compile all debug output out of the firmware. That
// drops the SoftwareSerial driver, number printing and every debug string,
// which frees roughly 2.5 KB of the ATtiny816's 8 KB of flash. The debug
// calls stay in the code; with DEBUG_OUTPUT 0 they compile to nothing.
// =============================================================================
#ifndef DEBUG_OUTPUT
#define DEBUG_OUTPUT 1
#endif

#if DEBUG_OUTPUT
#include <SoftwareSerial.h>
typedef SoftwareSerial DebugSerial;
#else
// Stands in for SoftwareSerial with the calls the firmware uses, all no-ops.
class DebugSerial {
 public:
  DebugSerial(uint8_t, uint8_t) {}
  void begin(long) {}
  template <typename T> void print(const T&) {}
  template <typename T> void println(const T&) {}
};
#endif

#endif
