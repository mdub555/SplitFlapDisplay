// The module as a whole: dumps, saved settings, start-up, the status LED.
#include <Arduino.h>
#include <EEPROM.h>

#include "harness.h"
#include <gtest/gtest.h>

using namespace Module;

namespace {
  // A changing pin's transitions over `ms`, sampled every millisecond.
  int ledToggles(uint32_t ms) {
    int toggles = 0;
    uint8_t last = FakePins::statusLed;
    for (uint32_t i = 0; i < ms; i++) {
      runMs(1);
      if (FakePins::statusLed != last) toggles++;
      last = FakePins::statusLed;
    }
    return toggles;
  }
}

// ---- Dumps ----

TEST(Dump, ADumpReportsEverySettingWithItsLetter) {
  bootWithId(5);
  sendAndSettle("m5?");
  runMs(1);
  EXPECT_EQ(takeOutput(),
           std::string("m05?\tO480\tT4096\tD100\tS1000\tH1000\tC1\tA0\tF1\tE1\tR3000\tL0\tW0\tP150\t#0\t~0\r\n"));
}

TEST(Dump, ADumpWhileBusyWaitsUntilTheModuleIsIdle) {
  bootWithId(5);
  reel.stepsPerRev = 4000;
  send("m5c");
  send("m5?");
  runMs(1000);
  EXPECT_EQ(takeOutput(), std::string(""));
  EXPECT_TRUE(runUntilIdle());
  runMs(1);
  std::string dump = takeOutput();
  EXPECT_TRUE(dump.find("\tT4000\t") != std::string::npos);  // the calibration's result
}

TEST(Dump, ABroadcastDumpIsAnsweredInThisModulesSlot) {
  bootWithId(3);
  send("m*?");
  runMs(310);  // module 3 answers 3 x 105 ms after the request
  EXPECT_EQ(takeOutput(), std::string(""));
  runMs(10);
  EXPECT_TRUE(takeOutput().rfind("m03?\t", 0) == 0);
}

TEST(Dump, AnUnprovisionedModuleOnlyAnswersADumpAddressedToIt) {
  boot();
  sendAndSettle("m*?");
  runMs(30000);
  EXPECT_EQ(takeOutput(), std::string(""));
  sendAndSettle("m255?");
  runMs(1);
  EXPECT_TRUE(takeOutput().rfind("m255?\t", 0) == 0);
}

TEST(Dump, TheDumpReportsRevolutionsAndDrift) {
  bootWithId(5);
  home();
  reel.stepsToMiss = 3;
  sendAndSettle("m5+32");
  sendAndSettle("m5+0");
  sendAndSettle("m5?");
  runMs(1);
  std::string dump = takeOutput();
  EXPECT_TRUE(dump.find("\t#2\t~3\r\n") != std::string::npos);
}

// ---- Saved settings ----

TEST(Settings, TheFirstBootSavesTheDefaults) {
  boot();
  EXPECT_EQ(EepromStore::getModuleId(), EepromStore::UNPROVISIONED_ID);
  EXPECT_EQ(EepromStore::getTotalSteps(), 4096);
  EXPECT_TRUE(EepromStore::isInitialized());
}

TEST(Settings, SettingsSurviveAPowerCycle) {
  bootWithId(5);
  sendAndSettle("m5S1500");
  sendAndSettle("m5P20");
  boot();
  EXPECT_EQ(EepromStore::getModuleId(), 5);
  EXPECT_EQ(EepromStore::getStepDelayUs(), 1500);
  EXPECT_EQ(EepromStore::getStaggerMs(), 20);
}

TEST(Settings, SavingWritesOnlyTheBytesThatChange) {
  bootWithId(5);
  uint32_t before = EEPROM.writes;
  sendAndSettle("m5S1000");  // the value it already has
  EXPECT_EQ(EEPROM.writes, before);
  sendAndSettle("m5S1001");  // one byte of the two differs
  EXPECT_EQ(EEPROM.writes, before + 1);
}

TEST(Settings, ASettingsResetKeepsTheIdAndRevolutionsThenReboots) {
  bootWithId(5);
  home();
  runMs(1);
  sendAndSettle("m5S1500");
  EepromStore::saveRevolutions(40);
  sendAndSettle("m5!");
  EXPECT_TRUE(rebootRequested);
  boot();
  EXPECT_EQ(EepromStore::getModuleId(), 5);
  EXPECT_EQ(EepromStore::getStepDelayUs(), 1000);
  EXPECT_EQ(EepromStore::getRevolutions(), 40u);
}

TEST(Settings, ASettingsResetCutShortIsFinishedOnTheNextBoot) {
  bootWithId(5);
  sendAndSettle("m5S1500");
  EepromStore::saveRevolutions(40);
  EEPROM.writesBeforePowerCut = 1;  // the power goes part way through
  sendAndSettle("m5!");
  EEPROM.writesBeforePowerCut = UINT32_MAX;
  boot();
  EXPECT_EQ(EepromStore::getModuleId(), 5);
  EXPECT_EQ(EepromStore::getStepDelayUs(), 1000);
  EXPECT_EQ(EepromStore::getRevolutions(), 40u);
  EXPECT_TRUE(EepromStore::isInitialized());
}

TEST(Settings, AFirstBootCutShortIsFinishedOnTheNextBoot) {
  EEPROM.bytes[1 + 3 * 2] = 0x12;   // a step delay from whatever was there before
  EEPROM.writesBeforePowerCut = 6;  // the count, the reset mark, then one more
  boot();
  EEPROM.writesBeforePowerCut = UINT32_MAX;
  boot();
  EXPECT_TRUE(EepromStore::isInitialized());
  EXPECT_EQ(EepromStore::getModuleId(), EepromStore::UNPROVISIONED_ID);
  EXPECT_EQ(EepromStore::getStepDelayUs(), 1000);
  EXPECT_EQ(EepromStore::getRevolutions(), 0u);
}

TEST(Settings, RebootResetsTheModule) {
  bootWithId(5);
  sendAndSettle("m5r");
  EXPECT_TRUE(rebootRequested);
}

// ---- Start-up ----

TEST(Startup, AutoHomeWaitsForTheModulesStagger) {
  bootWithId(5);
  sendAndSettle("m5A1");
  sendAndSettle("m5P100");  // 5 x 100 ms
  boot();
  runMs(490);
  EXPECT_EQ(reel.forwardSteps, 0u);
  runMs(20);
  EXPECT_TRUE(reel.forwardSteps > 0);
  EXPECT_TRUE(runUntilIdle());
  EXPECT_EQ(flapShowing(), 0);
}

TEST(Startup, AMoveDuringTheStaggerStartsStraightAway) {
  bootWithId(5);
  sendAndSettle("m5A1");
  sendAndSettle("m5P100");
  boot();
  send("m5+2");
  runMs(100);
  EXPECT_TRUE(reel.forwardSteps > 50);
  EXPECT_TRUE(runUntilIdle());
  EXPECT_EQ(flapShowing(), 2);
}

// ---- The status LED ----

TEST(StatusLed, TheLedIsOffWhenIdleAndOnWhileHoming) {
  bootWithId(5);
  runMs(10);
  EXPECT_EQ(FakePins::statusLed, LOW);
  send("m5h");
  runMs(100);
  EXPECT_EQ(FakePins::statusLed, HIGH);
  EXPECT_TRUE(runUntilIdle());
  runMs(1);
  EXPECT_EQ(FakePins::statusLed, LOW);
}

TEST(StatusLed, TheLedBlinksSlowlyWhileUnprovisioned) {
  boot();
  EXPECT_EQ(ledToggles(4200), 8);  // 1 Hz: a toggle every 512 ms
}

TEST(StatusLed, TheLedBlinksAfterAFailedHome) {
  bootWithId(5);
  reel.sensorConnected = false;
  sendAndSettle("m5h");
  EXPECT_EQ(ledToggles(1024), 8);  // 4 Hz
}

TEST(StatusLed, IdentifyBlinksTheLedQuicklyFor10Seconds) {
  bootWithId(5);
  sendAndSettle("m5b");
  EXPECT_EQ(ledToggles(1024), 16);  // 8 Hz
  runMs(9000);
  EXPECT_EQ(ledToggles(1000), 0);
}
