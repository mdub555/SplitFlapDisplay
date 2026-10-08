# Builds the firmware on the host, against the fakes in fakes/, with the
# tests. Run them with run_tests.sh, or ctest, so each test gets its own
# process (and so a freshly powered-on module).
cmake_minimum_required(VERSION 3.24)
project(splitflap_firmware_tests CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS ON)

# GoogleTest: an installed one if there is one, otherwise this release,
# downloaded on the first configure.
include(FetchContent)
FetchContent_Declare(
  googletest
  GIT_REPOSITORY https://github.com/google/googletest.git
  GIT_TAG v1.15.2
  GIT_SHALLOW TRUE
  FIND_PACKAGE_ARGS NAMES GTest
)
set(INSTALL_GTEST OFF CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(googletest)

set(SKETCH ${CMAKE_CURRENT_SOURCE_DIR}/..)

add_executable(firmware_tests
  # The firmware, unchanged. firmware.cpp includes the sketch (.ino).
  firmware.cpp
  ${SKETCH}/splitflap.cpp
  ${SKETCH}/transceiver.cpp
  ${SKETCH}/eeprom_store.cpp
  ${SKETCH}/home_sensor.cpp
  ${SKETCH}/motor.cpp
  # The fake hardware, and the tests.
  fakes/fake_hardware.cpp
  harness.cpp
  test_bus.cpp
  test_module.cpp
  test_motion.cpp
)
# fakes/ first, so the firmware's #include <Arduino.h> finds the fake one.
target_include_directories(firmware_tests PRIVATE fakes ${SKETCH})
# Debug output is compiled out: it bit-bangs a pin with interrupts off.
target_compile_definitions(firmware_tests PRIVATE DEBUG_OUTPUT=0)
target_compile_options(firmware_tests PRIVATE -Wall -Werror)
target_link_libraries(firmware_tests PRIVATE GTest::gtest_main)

enable_testing()
include(GoogleTest)
# One CTest test per test, each run in its own process. A test that runs
# longer than the timeout has hung (a loop that never goes idle).
gtest_discover_tests(firmware_tests PROPERTIES TIMEOUT 30)
