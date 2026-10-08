// Runs every registered test, each in a forked process so it starts from a
// fresh module, and reports the failures. Pass a name (or part of one) to run
// only the matching tests.
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

#include "test.h"

std::vector<TestCase>& testRegistry() {
  static std::vector<TestCase> tests;
  return tests;
}

int checkFailures = 0;
const char* currentTest = "";

// A test that runs longer than this has hung (a loop that never goes idle).
const unsigned TIMEOUT_S = 30;

int main(int argc, char** argv) {
  const char* filter = argc > 1 ? argv[1] : nullptr;
  int passed = 0, failed = 0;
  for (const TestCase& test : testRegistry()) {
    if (filter && !strstr(test.name, filter)) continue;
    fflush(stdout);
    pid_t pid = fork();
    if (pid == 0) {
      currentTest = test.name;
      alarm(TIMEOUT_S);
      test.run();
      fflush(stdout);
      _exit(checkFailures ? 1 : 0);
    }
    int status = 0;
    waitpid(pid, &status, 0);
    bool ok = WIFEXITED(status) && WEXITSTATUS(status) == 0;
    if (ok) {
      passed++;
      printf("  ok    %s\n", test.name);
    } else {
      failed++;
      // A failed check has already printed the test's name and what failed.
      if (WIFSIGNALED(status)) {
        printf("  FAIL  %s (%s)\n", test.name,
               WTERMSIG(status) == SIGALRM ? "timed out" : strsignal(WTERMSIG(status)));
      }
    }
  }
  printf("\n%d passed, %d failed\n", passed, failed);
  return failed ? 1 : 0;
}
