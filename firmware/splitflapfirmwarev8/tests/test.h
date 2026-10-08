// A small test framework: TEST() registers a test, CHECK() and CHECK_EQ()
// report a failure and carry on. main.cpp runs each test in its own
// process, so every test starts from a powered-off module with blank EEPROM.
#ifndef TEST_H
#define TEST_H

#include <stdio.h>

#include <string>
#include <type_traits>
#include <vector>

struct TestCase {
  const char* name;
  void (*run)();
};

std::vector<TestCase>& testRegistry();

struct TestRegistration {
  TestRegistration(const char* name, void (*run)()) { testRegistry().push_back({name, run}); }
};

#define TEST(name)                                              \
  static void name();                                           \
  static TestRegistration name##_registration(#name, name);     \
  static void name()

extern int checkFailures;
extern const char* currentTest;

template <typename T> std::string describe(const T& value) {
  if constexpr (std::is_same_v<T, std::string>) {
    return "\"" + value + "\"";
  } else if constexpr (std::is_same_v<T, char>) {
    return std::string("'") + value + "'";
  } else if constexpr (std::is_same_v<T, bool>) {
    return value ? "true" : "false";
  } else if constexpr (std::is_enum_v<T>) {
    return std::to_string((long long)value);
  } else if constexpr (std::is_integral_v<T>) {
    return std::to_string((long long)value);
  } else {
    return std::string(value);
  }
}

inline void checkFailed(const char* file, int line, const std::string& what) {
  if (checkFailures++ == 0) printf("  FAIL  %s\n", currentTest);
  printf("          %s:%d: %s\n", file, line, what.c_str());
}

#define CHECK(condition)                                                     \
  do {                                                                       \
    if (!(condition)) checkFailed(__FILE__, __LINE__, "CHECK(" #condition ")"); \
  } while (0)

#define CHECK_EQ(actual, expected)                                           \
  do {                                                                       \
    auto actualValue = (actual);                                             \
    decltype(actualValue) expectedValue = (expected);                        \
    if (!(actualValue == expectedValue)) {                                   \
      checkFailed(__FILE__, __LINE__, #actual " is " + describe(actualValue) + \
                  ", expected " + describe(expectedValue));                  \
    }                                                                        \
  } while (0)

#endif
