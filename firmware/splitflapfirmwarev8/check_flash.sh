#!/usr/bin/env bash
# Builds the firmware for the ATtiny816 (the attiny816 profile in
# sketch.yaml) twice, and reports how much flash and RAM each uses:
#   debug    with debug output, as the sketch is checked in
#   release  without (DEBUG_OUTPUT 0), as it's flashed onto the modules
# Fails if either build doesn't fit, and warns when one has less than
# WARN_FREE bytes of flash left.
#
#   ./check_flash.sh
#
# Needs arduino-cli (https://arduino.github.io/arduino-cli/). The first run
# downloads megaTinyCore and its toolchain, as listed in sketch.yaml.
#
# Environment:
#   WARN_FREE    warn below this much free flash, in bytes (default 256)
#   ARDUINO_CLI  the arduino-cli to run (default: arduino-cli on the PATH)
#   BUILD_DIR    where to build (default: a temporary directory)
set -euo pipefail

SKETCH="$(cd "$(dirname "$0")" && pwd)"
WARN_FREE="${WARN_FREE:-256}"
ARDUINO_CLI="${ARDUINO_CLI:-arduino-cli}"
if [[ -z "${BUILD_DIR:-}" ]]; then
  BUILD_DIR="$(mktemp -d)"
  trap 'rm -rf "$BUILD_DIR"' EXIT
fi

if ! command -v "$ARDUINO_CLI" > /dev/null; then
  echo "arduino-cli not found: install it, or set ARDUINO_CLI to its path." >&2
  exit 2
fi

# arduino-cli looks up the upload port in sketch.yaml (default_port) even
# just to compile, and stops if nothing is plugged in there. So the build is
# of a copy of the sketch whose sketch.yaml has no upload port.
COPY="$BUILD_DIR/sketch/$(basename "$SKETCH")"
mkdir -p "$COPY"
cp "$SKETCH"/*.ino "$SKETCH"/*.cpp "$SKETCH"/*.h "$COPY"/
grep -vE '^default_(port|protocol):' "$SKETCH/sketch.yaml" > "$COPY/sketch.yaml"

failed=0
summary="| Build | Flash used | Flash free | RAM used |\n|---|---|---|---|\n"

# Reports a problem, as an annotation when running in GitHub Actions.
report() {
  local level=$1 message=$2
  if [[ -n "${GITHUB_ACTIONS:-}" ]]; then
    echo "::$level title=Firmware size::$message"
  else
    echo "${level^^}: $message"
  fi
}

# Builds into BUILD_DIR/`name` with `flags` added to the compiler's, and
# checks the sizes.
check_build() {
  local name=$1 flags=$2 output
  echo "Building $name..."
  if ! output=$("$ARDUINO_CLI" compile --profile attiny816 --build-path "$BUILD_DIR/$name" \
                  --build-property "compiler.cpp.extra_flags=$flags" "$COPY" 2>&1); then
    echo "$output"
    report error "The $name build failed, or doesn't fit (see above)."
    failed=1
    summary+="| $name | failed | | |\n"
    return
  fi

  # arduino-cli's summary lines, e.g.
  #   Sketch uses 7570 bytes (92%) of program storage space. Maximum is 8192 bytes.
  #   Global variables use 206 bytes (40%) of dynamic memory, leaving 306 bytes ... Maximum is 512 bytes.
  local flash max_flash ram max_ram
  flash=$(sed -nE 's/^Sketch uses ([0-9]+) bytes.*/\1/p' <<< "$output")
  max_flash=$(sed -nE 's/^Sketch uses .*Maximum is ([0-9]+) bytes.*/\1/p' <<< "$output")
  ram=$(sed -nE 's/^Global variables use ([0-9]+) bytes.*/\1/p' <<< "$output")
  max_ram=$(sed -nE 's/^Global variables use .*Maximum is ([0-9]+) bytes.*/\1/p' <<< "$output")
  if [[ -z "$flash" || -z "$max_flash" ]]; then
    echo "$output"
    report error "Couldn't find the $name build's size in arduino-cli's output."
    failed=1
    return
  fi

  local free=$((max_flash - flash))
  printf '  flash: %5d of %d bytes (%d free)\n' "$flash" "$max_flash" "$free"
  [[ -n "$ram" ]] && printf '  RAM:   %5d of %d bytes used by globals\n' "$ram" "$max_ram"
  summary+="| $name | $flash / $max_flash B | $free B | ${ram:-?} / ${max_ram:-?} B |\n"
  if (( free < WARN_FREE )); then
    report warning "The $name build has only $free bytes of flash left (warning below $WARN_FREE)."
  fi
}

check_build debug ""
check_build release "-DDEBUG_OUTPUT=0"

if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
  printf '### Firmware size\n\n%b' "$summary" >> "$GITHUB_STEP_SUMMARY"
fi
exit $failed
