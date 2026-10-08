// The module as a whole: dumps, saved settings, start-up, the status LED.
#include <Arduino.h>
#include <EEPROM.h>

#include "harness.h"
#include "test.h"

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

TEST(a_dump_reports_every_setting_with_its_letter) {
  bootWithId(5);
  sendAndSettle("m5?");
  runMs(1);
  CHECK_EQ(takeOutput(),
           std::string("m05?\tO480\tT4096\tD100\tS1000\tH1000\tC1\tA0\tF1\tE1\tR3000\tL0\tW0\tP150\t#0\t~0\r\n"));
}

TEST(a_dump_while_busy_waits_until_the_module_is_idle) {
  bootWithId(5);
  reel.stepsPerRev = 4000;
  send("m5c");
  send("m5?");
  runMs(1000);
  CHECK_EQ(takeOutput(), std::string(""));
  CHECK(runUntilIdle());
  runMs(1);
  std::string dump = takeOutput();
  CHECK(dump.find("\tT4000\t") != std::string::npos);  // the calibration's result
}

TEST(a_broadcast_dump_is_answered_in_this_modules_slot) {
  bootWithId(3);
  send("m*?");
  runMs(310);  // module 3 answers 3 x 105 ms after the request
  CHECK_EQ(takeOutput(), std::string(""));
  runMs(10);
  CHECK(takeOutput().rfind("m03?\t", 0) == 0);
}

TEST(an_unprovisioned_module_only_answers_a_dump_addressed_to_it) {
  boot();
  sendAndSettle("m*?");
  runMs(30000);
  CHECK_EQ(takeOutput(), std::string(""));
  sendAndSettle("m255?");
  runMs(1);
  CHECK(takeOutput().rfind("m255?\t", 0) == 0);
}

TEST(the_dump_reports_revolutions_and_drift) {
  bootWithId(5);
  home();
  reel.stepsToMiss = 3;
  sendAndSettle("m5+32");
  sendAndSettle("m5+0");
  sendAndSettle("m5?");
  runMs(1);
  std::string dump = takeOutput();
  CHECK(dump.find("\t#2\t~3\r\n") != std::string::npos);
}

// ---- Saved settings ----

TEST(the_first_boot_saves_the_defaults) {
  boot();
  CHECK_EQ(EepromStore::getModuleId(), EepromStore::UNPROVISIONED_ID);
  CHECK_EQ(EepromStore::getTotalSteps(), (uint16_t)4096);
  CHECK(EepromStore::isInitialized());
}

TEST(settings_survive_a_power_cycle) {
  bootWithId(5);
  sendAndSettle("m5S1500");
  sendAndSettle("m5P20");
  boot();
  CHECK_EQ(EepromStore::getModuleId(), (uint8_t)5);
  CHECK_EQ(EepromStore::getStepDelayUs(), (uint16_t)1500);
  CHECK_EQ(EepromStore::getStaggerMs(), (uint8_t)20);
}

TEST(saving_writes_only_the_bytes_that_change) {
  bootWithId(5);
  uint32_t before = EEPROM.writes;
  sendAndSettle("m5S1000");  // the value it already has
  CHECK_EQ(EEPROM.writes, before);
  sendAndSettle("m5S1001");  // one byte of the two differs
  CHECK_EQ(EEPROM.writes, before + 1);
}

TEST(a_settings_reset_keeps_the_id_and_revolutions_then_reboots) {
  bootWithId(5);
  home();
  runMs(1);
  sendAndSettle("m5S1500");
  EepromStore::saveRevolutions(40);
  sendAndSettle("m5!");
  CHECK(rebootRequested);
  boot();
  CHECK_EQ(EepromStore::getModuleId(), (uint8_t)5);
  CHECK_EQ(EepromStore::getStepDelayUs(), (uint16_t)1000);
  CHECK_EQ(EepromStore::getRevolutions(), 40u);
}

TEST(reboot_resets_the_module) {
  bootWithId(5);
  sendAndSettle("m5r");
  CHECK(rebootRequested);
}

// ---- Start-up ----

TEST(auto_home_waits_for_the_modules_stagger) {
  bootWithId(5);
  sendAndSettle("m5A1");
  sendAndSettle("m5P100");  // 5 x 100 ms
  boot();
  runMs(490);
  CHECK_EQ(reel.forwardSteps, 0u);
  runMs(20);
  CHECK(reel.forwardSteps > 0);
  CHECK(runUntilIdle());
  CHECK_EQ(flapShowing(), 0);
}

TEST(a_move_during_the_stagger_starts_straight_away) {
  bootWithId(5);
  sendAndSettle("m5A1");
  sendAndSettle("m5P100");
  boot();
  send("m5+2");
  runMs(100);
  CHECK(reel.forwardSteps > 50);
  CHECK(runUntilIdle());
  CHECK_EQ(flapShowing(), 2);
}

// ---- The status LED ----

TEST(the_led_is_off_when_idle_and_on_while_homing) {
  bootWithId(5);
  runMs(10);
  CHECK_EQ(FakePins::statusLed, (uint8_t)LOW);
  send("m5h");
  runMs(100);
  CHECK_EQ(FakePins::statusLed, (uint8_t)HIGH);
  CHECK(runUntilIdle());
  runMs(1);
  CHECK_EQ(FakePins::statusLed, (uint8_t)LOW);
}

TEST(the_led_blinks_slowly_while_unprovisioned) {
  boot();
  CHECK_EQ(ledToggles(4200), 8);  // 1 Hz: a toggle every 512 ms
}

TEST(the_led_blinks_after_a_failed_home) {
  bootWithId(5);
  reel.sensorConnected = false;
  sendAndSettle("m5h");
  CHECK_EQ(ledToggles(1024), 8);  // 4 Hz
}

TEST(identify_blinks_the_led_quickly_for_10_seconds) {
  bootWithId(5);
  sendAndSettle("m5b");
  CHECK_EQ(ledToggles(1024), 16);  // 8 Hz
  runMs(9000);
  CHECK_EQ(ledToggles(1000), 0);
}
