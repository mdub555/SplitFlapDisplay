// Reading messages off the bus: addressing, data, and what's rejected.
#include <Arduino.h>

#include "harness.h"
#include <gtest/gtest.h>

using namespace Module;

TEST(Bus, AMessageForAnotherModuleIsIgnored) {
  bootWithId(5);
  sendAndSettle("m6h");
  sendAndSettle("m50h");
  EXPECT_EQ(reel.forwardSteps, 0u);
}

TEST(Bus, TheIdCanHaveLeadingZeros) {
  bootWithId(5);
  sendAndSettle("m005S1500");
  EXPECT_EQ(EepromStore::getStepDelayUs(), 1500);
}

TEST(Bus, AMessageWithoutAnIdIsIgnored) {
  bootWithId(0);
  sendAndSettle("mS1500");
  EXPECT_EQ(EepromStore::getStepDelayUs(), 1000);
}

TEST(Bus, AnIdAbove255DoesNotWrapOntoAModule) {
  bootWithId(5);
  sendAndSettle("m261S1500");  // 261 = 256 + 5
  EXPECT_EQ(EepromStore::getStepDelayUs(), 1000);
}

TEST(Bus, ABroadcastReachesEveryModule) {
  bootWithId(5);
  sendAndSettle("m*S1500");
  EXPECT_EQ(EepromStore::getStepDelayUs(), 1500);
}

TEST(Bus, BytesBeforeTheMAreSkipped) {
  bootWithId(5);
  sendAndSettle("\x01junk!m5S1500");
  EXPECT_EQ(EepromStore::getStepDelayUs(), 1500);
}

TEST(Bus, AnUnknownCommandIsIgnored) {
  bootWithId(5);
  sendAndSettle("m5Z12");
  sendAndSettle("m5S1500");  // and the next message still works
  EXPECT_EQ(EepromStore::getStepDelayUs(), 1500);
}

TEST(Bus, ANumberIsRequiredWhereOneIsExpected) {
  bootWithId(5);
  sendAndSettle("m5S");
  sendAndSettle("m5Sx");
  EXPECT_EQ(EepromStore::getStepDelayUs(), 1000);
}

TEST(Bus, NumbersOutOfRangeAreRejected) {
  bootWithId(5);
  sendAndSettle("m5S65536");  // over 16 bits
  sendAndSettle("m5S99999");
  sendAndSettle("m5S0");      // a step delay of 0
  sendAndSettle("m5T0");      // a revolution of 0 steps
  sendAndSettle("m5A2");      // not 0 or 1
  sendAndSettle("m5L256");    // over a byte
  sendAndSettle("m5O4096");   // not below total steps
  EXPECT_EQ(EepromStore::getStepDelayUs(), 1000);
  EXPECT_EQ(EepromStore::getTotalSteps(), 4096);
  EXPECT_EQ(EepromStore::autoHomeEnabled(), false);
  EXPECT_EQ(EepromStore::getRampSteps(), 0);
  EXPECT_EQ(EepromStore::getHomeOffset(), 480);
}

TEST(Bus, NumbersAtTheEndsOfTheirRangeAreAccepted) {
  bootWithId(5);
  sendAndSettle("m5S65535");
  sendAndSettle("m5L255");
  sendAndSettle("m5O4095");
  sendAndSettle("m5D0");
  EXPECT_EQ(EepromStore::getStepDelayUs(), 65535);
  EXPECT_EQ(EepromStore::getRampSteps(), 255);
  EXPECT_EQ(EepromStore::getHomeOffset(), 4095);
  EXPECT_EQ(EepromStore::getDebounceMs(), 0);
}

TEST(Bus, AMessageWithNoNewlineIsReadAfter50ms) {
  bootWithId(5);
  sendRaw("m5S1500");
  runMs(20);
  EXPECT_EQ(EepromStore::getStepDelayUs(), 1000);
  runMs(50);
  EXPECT_EQ(EepromStore::getStepDelayUs(), 1500);
}

TEST(Bus, ABroadcastIdChangeOnlyReachesUnprovisionedModules) {
  bootWithId(5);
  sendAndSettle("m*@7");
  EXPECT_EQ(EepromStore::getModuleId(), 5);
  sendAndSettle("m5@7");
  EXPECT_EQ(EepromStore::getModuleId(), 7);
}

// ---- Frames ----

TEST(Frame, AFrameGivesEachModuleItsCharacterAndRank) {
  bootWithId(2);
  home();
  // Modules 0, 1, 2 show A, B, C, as ranks 0, 1, 2 (sent as '!' + rank),
  // 10 ms apart: module 2 starts 20 ms after the frame.
  send("m*f10:A!B\"C#");
  runMs(15);
  EXPECT_EQ(reel.position, 480);
  runMs(10);
  EXPECT_TRUE(reel.position != 480);
  EXPECT_TRUE(runUntilIdle());
  EXPECT_EQ(flapShowing(), 3);
}

TEST(Frame, AFrameWithoutAPairForThisModuleIsIgnored) {
  bootWithId(5);
  home();
  sendAndSettle("m*f0:A!B!C!");
  runMs(100);
  EXPECT_EQ(flapShowing(), 0);
}

TEST(Frame, AFrameCanBeLongerThanTheReceiveBuffer) {
  bootWithId(40);
  home();
  std::string pairs;
  for (int id = 0; id < 40; id++) pairs += "A!";
  pairs += "Z!";  // module 40's pair is bytes 81 and 82
  sendAndSettle("m*f0:" + pairs);
  runMs(10);
  EXPECT_TRUE(runUntilIdle());
  EXPECT_EQ(flapShowing(), 26);
}

TEST(Frame, AFrameThatStallsIsDropped) {
  bootWithId(1);
  home();
  sendRaw("m*f0:A!B!");  // no newline
  runMs(200);
  EXPECT_EQ(flapShowing(), 0);
  sendAndSettle("m1+3");  // the bus works again afterwards
  EXPECT_EQ(flapShowing(), 3);
}
