#include "fake_hardware.h"

#include <Arduino.h>
#include <EEPROM.h>

#include "../../pinout.h"

FakeSerial Serial;
FakeEeprom EEPROM;
FakeVPort VPORTB;
FakeWdt WDT;
FakeRstCtrl RSTCTRL;
FakeReel reel;
bool rebootRequested = false;

namespace FakePins {
  uint8_t statusLed = LOW;
}

// ---- Time ----

namespace {
  uint32_t clockUs = 0;
}

namespace FakeClock {
  void advanceUs(uint32_t us) { clockUs += us; }
  uint32_t nowUs() { return clockUs; }
  void resetForBoot() { clockUs = 0; }
}

uint32_t micros() { return clockUs; }
uint32_t millis() { return clockUs / 1000; }

// ---- Pins ----

void pinMode(uint8_t, uint8_t) {}
void pinModeFast(uint8_t, uint8_t) {}

uint8_t digitalRead(uint8_t pin) {
  // The home sensor pulls its pin low while the contact is closed.
  if (pin == HOME_PIN) return reel.homeContactClosed() ? LOW : HIGH;
  return HIGH;
}

void digitalWriteFast(uint8_t pin, uint8_t value) {
  if (pin == STATUS_LED) FakePins::statusLed = value ? HIGH : LOW;
}

void fakeProtectedWrite(uint8_t* reg, uint8_t value) {
  *reg = value;
  if (reg == &RSTCTRL.SWRR && value) rebootRequested = true;
}

// ---- The motor and reel ----

FakePortOut& FakePortOut::operator=(uint8_t newValue) {
  value = newValue;
  reel.coilsChanged((newValue >> 2) & 0x0F);  // the coils are on PB2-PB5
  return *this;
}

namespace {
  // The motor's half-step sequence (HALF_STEP_SEQUENCE in motor.cpp).
  const uint8_t SEQUENCE[8] = {0b0001, 0b0011, 0b0010, 0b0110, 0b0100, 0b1100, 0b1000, 0b1001};
}

void FakeReel::coilsChanged(uint8_t coils) {
  energized = coils != 0;
  if (!energized) return;
  int8_t newPhase = -1;
  for (int8_t i = 0; i < 8; i++) {
    if (SEQUENCE[i] == coils) newPhase = i;
  }
  if (newPhase < 0) return;  // not a pattern the motor uses
  // The motor steps clockwise by walking the sequence backward.
  uint8_t change = (newPhase - phase) & 7;
  if (change == 7) move(forwardWhenClockwise ? 1 : -1);
  if (change == 1) move(forwardWhenClockwise ? -1 : 1);
  phase = newPhase;
}

void FakeReel::move(int8_t direction) {
  if (stepsToMiss > 0) {
    stepsToMiss--;
    return;
  }
  if (direction > 0) {
    forwardSteps++;
    position = position + 1 == stepsPerRev ? 0 : position + 1;
  } else {
    backwardSteps++;
    position = position == 0 ? stepsPerRev - 1 : position - 1;
  }
  stepTimesUs.push_back(micros());
}

void resetFakeHardware() {
  Serial = FakeSerial();
  VPORTB = FakeVPort();
  rebootRequested = false;
  FakePins::statusLed = LOW;
}
