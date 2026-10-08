// The firmware's sketch, built on the host. The other sources (splitflap.cpp,
// transceiver.cpp, ...) are compiled as they are; this file pulls in the
// sketch so the tests can reach its globals.
#include "../splitflapfirmwarev8.ino"

#include "harness.h"

namespace Module {
  SplitFlap& splitFlap() { return ::splitFlap; }

  void clearRam() {
    transceiver = Transceiver();
    ::splitFlap = SplitFlap(&debugSerial);
    command = Command();
    dumpPending = false;
    dumpDelayMs = 0;
    dumpAtMs = 0;
    flapOffsetsPending = false;
    identifyStartMs = 0;
    identifying = false;
  }

  void runSetup() { setup(); }
  void runLoop() { loop(); }
}
