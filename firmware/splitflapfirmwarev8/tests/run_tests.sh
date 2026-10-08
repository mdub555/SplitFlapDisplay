#!/usr/bin/env bash
# Builds the firmware on this computer against fake hardware (tests/fakes/)
# and runs the tests. Needs only a C++17 compiler (g++ or clang++).
#
#   tests/run_tests.sh            run every test
#   tests/run_tests.sh frame      run the tests whose names contain "frame"
set -euo pipefail

TESTS="$(cd "$(dirname "$0")" && pwd)"
SKETCH="$(dirname "$TESTS")"
BUILD="${BUILD_DIR:-$TESTS/build}"
CXX="${CXX:-g++}"
mkdir -p "$BUILD"

# Debug output is compiled out: it bit-bangs a pin with interrupts off.
"$CXX" -std=gnu++17 -O1 -g -Wall -Werror \
  -DDEBUG_OUTPUT=0 -I"$TESTS/fakes" -I"$SKETCH" \
  "$TESTS/firmware.cpp" \
  "$SKETCH/splitflap.cpp" "$SKETCH/transceiver.cpp" "$SKETCH/eeprom_store.cpp" \
  "$SKETCH/home_sensor.cpp" "$SKETCH/motor.cpp" \
  "$TESTS/fakes/fake_hardware.cpp" "$TESTS/harness.cpp" "$TESTS/main.cpp" \
  "$TESTS"/test_*.cpp \
  -o "$BUILD/firmware_tests"

"$BUILD/firmware_tests" "$@"
