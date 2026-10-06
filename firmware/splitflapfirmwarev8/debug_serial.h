#ifndef DEBUG_SERIAL_H
#define DEBUG_SERIAL_H

#include <Arduino.h>

// =============================================================================
// Debug output on DEBUG_PIN (see pinout.h).
//
// Set DEBUG_OUTPUT to 0 to compile all debug output out of the firmware. That
// drops the serial writer, number printing and every debug string, which
// frees roughly 750 bytes of flash. The debug calls stay in the code; with
// DEBUG_OUTPUT 0 they compile to nothing.
// =============================================================================
#ifndef DEBUG_OUTPUT
#define DEBUG_OUTPUT 1
#endif

#if DEBUG_OUTPUT
#include <util/delay.h>
#include "pinout.h"

// Transmit-only serial output on DEBUG_PIN at a fixed 19200 baud, 8N1.
// This replaces SoftwareSerial: the firmware never receives on the debug
// pin, but SoftwareSerial's receive interrupt handling, pin-change interrupt
// code and buffer were linked in regardless, about 1.2 KB of flash.
class DebugSerial : public Print {
 public:
  static const uint32_t BAUD = 19200;

  void begin() {
    digitalWriteFast(DEBUG_PIN, HIGH);  // idle high
    pinModeFast(DEBUG_PIN, OUTPUT);
  }

  // Sends one byte, start bit to stop bit, with interrupts off so the bit
  // timing holds (about 0.5 ms per byte, as with SoftwareSerial).
  size_t write(uint8_t byte) override {
    uint8_t sreg = SREG;
    cli();
    digitalWriteFast(DEBUG_PIN, LOW);  // start bit
    _delay_us(BIT_US);
    for (uint8_t i = 0; i < 8; i++) {
      digitalWriteFast(DEBUG_PIN, byte & 1);
      byte >>= 1;
      _delay_us(BIT_US);
    }
    digitalWriteFast(DEBUG_PIN, HIGH);  // stop bit
    _delay_us(BIT_US);
    SREG = sreg;
    return 1;
  }

  using Print::write;

 private:
  // One bit time, less a little for the loop and pin write around each delay.
  static constexpr double BIT_US = 1000000.0 / BAUD - 12.0 * 1000000.0 / F_CPU;
};
#else
// Stands in for the debug serial with the calls the firmware uses, all no-ops.
class DebugSerial {
 public:
  void begin() {}
  template <typename T> void print(const T&) {}
  template <typename T> void println(const T&) {}
};
#endif

#endif
