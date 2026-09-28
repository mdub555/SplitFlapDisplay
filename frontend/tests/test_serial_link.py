"""Tests for the RS-485 dump parser in display/serial_link.py.

Run from frontend/:   python -m unittest tests.test_serial_link
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from display.serial_link import parse_buffer  # noqa: E402


class ParseBufferTest(unittest.TestCase):
    def test_parses_all_fields_with_crlf_terminator(self):
        # The firmware ends the line with Serial.println() -> "\r\n". The
        # trailing "\r" must not leak into the last field.
        self.assertEqual(
            parse_buffer("m05d:480:4096:1:0:1\r\n", 5),
            {'homeOffset': 480, 'totalSteps': 4096, 'motorClockwise': True,
             'autoHome': False, 'motorRelease': True},
        )

    def test_zero_fields_are_false(self):
        dump = parse_buffer("m05d:480:4096:0:1:0\r\n", 5)
        self.assertFalse(dump['motorClockwise'])
        self.assertTrue(dump['autoHome'])
        self.assertFalse(dump['motorRelease'])

    def test_bare_newline_terminator(self):
        self.assertEqual(parse_buffer("m05d:1:2:1:1:1\n", 5)['totalSteps'], 2)

    def test_unprovisioned_module_id(self):
        self.assertEqual(parse_buffer("m255d:480:4096:1:0:1\r\n", 255)['homeOffset'], 480)

    def test_ignores_echoed_command_before_reply(self):
        buf = "m05d\r\nm05d:10:20:1:1:1\r\n"
        self.assertEqual(parse_buffer(buf, 5)['homeOffset'], 10)

    def test_ignores_line_noise_before_reply(self):
        self.assertEqual(parse_buffer("\x00\x7fjunk m07d:10:20:1:1:1\r\n", 7)['totalSteps'], 20)

    def test_incomplete_line_is_not_parsed_yet(self):
        self.assertIsNone(parse_buffer("m05d:480:4096:1:0", 5))
        self.assertIsNone(parse_buffer("m05d:480:4096:1:0:1", 5))

    def test_other_modules_reply_is_ignored_when_id_given(self):
        buf = "m06d:1:2:1:1:1\r\n"
        self.assertIsNone(parse_buffer(buf, 5))
        self.assertEqual(parse_buffer(buf)['totalSteps'], 2)  # any id when omitted

    def test_id_must_match_exactly(self):
        # "m05d:" must not match inside "m105d:"
        self.assertIsNone(parse_buffer("m105d:1:2:1:1:1\r\n", 5))
        self.assertEqual(parse_buffer("m105d:1:2:1:1:1\r\n", 105)['homeOffset'], 1)

    def test_malformed_line_is_skipped_but_later_valid_line_is_used(self):
        buf = "m05d:x:y:1:1:1\r\nm05d:10:20:1:0:0\r\n"
        self.assertEqual(parse_buffer(buf, 5)['homeOffset'], 10)

    def test_too_few_fields_returns_none(self):
        self.assertIsNone(parse_buffer("m05d:480:4096:1:0\r\n", 5))

    def test_no_dump_returns_none(self):
        self.assertIsNone(parse_buffer("", 5))


if __name__ == '__main__':
    unittest.main()
