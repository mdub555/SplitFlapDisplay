#include "harness.h"

#include <Arduino.h>

#include <gtest/gtest.h>

namespace {
  // Simulated time each pass through loop() takes. Short against the step
  // delays (1000 µs by default), so a step is taken within this of being due.
  const uint32_t LOOP_US = 20;
}

namespace Module {
  void boot() {
    resetFakeHardware();
    FakeClock::resetForBoot();
    clearRam();
    runSetup();
  }

  void bootWithId(uint8_t id) {
    boot();
    send("m*@" + std::to_string(id));
    runMs(1);
    EXPECT_EQ(EepromStore::getModuleId(), id);
  }

  void sendRaw(const std::string& bytes) { Serial.rx += bytes; }

  void send(const std::string& message) { sendRaw(message + "\n"); }

  void runMs(uint32_t ms) {
    for (uint32_t elapsed = 0; elapsed < ms * 1000; elapsed += LOOP_US) {
      runLoop();
      FakeClock::advanceUs(LOOP_US);
    }
  }

  bool runUntilIdle(uint32_t maxMs) {
    for (uint32_t elapsed = 0; elapsed < maxMs * 1000; elapsed += LOOP_US) {
      runLoop();
      if (!splitFlap().busy() && Serial.available() == 0) return true;
      FakeClock::advanceUs(LOOP_US);
    }
    return false;
  }

  void sendAndSettle(const std::string& message) {
    send(message);
    EXPECT_TRUE(runUntilIdle());
  }

  std::string takeOutput() {
    std::string output = Serial.tx;
    Serial.tx.clear();
    return output;
  }

  void home() {
    sendAndSettle("m" + std::to_string(EepromStore::getModuleId()) + "h");
    EXPECT_EQ(splitFlap().currentFlapIndex(), 0);
    EXPECT_EQ(flapShowing(), 0);
  }

  int flapShowing() {
    uint16_t total = EepromStore::getTotalSteps();
    int32_t fromFlap0 = (int32_t)reel.stepsPastHome() - EepromStore::getHomeOffset();
    if (fromFlap0 < 0) fromFlap0 += reel.stepsPerRev;
    for (int flap = 0; flap < 64; flap++) {
      if ((uint32_t)flap * total / 64 == (uint32_t)fromFlap0) return flap;
    }
    return -1;
  }
}
