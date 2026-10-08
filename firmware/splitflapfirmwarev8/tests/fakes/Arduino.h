// Stands in for megaTinyCore's Arduino.h when the firmware is built on the
// host for the tests: just the parts the firmware uses, wired to the fake
// hardware in fake_hardware.cpp (the clock, the bus, the pins, the reel).
#ifndef FAKE_ARDUINO_H
#define FAKE_ARDUINO_H

#include <stddef.h>
#include <stdint.h>

#include <string>

#define F_CPU 10000000UL
#define PROGMEM
#define pgm_read_byte(address) (*(const uint8_t*)(address))

// ---- Time ----
uint32_t millis();
uint32_t micros();

// ---- Pins ----
#define LOW 0
#define HIGH 1
#define INPUT 0
#define OUTPUT 1
#define INPUT_PULLUP 2

enum : uint8_t {
  PIN_PA1 = 1, PIN_PA2, PIN_PA4,
  PIN_PB2 = 10, PIN_PB3, PIN_PB4, PIN_PB5,
  PIN_PC0 = 20, PIN_PC1, PIN_PC2,
};

void pinMode(uint8_t pin, uint8_t mode);
uint8_t digitalRead(uint8_t pin);
void digitalWriteFast(uint8_t pin, uint8_t value);
void pinModeFast(uint8_t pin, uint8_t mode);

// The motor writes its coils straight to port B. Writing OUT tells the reel
// which coils are on (see FakeReel in fake_hardware.h).
struct FakePortOut {
  uint8_t value = 0;
  FakePortOut& operator=(uint8_t newValue);
  operator uint8_t() const { return value; }
};
struct FakeVPort {
  FakePortOut OUT;
  uint8_t DIR = 0;
};
extern FakeVPort VPORTB;

// ---- Registers written through _PROTECTED_WRITE ----
struct FakeWdt { uint8_t CTRLA = 0; };
struct FakeRstCtrl { uint8_t SWRR = 0; };
extern FakeWdt WDT;
extern FakeRstCtrl RSTCTRL;
#define WDT_PERIOD_2KCLK_gc 0x0A
#define RSTCTRL_SWRE_bm 0x01
void fakeProtectedWrite(uint8_t* reg, uint8_t value);
#define _PROTECTED_WRITE(reg, value) fakeProtectedWrite(&(reg), (value))

// ---- Characters ----
inline bool isDigit(char c) { return c >= '0' && c <= '9'; }

// ---- The RS-485 serial port ----
#define SERIAL_8N1 0x03
#define SERIAL_RS485 0x80

// Bytes the tests put on the bus are read from `rx`; whatever the module
// prints is collected in `tx`.
class FakeSerial {
 public:
  std::string rx;
  size_t rxPos = 0;
  std::string tx;

  void swap(uint8_t) {}
  void begin(long, uint16_t) {}
  int available() { return (int)(rx.size() - rxPos); }
  int read() { return rxPos < rx.size() ? (uint8_t)rx[rxPos++] : -1; }

  void print(char c) { tx += c; }
  void print(const char* s) { tx += s; }
  void print(unsigned char n) { tx += std::to_string(n); }
  void print(int n) { tx += std::to_string(n); }
  void print(unsigned int n) { tx += std::to_string(n); }
  void print(long n) { tx += std::to_string(n); }
  void print(unsigned long n) { tx += std::to_string(n); }
  void println() { tx += "\r\n"; }
  template <typename T> void println(T value) { print(value); println(); }
};
extern FakeSerial Serial;

#endif
