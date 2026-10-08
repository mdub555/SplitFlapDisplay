// Reading messages off the bus: addressing, data, and what's rejected.
#include <Arduino.h>

#include "harness.h"
#include "test.h"

using namespace Module;

TEST(a_message_for_another_module_is_ignored) {
  bootWithId(5);
  sendAndSettle("m6h");
  sendAndSettle("m50h");
  CHECK_EQ(reel.forwardSteps, 0u);
}

TEST(the_id_can_have_leading_zeros) {
  bootWithId(5);
  sendAndSettle("m005S1500");
  CHECK_EQ(EepromStore::getStepDelayUs(), (uint16_t)1500);
}

TEST(a_message_without_an_id_is_ignored) {
  bootWithId(0);
  sendAndSettle("mS1500");
  CHECK_EQ(EepromStore::getStepDelayUs(), (uint16_t)1000);
}

TEST(an_id_above_255_does_not_wrap_onto_a_module) {
  bootWithId(5);
  sendAndSettle("m261S1500");  // 261 = 256 + 5
  CHECK_EQ(EepromStore::getStepDelayUs(), (uint16_t)1000);
}

TEST(a_broadcast_reaches_every_module) {
  bootWithId(5);
  sendAndSettle("m*S1500");
  CHECK_EQ(EepromStore::getStepDelayUs(), (uint16_t)1500);
}

TEST(bytes_before_the_m_are_skipped) {
  bootWithId(5);
  sendAndSettle("\x01junk!m5S1500");
  CHECK_EQ(EepromStore::getStepDelayUs(), (uint16_t)1500);
}

TEST(an_unknown_command_is_ignored) {
  bootWithId(5);
  sendAndSettle("m5Z12");
  sendAndSettle("m5S1500");  // and the next message still works
  CHECK_EQ(EepromStore::getStepDelayUs(), (uint16_t)1500);
}

TEST(a_number_is_required_where_one_is_expected) {
  bootWithId(5);
  sendAndSettle("m5S");
  sendAndSettle("m5Sx");
  CHECK_EQ(EepromStore::getStepDelayUs(), (uint16_t)1000);
}

TEST(numbers_out_of_range_are_rejected) {
  bootWithId(5);
  sendAndSettle("m5S65536");  // over 16 bits
  sendAndSettle("m5S99999");
  sendAndSettle("m5S0");      // a step delay of 0
  sendAndSettle("m5T0");      // a revolution of 0 steps
  sendAndSettle("m5A2");      // not 0 or 1
  sendAndSettle("m5L256");    // over a byte
  sendAndSettle("m5O4096");   // not below total steps
  CHECK_EQ(EepromStore::getStepDelayUs(), (uint16_t)1000);
  CHECK_EQ(EepromStore::getTotalSteps(), (uint16_t)4096);
  CHECK_EQ(EepromStore::autoHomeEnabled(), false);
  CHECK_EQ(EepromStore::getRampSteps(), (uint8_t)0);
  CHECK_EQ(EepromStore::getHomeOffset(), (uint16_t)480);
}

TEST(numbers_at_the_ends_of_their_range_are_accepted) {
  bootWithId(5);
  sendAndSettle("m5S65535");
  sendAndSettle("m5L255");
  sendAndSettle("m5O4095");
  sendAndSettle("m5D0");
  CHECK_EQ(EepromStore::getStepDelayUs(), (uint16_t)65535);
  CHECK_EQ(EepromStore::getRampSteps(), (uint8_t)255);
  CHECK_EQ(EepromStore::getHomeOffset(), (uint16_t)4095);
  CHECK_EQ(EepromStore::getDebounceMs(), (uint16_t)0);
}

TEST(a_message_with_no_newline_is_read_after_50ms) {
  bootWithId(5);
  sendRaw("m5S1500");
  runMs(20);
  CHECK_EQ(EepromStore::getStepDelayUs(), (uint16_t)1000);
  runMs(50);
  CHECK_EQ(EepromStore::getStepDelayUs(), (uint16_t)1500);
}

TEST(a_broadcast_id_change_only_reaches_unprovisioned_modules) {
  bootWithId(5);
  sendAndSettle("m*@7");
  CHECK_EQ(EepromStore::getModuleId(), (uint8_t)5);
  sendAndSettle("m5@7");
  CHECK_EQ(EepromStore::getModuleId(), (uint8_t)7);
}

// ---- Frames ----

TEST(a_frame_gives_each_module_its_character_and_rank) {
  bootWithId(2);
  home();
  // Modules 0, 1, 2 show A, B, C, as ranks 0, 1, 2 (sent as '!' + rank),
  // 10 ms apart: module 2 starts 20 ms after the frame.
  send("m*f10:A!B\"C#");
  runMs(15);
  CHECK_EQ(reel.position, (uint16_t)480);
  runMs(10);
  CHECK(reel.position != 480);
  CHECK(runUntilIdle());
  CHECK_EQ(flapShowing(), 3);
}

TEST(a_frame_without_a_pair_for_this_module_is_ignored) {
  bootWithId(5);
  home();
  sendAndSettle("m*f0:A!B!C!");
  runMs(100);
  CHECK_EQ(flapShowing(), 0);
}

TEST(a_frame_can_be_longer_than_the_receive_buffer) {
  bootWithId(40);
  home();
  std::string pairs;
  for (int id = 0; id < 40; id++) pairs += "A!";
  pairs += "Z!";  // module 40's pair is bytes 81 and 82
  sendAndSettle("m*f0:" + pairs);
  runMs(10);
  CHECK(runUntilIdle());
  CHECK_EQ(flapShowing(), 26);
}

TEST(a_frame_that_stalls_is_dropped) {
  bootWithId(1);
  home();
  sendRaw("m*f0:A!B!");  // no newline
  runMs(200);
  CHECK_EQ(flapShowing(), 0);
  sendAndSettle("m1+3");  // the bus works again afterwards
  CHECK_EQ(flapShowing(), 3);
}
