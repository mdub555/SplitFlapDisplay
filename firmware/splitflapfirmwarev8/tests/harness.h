// Drives the simulated module: power it on, put messages on the bus, let
// time pass, and read what it sent back.
#ifndef HARNESS_H
#define HARNESS_H

#include <stdint.h>

#include <string>

#include "../eeprom_store.h"
#include "../splitflap.h"
#include "fakes/fake_hardware.h"

namespace Module {
  // The module's SplitFlap, to check its state directly.
  SplitFlap& splitFlap();

  // Powers the module on (or back on): clears its RAM and the clock, as a
  // power cycle does, and runs setup(). The EEPROM and the reel keep their
  // state.
  void boot();

  // boot(), then gives the unprovisioned module `id` over the bus.
  void bootWithId(uint8_t id);

  // Puts `message` and a newline on the bus. The module reads it on its next
  // loop().
  void send(const std::string& message);

  // Puts bytes on the bus as they are, with no newline added.
  void sendRaw(const std::string& bytes);

  // Runs loop() for `ms` milliseconds of simulated time.
  void runMs(uint32_t ms);

  // Runs loop() until the module is idle (or `maxMs` pass). Returns whether
  // it went idle.
  bool runUntilIdle(uint32_t maxMs = 60000);

  // send(), then runUntilIdle().
  void sendAndSettle(const std::string& message);

  // Everything the module has sent on the bus since the last call.
  std::string takeOutput();

  // Homes the module and checks it landed on flap 0.
  void home();

  // The flap the reel is showing, from where the reel physically is and the
  // module's saved home offset and total steps; -1 if it isn't on one.
  int flapShowing();

  // Defined in firmware.cpp, next to the sketch's globals.
  void clearRam();
  void runSetup();
  void runLoop();
}

#endif
