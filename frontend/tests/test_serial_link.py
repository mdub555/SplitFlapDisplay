"""Tests for the RS-485 dump parser in display/serial_link.py.

Run from frontend/:   python -m unittest tests.test_serial_link
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from display.serial_link import parse_buffer, parse_all_dumps  # noqa: E402


class ParseBufferTest(unittest.TestCase):
    def test_parses_all_fields_with_crlf_terminator(self):
        # The firmware ends the line with Serial.println() -> "\r\n". The
        # trailing "\r" must not leak into the last field.
        self.assertEqual(
            parse_buffer("m05d:480:4096:100:2:3:1:0:1:0\r\n", 5),
            {'homeOffset': 480, 'totalSteps': 4096, 'debounceMs': 100,
             'stepDelay': 2, 'homingStepDelay': 3, 'motorClockwise': True,
             'autoHome': False, 'motorRelease': True, 'recalculateHome': False},
        )

    def test_zero_fields_are_false(self):
        dump = parse_buffer("m05d:480:4096:100:1:1:0:1:0:1\r\n", 5)
        self.assertFalse(dump['motorClockwise'])
        self.assertTrue(dump['autoHome'])
        self.assertFalse(dump['motorRelease'])
        self.assertTrue(dump['recalculateHome'])

    def test_bare_newline_terminator(self):
        self.assertEqual(parse_buffer("m05d:1:2:3:4:5:1:1:1:1\n", 5)['totalSteps'], 2)

    def test_unprovisioned_module_id(self):
        self.assertEqual(parse_buffer("m255d:480:4096:100:1:1:1:0:1:1\r\n", 255)['homeOffset'], 480)

    def test_ignores_echoed_command_before_reply(self):
        buf = "m05d\r\nm05d:10:20:100:1:1:1:1:1:1\r\n"
        self.assertEqual(parse_buffer(buf, 5)['homeOffset'], 10)

    def test_ignores_line_noise_before_reply(self):
        self.assertEqual(parse_buffer("\x00\x7fjunk m07d:10:20:100:1:1:1:1:1:1\r\n", 7)['totalSteps'], 20)

    def test_incomplete_line_is_not_parsed_yet(self):
        self.assertIsNone(parse_buffer("m05d:480:4096:100:1:1:1:0", 5))
        self.assertIsNone(parse_buffer("m05d:480:4096:100:1:1:1:0:1:1", 5))

    def test_other_modules_reply_is_ignored_when_id_given(self):
        buf = "m06d:1:2:100:1:1:1:1:1:1\r\n"
        self.assertIsNone(parse_buffer(buf, 5))
        self.assertEqual(parse_buffer(buf)['totalSteps'], 2)  # any id when omitted

    def test_id_must_match_exactly(self):
        # "m05d:" must not match inside "m105d:"
        self.assertIsNone(parse_buffer("m105d:1:2:100:1:1:1:1:1:1\r\n", 5))
        self.assertEqual(parse_buffer("m105d:1:2:100:1:1:1:1:1:1\r\n", 105)['homeOffset'], 1)

    def test_malformed_line_is_skipped_but_later_valid_line_is_used(self):
        buf = "m05d:x:y:100:1:1:1:1:1:1\r\nm05d:10:20:100:1:1:1:0:0:0\r\n"
        self.assertEqual(parse_buffer(buf, 5)['homeOffset'], 10)

    def test_too_few_fields_returns_none(self):
        self.assertIsNone(parse_buffer("m05d:480:4096:100:1:1:1:0\r\n", 5))

    def test_pre_timing_firmware_dump_is_not_accepted(self):
        # Firmware from before the timing/debounce fields sent only five
        # values after the id; guessing at that layout would mis-assign them.
        self.assertIsNone(parse_buffer("m05d:480:4096:1:0:1\r\n", 5))

    def test_extended_fields_are_parsed(self):
        dump = parse_buffer("m05d:480:4096:50:2:1:1:0:1:1:6:40:120:80:-12\r\n", 5)
        self.assertEqual(
            {k: dump[k] for k in ('rampStartDelay', 'rampSteps', 'settleMs', 'staggerMs', 'drift')},
            {'rampStartDelay': 6, 'rampSteps': 40, 'settleMs': 120, 'staggerMs': 80, 'drift': -12},
        )
        self.assertEqual(dump['stepDelay'], 2)

    def test_revolutions_are_parsed_before_drift(self):
        dump = parse_buffer("m05d:480:4096:50:2:1:1:0:1:1:6:40:120:80:12345:-3\r\n", 5)
        self.assertEqual((dump['revolutions'], dump['drift'], dump['staggerMs']), (12345, -3, 80))

    def test_dump_without_revolutions_still_has_drift(self):
        # Firmware from before the revolution counter.
        dump = parse_buffer("m05d:480:4096:50:2:1:1:0:1:1:6:40:120:80:-3\r\n", 5)
        self.assertEqual(dump['drift'], -3)
        self.assertNotIn('revolutions', dump)

    def test_nine_field_dump_has_no_extended_keys(self):
        dump = parse_buffer("m05d:480:4096:50:1:1:1:0:1:1\r\n", 5)
        for key in ('rampStartDelay', 'rampSteps', 'settleMs', 'staggerMs', 'drift'):
            self.assertNotIn(key, dump)

    def test_malformed_extended_field_rejects_the_line(self):
        self.assertIsNone(parse_buffer("m05d:480:4096:50:1:1:1:0:1:1:3:x:0:150:0\r\n", 5))

    def test_no_dump_returns_none(self):
        self.assertIsNone(parse_buffer("", 5))


class ParseAllDumpsTest(unittest.TestCase):
    def test_collects_every_module_in_a_broadcast_reply(self):
        buffer = ("m00d:480:4096:50:1:1:1:0:1:1:3:0:0:150:7:0\r\n"
                  "m05d:470:4075:50:1:1:1:0:1:1:3:0:0:150:9:-2\r\n"
                  "m63d:460:4096:50:1:1:1:0:1:1:3:0:0:150:11:1\r\n")
        dumps = parse_all_dumps(buffer)
        self.assertEqual(sorted(dumps), [0, 5, 63])
        self.assertEqual((dumps[5]['totalSteps'], dumps[5]['drift']), (4075, -2))

    def test_skips_partial_and_malformed_lines(self):
        buffer = ("m01d:480:4096:50:1:1:1:0:1:1\r\n"
                  "m02d:garbage\r\n"
                  "m03d:480:4096:50:1:1:1:0")
        self.assertEqual(sorted(parse_all_dumps(buffer)), [1])

    def test_empty_buffer(self):
        self.assertEqual(parse_all_dumps(""), {})


if __name__ == '__main__':
    unittest.main()
