// Per-flap offsets: setting one with J, where flaps then land, and reading
// them back with %.
#include <Arduino.h>
#include <EEPROM.h>

#include <gtest/gtest.h>

#include "harness.h"

using namespace Module;

namespace {
  const uint16_t FLAP = 64;
  const uint16_t OFFSET = 480;

  // Where flap `flap` lands with no offset, in steps from where the home
  // contact starts.
  uint16_t evenPosition(int flap) { return (OFFSET + flap * FLAP) % 4096; }

  // The % reply with every flap's offset at 0 except those in `offsets`
  // (flap, stored value).
  std::string offsetDump(const std::string& id, std::initializer_list<std::pair<int, int>> offsets = {}) {
    std::string hex;
    for (int flap = 0; flap < 64; flap++) {
      int stored = 128;
      for (const auto& [f, value] : offsets) {
        if (f == flap) stored = value;
      }
      char digits[3];
      snprintf(digits, sizeof(digits), "%02X", stored);
      hex += digits;
    }
    return "m" + id + "%" + hex + "\r\n";
  }
}

TEST(FlapOffset, EveryFlapStartsWithNoOffset) {
  bootWithId(5);
  sendAndSettle("m5%");
  runMs(1);
  EXPECT_EQ(takeOutput(), offsetDump("05"));
}

TEST(FlapOffset, RaisingAnOffsetMovesForwardByTheDifference) {
  bootWithId(5);
  home();
  sendAndSettle("m5+5");
  uint32_t before = reel.forwardSteps;
  sendAndSettle("m5J131");  // +3 steps
  EXPECT_EQ(reel.forwardSteps - before, 3u);
  EXPECT_EQ(reel.position, evenPosition(5) + 3);
  EXPECT_EQ(splitFlap().currentFlapIndex(), 5);
}

TEST(FlapOffset, LoweringAnOffsetGoesNearlyARevolution) {
  bootWithId(5);
  home();
  sendAndSettle("m5+5");
  sendAndSettle("m5J131");
  uint32_t before = reel.forwardSteps;
  sendAndSettle("m5J126");  // from +3 to -2
  EXPECT_EQ(reel.forwardSteps - before, 4096u - 5);
  EXPECT_EQ(reel.position, evenPosition(5) - 2);
  EXPECT_EQ(splitFlap().currentFlapIndex(), 5);
  EXPECT_EQ(reel.backwardSteps, 0u);
}

TEST(FlapOffset, SettingTheSameOffsetAgainDoesNotMove) {
  bootWithId(5);
  home();
  sendAndSettle("m5+5");
  sendAndSettle("m5J131");
  uint32_t before = reel.forwardSteps;
  sendAndSettle("m5J131");
  EXPECT_EQ(reel.forwardSteps, before);
}

TEST(FlapOffset, MovesToAFlapUseItsOffset) {
  bootWithId(5);
  home();
  sendAndSettle("m5+5");
  sendAndSettle("m5J126");
  sendAndSettle("m5+6");
  EXPECT_EQ(reel.position, evenPosition(6));  // other flaps are unaffected
  sendAndSettle("m5-E");  // flap 5, by character
  EXPECT_EQ(reel.position, evenPosition(5) - 2);
  EXPECT_EQ(splitFlap().currentFlapIndex(), 5);
}

TEST(FlapOffset, AnOffsetCanPutAFlapPastEitherEndOfTheRevolution) {
  bootWithId(5);
  home();
  sendAndSettle("m5+1");
  sendAndSettle("m5J0");  // -128 steps: back past flap 0
  EXPECT_EQ(reel.position, evenPosition(1) - 128);
  EXPECT_EQ(splitFlap().currentFlapIndex(), 1);
  sendAndSettle("m5+63");
  sendAndSettle("m5J255");  // +127 steps: on past the end of the revolution
  EXPECT_EQ(reel.position, (evenPosition(63) + 127) % 4096);
  EXPECT_EQ(splitFlap().currentFlapIndex(), 63);
}

TEST(FlapOffset, AnOffsetIsAppliedAfterHomingFirst) {
  bootWithId(5);
  home();
  sendAndSettle("m5+5");
  sendAndSettle("m5J131");
  boot();  // the position is unknown again
  sendAndSettle("m5+5");
  EXPECT_EQ(reel.position, evenPosition(5) + 3);
  EXPECT_EQ(splitFlap().currentFlapIndex(), 5);
}

TEST(FlapOffset, IsIgnoredForFlap0) {
  bootWithId(5);
  home();
  sendAndSettle("m5J140");
  EXPECT_EQ(reel.position, OFFSET);
  sendAndSettle("m5%");
  runMs(1);
  EXPECT_EQ(takeOutput(), offsetDump("05"));
}

TEST(FlapOffset, IsIgnoredBetweenFlapsOrWhileThePositionIsUnknown) {
  bootWithId(5);
  sendAndSettle("m5J140");  // unknown: not homed yet
  home();
  sendAndSettle("m5+20");
  sendAndSettle("m5n3");  // between flaps
  sendAndSettle("m5J140");
  send("m5+30");
  runMs(10);
  sendAndSettle("m5J140");  // mid-move
  sendAndSettle("m5%");
  runMs(1);
  EXPECT_EQ(takeOutput(), offsetDump("05"));
}

TEST(FlapOffset, ANumberIsRequired) {
  bootWithId(5);
  home();
  sendAndSettle("m5+5");
  sendAndSettle("m5J");
  sendAndSettle("m5J256");
  EXPECT_EQ(reel.position, evenPosition(5));
  EXPECT_EQ(takeOutput(), "");  // and a bare J isn't a dump
}

TEST(FlapOffset, BroadcastsAreIgnored) {
  bootWithId(5);
  home();
  sendAndSettle("m5+5");
  sendAndSettle("m*J131");
  EXPECT_EQ(reel.position, evenPosition(5));
  sendAndSettle("m*%");
  runMs(1000);
  EXPECT_EQ(takeOutput(), "");
}

TEST(FlapOffset, TheDumpGivesEachFlapsStoredOffsetInHex) {
  bootWithId(5);
  home();
  sendAndSettle("m5+3");
  sendAndSettle("m5J125");
  sendAndSettle("m5+4");
  sendAndSettle("m5J131");
  sendAndSettle("m5+63");
  sendAndSettle("m5J10");
  sendAndSettle("m5%");
  runMs(1);
  EXPECT_EQ(takeOutput(), offsetDump("05", {{3, 0x7D}, {4, 0x83}, {63, 0x0A}}));
}

TEST(FlapOffset, TheDumpWaitsUntilTheModuleIsIdle) {
  bootWithId(5);
  home();
  send("m5+40");
  send("m5%");
  runMs(500);
  EXPECT_EQ(takeOutput(), "");
  ASSERT_TRUE(runUntilIdle());
  runMs(1);
  EXPECT_EQ(takeOutput(), offsetDump("05"));
}

TEST(FlapOffset, OffsetsSurviveAPowerCycle) {
  bootWithId(5);
  home();
  sendAndSettle("m5+5");
  sendAndSettle("m5J131");
  boot();
  sendAndSettle("m5%");
  runMs(1);
  EXPECT_EQ(takeOutput(), offsetDump("05", {{5, 131}}));
}

TEST(FlapOffset, ASettingsResetClearsThem) {
  bootWithId(5);
  home();
  sendAndSettle("m5+5");
  sendAndSettle("m5J131");
  sendAndSettle("m5!");
  boot();
  sendAndSettle("m5%");
  runMs(1);
  EXPECT_EQ(takeOutput(), offsetDump("05"));
}

TEST(FlapOffset, EepromFromTheFirmwareBeforeOffsetsIsResetToDefaults) {
  // EEPROM as the previous firmware left it (layout 0x08): its bytes past
  // the revolution count were never written, so read as 0xFF (+127 steps).
  boot();
  EEPROM.bytes[0] = 0x08;
  boot();
  sendAndSettle("m255%");
  runMs(1);
  EXPECT_EQ(takeOutput(), offsetDump("255"));
}
