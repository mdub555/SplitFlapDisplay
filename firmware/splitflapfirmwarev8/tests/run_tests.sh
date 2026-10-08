#!/usr/bin/env bash
# Builds the firmware on this computer against fake hardware (tests/fakes/)
# and runs the tests, each in its own process. Needs CMake 3.24+ and a C++17
# compiler; the first run downloads GoogleTest unless it's installed.
#
#   tests/run_tests.sh            run every test
#   tests/run_tests.sh Frame      run the tests whose names match "Frame"
set -euo pipefail

TESTS="$(cd "$(dirname "$0")" && pwd)"
BUILD="${BUILD_DIR:-$TESTS/build}"

cmake -S "$TESTS" -B "$BUILD" -DCMAKE_BUILD_TYPE=Debug > /dev/null
cmake --build "$BUILD" --parallel
ctest --test-dir "$BUILD" --output-on-failure --parallel "$(nproc 2>/dev/null || sysctl -n hw.ncpu)" \
  ${1:+--tests-regex "$1"}
