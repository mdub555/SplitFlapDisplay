// Homing, moving and calibrating: what the reel physically does for each
// command.
#include <Arduino.h>

#include "harness.h"
#include "test.h"

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

TEST(homing_finds_the_edge_then_advances_the_home_offset) {
  bootWithId(5);
  sendAndSettle("m5h");
  CHECK_EQ(reel.position, OFFSET);
  CHECK_EQ(splitFlap().currentFlapIndex(), (int8_t)0);
  CHECK_EQ(reel.backwardSteps, 0u);
  CHECK(!reel.energized);  // released once idle (the default)
}

TEST(a_move_before_homing_homes_first) {
  bootWithId(5);
  sendAndSettle("m5-A");
  CHECK_EQ(flapShowing(), 1);
  CHECK_EQ(splitFlap().currentFlapIndex(), (int8_t)1);
}

TEST(moves_only_go_forward) {
  bootWithId(5);
  home();
  uint32_t before = reel.forwardSteps;
  sendAndSettle("m5+10");
  CHECK_EQ(flapShowing(), 10);
  CHECK_EQ(reel.forwardSteps - before, 10u * FLAP);
  sendAndSettle("m5+5");
  CHECK_EQ(flapShowing(), 5);
  CHECK_EQ(reel.forwardSteps - before, 4096u + 5 * FLAP);
  CHECK_EQ(reel.backwardSteps, 0u);
}

TEST(each_character_goes_to_its_flap) {
  bootWithId(5);
  home();
  const char* reel_chars = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789?!,.q:@#$&()+-*/=%dhwroygbp";
  for (int flap : {63, 1, 26, 36, 37}) {
    sendAndSettle(std::string("m5-") + reel_chars[flap]);
    CHECK_EQ(flapShowing(), flap);
  }
}

TEST(a_character_not_on_the_reel_is_ignored) {
  bootWithId(5);
  home();
  uint32_t before = reel.forwardSteps;
  sendAndSettle("m5-~");
  sendAndSettle("m5-a");
  sendAndSettle("m5+64");
  CHECK_EQ(reel.forwardSteps, before);
  CHECK_EQ(flapShowing(), 0);
}

TEST(showing_the_flap_already_showing_does_nothing) {
  bootWithId(5);
  home();
  sendAndSettle("m5+3");
  uint32_t before = reel.forwardSteps;
  sendAndSettle("m5+3");
  CHECK_EQ(reel.forwardSteps, before);
}

TEST(a_new_target_mid_move_takes_over) {
  bootWithId(5);
  home();
  uint32_t before = reel.forwardSteps;
  send("m5+30");
  runMs(100);
  sendAndSettle("m5+2");
  CHECK_EQ(flapShowing(), 2);
  CHECK_EQ(reel.forwardSteps - before, 2u * FLAP);  // straight on, no detour
}

TEST(stop_mid_move_keeps_the_step_position) {
  bootWithId(5);
  home();
  send("m5+30");
  runMs(100);
  sendAndSettle("m5x");
  CHECK_EQ(splitFlap().currentFlapIndex(), FLAP_BETWEEN);
  CHECK_EQ(splitFlap().currentStepPosition(), (uint16_t)(reel.position - OFFSET));
  uint32_t before = reel.forwardSteps;
  uint16_t stoppedAt = splitFlap().currentStepPosition();
  sendAndSettle("m5+2");
  CHECK_EQ(flapShowing(), 2);
  CHECK_EQ(reel.forwardSteps - before, 2u * FLAP - stoppedAt);  // no rehoming
}

TEST(stop_while_homing_leaves_the_position_unknown) {
  bootWithId(5);
  send("m5h");
  runMs(100);
  sendAndSettle("m5x");
  CHECK_EQ(splitFlap().currentFlapIndex(), FLAP_UNKNOWN);
  sendAndSettle("m5+1");  // has to home first
  CHECK_EQ(flapShowing(), 1);
}

TEST(stop_cancels_a_queued_frame_character) {
  bootWithId(0);
  home();
  // Module 0 shows 'B' as rank 50: 50 x 10 ms after the frame.
  send("m*f10:BS");
  runMs(100);
  sendAndSettle("m0x");
  runMs(1000);
  CHECK_EQ(flapShowing(), 0);
}

TEST(homing_without_a_sensor_fails_after_a_revolution_and_a_margin) {
  bootWithId(5);
  reel.sensorConnected = false;
  sendAndSettle("m5h");
  CHECK_EQ(splitFlap().lastError(), SPLITFLAP_HOME_NOT_FOUND);
  CHECK_EQ(splitFlap().currentFlapIndex(), FLAP_UNKNOWN);
  CHECK_EQ(reel.forwardSteps, 4096u + 500);
  // A move after a failed home tries homing again, and succeeds once the
  // sensor is back.
  reel.sensorConnected = true;
  sendAndSettle("m5+1");
  CHECK_EQ(flapShowing(), 1);
  CHECK_EQ(splitFlap().lastError(), SPLITFLAP_OK);
}

TEST(calibrate_measures_and_saves_the_revolution) {
  bootWithId(5);
  reel.stepsPerRev = 4000;
  sendAndSettle("m5c");
  CHECK_EQ(EepromStore::getTotalSteps(), (uint16_t)4000);
  CHECK_EQ(splitFlap().lastError(), SPLITFLAP_OK);
  CHECK_EQ(flapShowing(), 0);
  sendAndSettle("m5+32");
  CHECK_EQ(reel.position, OFFSET + 2000);
}

TEST(calibrate_rejects_an_implausible_revolution) {
  bootWithId(5);
  reel.stepsPerRev = 3000;
  sendAndSettle("m5c");
  CHECK_EQ(splitFlap().lastError(), SPLITFLAP_CALIBRATION_OUT_OF_RANGE);
  CHECK_EQ(EepromStore::getTotalSteps(), (uint16_t)4096);
  CHECK_EQ(splitFlap().currentFlapIndex(), FLAP_UNKNOWN);
}

TEST(offset_0_makes_the_current_position_flap_0) {
  bootWithId(5);
  home();
  sendAndSettle("m5n10");
  sendAndSettle("m5O0");
  CHECK_EQ(EepromStore::getHomeOffset(), (uint16_t)(OFFSET + 10));
  CHECK_EQ(splitFlap().currentFlapIndex(), (int8_t)0);
  sendAndSettle("m5h");
  CHECK_EQ(reel.position, OFFSET + 10);
}

TEST(offset_0_is_ignored_while_the_position_is_unknown) {
  bootWithId(5);
  sendAndSettle("m5O0");
  CHECK_EQ(EepromStore::getHomeOffset(), OFFSET);
}

TEST(a_new_home_offset_rehomes_before_the_next_move) {
  bootWithId(5);
  home();
  sendAndSettle("m5O500");
  CHECK_EQ(splitFlap().currentFlapIndex(), FLAP_UNKNOWN);
  sendAndSettle("m5+2");
  CHECK_EQ(reel.position, 500 + 2 * FLAP);
  CHECK_EQ(splitFlap().currentFlapIndex(), (int8_t)2);
}

TEST(a_new_home_offset_while_advancing_the_old_one_homes_again) {
  bootWithId(5);
  send("m5h");
  // Run until the edge has been found and the offset is being advanced.
  for (int i = 0; i < 10000 && !(reel.position > 0 && reel.position < 100); i++) runMs(1);
  sendAndSettle("m5O300");
  CHECK_EQ(reel.position, 300);
  CHECK_EQ(splitFlap().currentFlapIndex(), (int8_t)0);
}

TEST(new_total_steps_mid_move_stops_and_forgets_the_position) {
  bootWithId(5);
  home();
  send("m5+40");
  runMs(50);
  send("m5T4000");
  runMs(1);
  CHECK(!splitFlap().busy());
  CHECK_EQ(splitFlap().currentFlapIndex(), FLAP_UNKNOWN);
  CHECK_EQ(EepromStore::getTotalSteps(), (uint16_t)4000);
}

TEST(go_to_step_is_ignored_until_homed) {
  bootWithId(5);
  sendAndSettle("m5g100");
  CHECK_EQ(reel.forwardSteps, 0u);
  home();
  sendAndSettle("m5g100");
  CHECK_EQ(reel.position, OFFSET + 100);
  CHECK_EQ(splitFlap().currentFlapIndex(), FLAP_BETWEEN);
  CHECK_EQ(splitFlap().currentStepPosition(), (uint16_t)100);
}

TEST(nudge_moves_forward_and_wraps_past_the_revolution) {
  bootWithId(5);
  home();
  sendAndSettle("m5n4090");
  CHECK_EQ(splitFlap().currentStepPosition(), (uint16_t)4090);
  sendAndSettle("m5n10");
  CHECK_EQ(splitFlap().currentStepPosition(), (uint16_t)4);
  CHECK_EQ(reel.position, OFFSET + 4);
  CHECK_EQ(splitFlap().currentFlapIndex(), FLAP_BETWEEN);
}

TEST(nudge_while_the_position_is_unknown_keeps_it_unknown) {
  bootWithId(5);
  sendAndSettle("m5n10");
  CHECK_EQ(reel.forwardSteps, 10u);
  CHECK_EQ(splitFlap().currentFlapIndex(), FLAP_UNKNOWN);
}

TEST(exercise_steps_through_every_flap_and_ends_where_it_started) {
  bootWithId(5);
  home();
  uint32_t before = reel.forwardSteps;
  sendAndSettle("m5e1");
  CHECK_EQ(reel.forwardSteps - before, 4096u);
  CHECK_EQ(flapShowing(), 0);
}

TEST(any_motion_command_ends_an_exercise) {
  bootWithId(5);
  home();
  send("m5e3");
  runMs(1000);
  sendAndSettle("m5+20");
  CHECK_EQ(flapShowing(), 20);
  CHECK(reel.forwardSteps < 2 * 4096u);
}

TEST(the_step_delay_spaces_the_steps) {
  bootWithId(5);
  home();
  sendAndSettle("m*S2000");
  size_t from = reel.stepTimesUs.size();
  sendAndSettle("m5+1");
  size_t to = reel.stepTimesUs.size();
  CHECK_EQ(to - from, (size_t)FLAP);
  CHECK(shortestGap(from, to) >= 2000);
  CHECK(longestGap(from, to) <= 2040);
}

TEST(the_homing_step_delay_spaces_homing_steps) {
  bootWithId(5);
  sendAndSettle("m*H1500");
  send("m5h");
  runMs(300);
  size_t to = reel.stepTimesUs.size();
  CHECK(shortestGap(1, to) >= 1500);
  CHECK(longestGap(1, to) <= 1540);
}

TEST(the_ramp_slows_both_ends_of_a_move) {
  bootWithId(5);
  home();
  sendAndSettle("m*R3000");
  sendAndSettle("m*L10");
  size_t from = reel.stepTimesUs.size();
  sendAndSettle("m5+2");
  size_t to = reel.stepTimesUs.size();
  const std::vector<uint32_t>& t = reel.stepTimesUs;
  CHECK(t[from + 1] - t[from] >= 2700);   // starts slow
  CHECK(t[to - 1] - t[to - 2] >= 2700);   // ends slow
  CHECK(longestGap(from + 20, to - 20) <= 1040);  // full speed in between
}

TEST(settle_holds_the_coils_before_releasing_them) {
  bootWithId(5);
  home();
  sendAndSettle("m*W50");
  send("m5+1");
  for (int i = 0; i < 1000 && reel.position != OFFSET + FLAP; i++) runMs(1);
  runMs(40);
  CHECK(reel.energized);
  runMs(20);
  CHECK(!reel.energized);
}

TEST(with_release_off_the_coils_stay_energized) {
  bootWithId(5);
  home();
  CHECK(!reel.energized);
  sendAndSettle("m*F0");
  CHECK(reel.energized);  // turning release off energizes them straight away
  sendAndSettle("m5+1");
  CHECK(reel.energized);
  sendAndSettle("m*F1");
  CHECK(!reel.energized);
}

TEST(the_direction_setting_reverses_the_motor) {
  bootWithId(5);
  reel.forwardWhenClockwise = false;  // a motor wired the other way round
  send("m5h");
  runMs(200);
  CHECK(reel.backwardSteps > 0);
  sendAndSettle("m5x");
  sendAndSettle("m5C0");
  home();
}

TEST(recalculating_home_corrects_missed_steps_at_the_edge) {
  bootWithId(5);
  home();
  reel.stepsToMiss = 5;
  sendAndSettle("m5+32");
  CHECK_EQ(reel.position, OFFSET + 32 * FLAP - 5);  // the motor stalled for 5 steps
  sendAndSettle("m5+0");  // crosses the home edge
  CHECK_EQ(splitFlap().lastDrift(), (int16_t)5);
  CHECK_EQ(flapShowing(), 0);
}

TEST(without_recalculating_home_missed_steps_stay_missed) {
  bootWithId(5);
  home();
  sendAndSettle("m*E0");
  reel.stepsToMiss = 5;
  sendAndSettle("m5+32");
  sendAndSettle("m5+0");
  CHECK_EQ(splitFlap().lastDrift(), (int16_t)5);  // still measured
  CHECK_EQ(reel.position, OFFSET - 5);
}

TEST(revolutions_are_counted_and_saved_every_16) {
  bootWithId(5);
  home();  // crosses the edge once
  send("m5e15");
  CHECK(runUntilIdle(120000));
  CHECK_EQ(splitFlap().revolutionCount(), 16u);
  runMs(1);
  CHECK_EQ(EepromStore::getRevolutions(), 16u);
  sendAndSettle("m5e1");
  runMs(1);
  CHECK_EQ(EepromStore::getRevolutions(), 16u);  // not yet: 17
  boot();
  CHECK_EQ(splitFlap().revolutionCount(), 16u);  // what was saved
}
