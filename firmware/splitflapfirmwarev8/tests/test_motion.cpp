// Homing, moving and calibrating: what the reel physically does for each
// command.
#include <Arduino.h>

#include "harness.h"
#include <gtest/gtest.h>

using namespace Module;

namespace {
  // Steps between flaps with the default 4096-step revolution.
  const uint16_t FLAP = 64;
  // The default home offset: flap 0 is this far past the home edge.
  const uint16_t OFFSET = 480;

  // The longest and shortest gap between the reel's steps from `from` on.
  uint32_t longestGap(size_t from, size_t to) {
    uint32_t longest = 0;
    for (size_t i = from + 1; i < to; i++) {
      uint32_t gap = reel.stepTimesUs[i] - reel.stepTimesUs[i - 1];
      if (gap > longest) longest = gap;
    }
    return longest;
  }
  uint32_t shortestGap(size_t from, size_t to) {
    uint32_t shortest = UINT32_MAX;
    for (size_t i = from + 1; i < to; i++) {
      uint32_t gap = reel.stepTimesUs[i] - reel.stepTimesUs[i - 1];
      if (gap < shortest) shortest = gap;
    }
    return shortest;
  }
}

TEST(Motion, HomingFindsTheEdgeThenAdvancesTheHomeOffset) {
  bootWithId(5);
  sendAndSettle("m5h");
  EXPECT_EQ(reel.position, OFFSET);
  EXPECT_EQ(splitFlap().currentFlapIndex(), 0);
  EXPECT_EQ(reel.backwardSteps, 0u);
  EXPECT_FALSE(reel.energized);  // released once idle (the default)
}

TEST(Motion, AMoveBeforeHomingHomesFirst) {
  bootWithId(5);
  sendAndSettle("m5-A");
  EXPECT_EQ(flapShowing(), 1);
  EXPECT_EQ(splitFlap().currentFlapIndex(), 1);
}

TEST(Motion, MovesOnlyGoForward) {
  bootWithId(5);
  home();
  uint32_t before = reel.forwardSteps;
  sendAndSettle("m5+10");
  EXPECT_EQ(flapShowing(), 10);
  EXPECT_EQ(reel.forwardSteps - before, 10u * FLAP);
  sendAndSettle("m5+5");
  EXPECT_EQ(flapShowing(), 5);
  EXPECT_EQ(reel.forwardSteps - before, 4096u + 5 * FLAP);
  EXPECT_EQ(reel.backwardSteps, 0u);
}

TEST(Motion, EachCharacterGoesToItsFlap) {
  bootWithId(5);
  home();
  const char* reel_chars = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789?!,.q:@#$&()+-*/=%dhwroygbp";
  for (int flap : {63, 1, 26, 36, 37}) {
    sendAndSettle(std::string("m5-") + reel_chars[flap]);
    EXPECT_EQ(flapShowing(), flap);
  }
}

TEST(Motion, ACharacterNotOnTheReelIsIgnored) {
  bootWithId(5);
  home();
  uint32_t before = reel.forwardSteps;
  sendAndSettle("m5-~");
  sendAndSettle("m5-a");
  sendAndSettle("m5+64");
  EXPECT_EQ(reel.forwardSteps, before);
  EXPECT_EQ(flapShowing(), 0);
}

TEST(Motion, ShowingTheFlapAlreadyShowingDoesNothing) {
  bootWithId(5);
  home();
  sendAndSettle("m5+3");
  uint32_t before = reel.forwardSteps;
  sendAndSettle("m5+3");
  EXPECT_EQ(reel.forwardSteps, before);
}

TEST(Motion, ANewTargetMidMoveTakesOver) {
  bootWithId(5);
  home();
  uint32_t before = reel.forwardSteps;
  send("m5+30");
  runMs(100);
  sendAndSettle("m5+2");
  EXPECT_EQ(flapShowing(), 2);
  EXPECT_EQ(reel.forwardSteps - before, 2u * FLAP);  // straight on, no detour
}

TEST(Motion, StopMidMoveKeepsTheStepPosition) {
  bootWithId(5);
  home();
  send("m5+30");
  runMs(100);
  sendAndSettle("m5x");
  EXPECT_EQ(splitFlap().currentFlapIndex(), FLAP_BETWEEN);
  EXPECT_EQ(splitFlap().currentStepPosition(), (uint16_t)(reel.position - OFFSET));
  uint32_t before = reel.forwardSteps;
  uint16_t stoppedAt = splitFlap().currentStepPosition();
  sendAndSettle("m5+2");
  EXPECT_EQ(flapShowing(), 2);
  EXPECT_EQ(reel.forwardSteps - before, 2u * FLAP - stoppedAt);  // no rehoming
}

TEST(Motion, StopWhileHomingLeavesThePositionUnknown) {
  bootWithId(5);
  send("m5h");
  runMs(100);
  sendAndSettle("m5x");
  EXPECT_EQ(splitFlap().currentFlapIndex(), FLAP_UNKNOWN);
  sendAndSettle("m5+1");  // has to home first
  EXPECT_EQ(flapShowing(), 1);
}

TEST(Motion, StopCancelsAQueuedFrameCharacter) {
  bootWithId(0);
  home();
  // Module 0 shows 'B' as rank 50: 50 x 10 ms after the frame.
  send("m*f10:BS");
  runMs(100);
  sendAndSettle("m0x");
  runMs(1000);
  EXPECT_EQ(flapShowing(), 0);
}

TEST(Motion, HomingWithoutASensorFailsAfterARevolutionAndAMargin) {
  bootWithId(5);
  reel.sensorConnected = false;
  sendAndSettle("m5h");
  EXPECT_EQ(splitFlap().lastError(), SPLITFLAP_HOME_NOT_FOUND);
  EXPECT_EQ(splitFlap().currentFlapIndex(), FLAP_UNKNOWN);
  EXPECT_EQ(reel.forwardSteps, 4096u + 500);
  // A move after a failed home tries homing again, and succeeds once the
  // sensor is back.
  reel.sensorConnected = true;
  sendAndSettle("m5+1");
  EXPECT_EQ(flapShowing(), 1);
  EXPECT_EQ(splitFlap().lastError(), SPLITFLAP_OK);
}

TEST(Motion, CalibrateMeasuresAndSavesTheRevolution) {
  bootWithId(5);
  reel.stepsPerRev = 4000;
  sendAndSettle("m5c");
  EXPECT_EQ(EepromStore::getTotalSteps(), 4000);
  EXPECT_EQ(splitFlap().lastError(), SPLITFLAP_OK);
  EXPECT_EQ(flapShowing(), 0);
  sendAndSettle("m5+32");
  EXPECT_EQ(reel.position, OFFSET + 2000);
}

TEST(Motion, CalibrateRejectsAnImplausibleRevolution) {
  bootWithId(5);
  reel.stepsPerRev = 3000;
  sendAndSettle("m5c");
  EXPECT_EQ(splitFlap().lastError(), SPLITFLAP_CALIBRATION_OUT_OF_RANGE);
  EXPECT_EQ(EepromStore::getTotalSteps(), 4096);
  EXPECT_EQ(splitFlap().currentFlapIndex(), FLAP_UNKNOWN);
}

TEST(Motion, Offset0MakesTheCurrentPositionFlap0) {
  bootWithId(5);
  home();
  sendAndSettle("m5n10");
  sendAndSettle("m5O0");
  EXPECT_EQ(EepromStore::getHomeOffset(), (uint16_t)(OFFSET + 10));
  EXPECT_EQ(splitFlap().currentFlapIndex(), 0);
  sendAndSettle("m5h");
  EXPECT_EQ(reel.position, OFFSET + 10);
}

TEST(Motion, Offset0IsIgnoredWhileThePositionIsUnknown) {
  bootWithId(5);
  sendAndSettle("m5O0");
  EXPECT_EQ(EepromStore::getHomeOffset(), OFFSET);
}

TEST(Motion, ANewHomeOffsetRehomesBeforeTheNextMove) {
  bootWithId(5);
  home();
  sendAndSettle("m5O500");
  EXPECT_EQ(splitFlap().currentFlapIndex(), FLAP_UNKNOWN);
  sendAndSettle("m5+2");
  EXPECT_EQ(reel.position, 500 + 2 * FLAP);
  EXPECT_EQ(splitFlap().currentFlapIndex(), 2);
}

TEST(Motion, ANewHomeOffsetWhileAdvancingTheOldOneHomesAgain) {
  bootWithId(5);
  send("m5h");
  // Run until the edge has been found and the offset is being advanced.
  for (int i = 0; i < 10000 && !(reel.position > 0 && reel.position < 100); i++) runMs(1);
  sendAndSettle("m5O300");
  EXPECT_EQ(reel.position, 300);
  EXPECT_EQ(splitFlap().currentFlapIndex(), 0);
}

TEST(Motion, NewTotalStepsMidMoveStopsAndForgetsThePosition) {
  bootWithId(5);
  home();
  send("m5+40");
  runMs(50);
  send("m5T4000");
  runMs(1);
  EXPECT_FALSE(splitFlap().busy());
  EXPECT_EQ(splitFlap().currentFlapIndex(), FLAP_UNKNOWN);
  EXPECT_EQ(EepromStore::getTotalSteps(), 4000);
}

TEST(Motion, GoToStepIsIgnoredUntilHomed) {
  bootWithId(5);
  sendAndSettle("m5g100");
  EXPECT_EQ(reel.forwardSteps, 0u);
  home();
  sendAndSettle("m5g100");
  EXPECT_EQ(reel.position, OFFSET + 100);
  EXPECT_EQ(splitFlap().currentFlapIndex(), FLAP_BETWEEN);
  EXPECT_EQ(splitFlap().currentStepPosition(), 100);
}

TEST(Motion, NudgeMovesForwardAndWrapsPastTheRevolution) {
  bootWithId(5);
  home();
  sendAndSettle("m5n4090");
  EXPECT_EQ(splitFlap().currentStepPosition(), 4090);
  sendAndSettle("m5n10");
  EXPECT_EQ(splitFlap().currentStepPosition(), 4);
  EXPECT_EQ(reel.position, OFFSET + 4);
  EXPECT_EQ(splitFlap().currentFlapIndex(), FLAP_BETWEEN);
}

TEST(Motion, NudgeWhileThePositionIsUnknownKeepsItUnknown) {
  bootWithId(5);
  sendAndSettle("m5n10");
  EXPECT_EQ(reel.forwardSteps, 10u);
  EXPECT_EQ(splitFlap().currentFlapIndex(), FLAP_UNKNOWN);
}

TEST(Motion, ExerciseStepsThroughEveryFlapAndEndsWhereItStarted) {
  bootWithId(5);
  home();
  uint32_t before = reel.forwardSteps;
  sendAndSettle("m5e1");
  EXPECT_EQ(reel.forwardSteps - before, 4096u);
  EXPECT_EQ(flapShowing(), 0);
}

TEST(Motion, AnyMotionCommandEndsAnExercise) {
  bootWithId(5);
  home();
  send("m5e3");
  runMs(1000);
  sendAndSettle("m5+20");
  EXPECT_EQ(flapShowing(), 20);
  EXPECT_TRUE(reel.forwardSteps < 2 * 4096u);
}

TEST(Motion, TheStepDelaySpacesTheSteps) {
  bootWithId(5);
  home();
  sendAndSettle("m*S2000");
  size_t from = reel.stepTimesUs.size();
  sendAndSettle("m5+1");
  size_t to = reel.stepTimesUs.size();
  EXPECT_EQ(to - from, (size_t)FLAP);
  EXPECT_TRUE(shortestGap(from, to) >= 2000);
  EXPECT_TRUE(longestGap(from, to) <= 2040);
}

TEST(Motion, TheHomingStepDelaySpacesHomingSteps) {
  bootWithId(5);
  sendAndSettle("m*H1500");
  send("m5h");
  runMs(300);
  size_t to = reel.stepTimesUs.size();
  EXPECT_TRUE(shortestGap(1, to) >= 1500);
  EXPECT_TRUE(longestGap(1, to) <= 1540);
}

TEST(Motion, TheRampSlowsBothEndsOfAMove) {
  bootWithId(5);
  home();
  sendAndSettle("m*R3000");
  sendAndSettle("m*L10");
  size_t from = reel.stepTimesUs.size();
  sendAndSettle("m5+2");
  size_t to = reel.stepTimesUs.size();
  const std::vector<uint32_t>& t = reel.stepTimesUs;
  EXPECT_TRUE(t[from + 1] - t[from] >= 2700);   // starts slow
  EXPECT_TRUE(t[to - 1] - t[to - 2] >= 2700);   // ends slow
  EXPECT_TRUE(longestGap(from + 20, to - 20) <= 1040);  // full speed in between
}

TEST(Motion, SettleHoldsTheCoilsBeforeReleasingThem) {
  bootWithId(5);
  home();
  sendAndSettle("m*W50");
  send("m5+1");
  for (int i = 0; i < 1000 && reel.position != OFFSET + FLAP; i++) runMs(1);
  runMs(40);
  EXPECT_TRUE(reel.energized);
  runMs(20);
  EXPECT_FALSE(reel.energized);
}

TEST(Motion, WithReleaseOffTheCoilsStayEnergized) {
  bootWithId(5);
  home();
  EXPECT_FALSE(reel.energized);
  sendAndSettle("m*F0");
  EXPECT_TRUE(reel.energized);  // turning release off energizes them straight away
  sendAndSettle("m5+1");
  EXPECT_TRUE(reel.energized);
  sendAndSettle("m*F1");
  EXPECT_FALSE(reel.energized);
}

TEST(Motion, TheDirectionSettingReversesTheMotor) {
  bootWithId(5);
  reel.forwardWhenClockwise = false;  // a motor wired the other way round
  send("m5h");
  runMs(200);
  EXPECT_TRUE(reel.backwardSteps > 0);
  sendAndSettle("m5x");
  sendAndSettle("m5C0");
  home();
}

TEST(Motion, RecalculatingHomeCorrectsMissedStepsAtTheEdge) {
  bootWithId(5);
  home();
  reel.stepsToMiss = 5;
  sendAndSettle("m5+32");
  EXPECT_EQ(reel.position, OFFSET + 32 * FLAP - 5);  // the motor stalled for 5 steps
  sendAndSettle("m5+0");  // crosses the home edge
  EXPECT_EQ(splitFlap().lastDrift(), 5);
  EXPECT_EQ(flapShowing(), 0);
}

TEST(Motion, WithoutRecalculatingHomeMissedStepsStayMissed) {
  bootWithId(5);
  home();
  sendAndSettle("m*E0");
  reel.stepsToMiss = 5;
  sendAndSettle("m5+32");
  sendAndSettle("m5+0");
  EXPECT_EQ(splitFlap().lastDrift(), 5);  // still measured
  EXPECT_EQ(reel.position, OFFSET - 5);
}

TEST(Motion, RevolutionsAreCountedAndSavedEvery16) {
  bootWithId(5);
  home();  // crosses the edge once
  send("m5e15");
  EXPECT_TRUE(runUntilIdle(120000));
  EXPECT_EQ(splitFlap().revolutionCount(), 16u);
  runMs(1);
  EXPECT_EQ(EepromStore::getRevolutions(), 16u);
  sendAndSettle("m5e1");
  runMs(1);
  EXPECT_EQ(EepromStore::getRevolutions(), 16u);  // not yet: 17
  boot();
  EXPECT_EQ(splitFlap().revolutionCount(), 16u);  // what was saved
}
