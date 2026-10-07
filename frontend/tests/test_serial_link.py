"""Tests for the RS-485 dump parser in display/serial_link.py.

Run from frontend/:   python -m unittest tests.test_serial_link
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest import mock  # noqa: E402

from display import serial_link  # noqa: E402
from display.serial_link import parse_buffer, parse_all_dumps  # noqa: E402

# Every field, in the order the firmware sends them.
FIELDS = ('\tO480\tT4096\tD100\tS1250\tH1800\tC1\tA0\tF1\tE0'
          '\tR6000\tL40\tW120\tP80\t#123456\t~-12')
PARSED = {'homeOffset': 480, 'totalSteps': 4096, 'debounceMs': 100,
          'stepDelayUs': 1250, 'homingStepDelayUs': 1800, 'motorClockwise': True,
          'autoHome': False, 'motorRelease': True, 'recalculateHome': False,
          'rampStartDelayUs': 6000, 'rampSteps': 40, 'settleMs': 120, 'staggerMs': 80,
          'revolutions': 123456, 'drift': -12}


def reply(mod_id='05', fields=FIELDS, end='\r\n'):
    return f"m{mod_id}?{fields}{end}"


class ParseBufferTest(unittest.TestCase):
    def test_parses_all_fields_with_crlf_terminator(self):
        # The firmware ends the line with Serial.println() -> "\r\n". The
        # trailing "\r" must not leak into the last field.
        self.assertEqual(parse_buffer(reply(), 5), PARSED)

    def test_fields_can_come_in_any_order(self):
        reordered = ''.join('\t' + f for f in reversed(FIELDS.split('\t')[1:]))
        self.assertEqual(parse_buffer(reply(fields=reordered), 5), PARSED)

    def test_booleans(self):
        dump = parse_buffer(reply(fields=FIELDS.replace('\tC1', '\tC0').replace('\tA0', '\tA1')), 5)
        self.assertFalse(dump['motorClockwise'])
        self.assertTrue(dump['autoHome'])

    def test_bare_newline_terminator(self):
        self.assertEqual(parse_buffer(reply(end='\n'), 5)['totalSteps'], 4096)

    def test_unprovisioned_module_id(self):
        self.assertEqual(parse_buffer(reply('255'), 255)['homeOffset'], 480)

    def test_ignores_echoed_command_before_reply(self):
        self.assertEqual(parse_buffer("m05?\r\n" + reply(), 5), PARSED)

    def test_ignores_line_noise_before_reply(self):
        self.assertEqual(parse_buffer("\x00\x7fjunk " + reply('07'), 7)['totalSteps'], 4096)

    def test_incomplete_line_is_not_parsed_yet(self):
        self.assertIsNone(parse_buffer(reply(end=''), 5))
        self.assertIsNone(parse_buffer(reply(fields=FIELDS[:20], end=''), 5))

    def test_other_modules_reply_is_ignored_when_id_given(self):
        buf = reply('06')
        self.assertIsNone(parse_buffer(buf, 5))
        self.assertEqual(parse_buffer(buf)['totalSteps'], 4096)  # any id when omitted

    def test_id_must_match_exactly(self):
        # "m05?" must not match inside "m105?"
        self.assertIsNone(parse_buffer(reply('105'), 5))
        self.assertEqual(parse_buffer(reply('105'), 105)['homeOffset'], 480)

    def test_malformed_line_is_skipped_but_later_valid_line_is_used(self):
        buf = reply(fields=FIELDS.replace('O480', 'Ox')) + reply(fields=FIELDS.replace('O480', 'O10'))
        self.assertEqual(parse_buffer(buf, 5)['homeOffset'], 10)

    def test_missing_field_rejects_the_line(self):
        self.assertIsNone(parse_buffer(reply(fields=FIELDS.replace('\tW120', '')), 5))

    def test_unknown_label_rejects_the_line(self):
        self.assertIsNone(parse_buffer(reply(fields=FIELDS.replace('W120', 'Q120')), 5))

    def test_repeated_field_rejects_the_line(self):
        self.assertIsNone(parse_buffer(reply(fields=FIELDS.replace('\tW120', '\tO1')), 5))

    def test_empty_or_bad_values_reject_the_line(self):
        for bad in ('O', 'O-', 'O4.5', 'O 4'):
            with self.subTest(field=bad):
                self.assertIsNone(parse_buffer(reply(fields=FIELDS.replace('O480', bad)), 5))

    def test_old_colon_format_is_not_accepted(self):
        self.assertIsNone(parse_buffer("m05?:480:4096:100:1000:1000:1:1:1:1:3000:0:0:150:12:-3\r\n", 5))

    def test_no_dump_returns_none(self):
        self.assertIsNone(parse_buffer("", 5))


class ParseAllDumpsTest(unittest.TestCase):
    def test_collects_every_module_in_a_broadcast_reply(self):
        buffer = (reply('00', FIELDS.replace('~-12', '~0'))
                  + reply('05', FIELDS.replace('T4096', 'T4075').replace('~-12', '~-2'))
                  + reply('63'))
        dumps = parse_all_dumps(buffer)
        self.assertEqual(sorted(dumps), [0, 5, 63])
        self.assertEqual((dumps[5]['totalSteps'], dumps[5]['drift']), (4075, -2))

    def test_skips_partial_and_malformed_lines(self):
        buffer = (reply('01')
                  + reply('02', '\tgarbage')
                  + reply('03', end=''))
        self.assertEqual(sorted(parse_all_dumps(buffer)), [1])

    def test_empty_buffer(self):
        self.assertEqual(parse_all_dumps(""), {})


class FakeSerial:
    """Hands out `chunks` one read at a time, as replies trickle in."""

    def __init__(self, chunks):
        self.chunks = [c.encode() for c in chunks]

    @property
    def in_waiting(self):
        return len(self.chunks[0]) if self.chunks else 0

    def read(self, n):
        return self.chunks.pop(0)

    def reset_input_buffer(self):
        pass

    def write(self, data):
        pass

    def flush(self):
        pass


class ReadAllDumpsTest(unittest.TestCase):
    def test_each_reply_is_reported_as_it_arrives(self):
        first = reply('00')
        chunks = [first[:20], first[20:] + reply('01')[:10], reply('01')[10:]]
        seen = []
        fake = FakeSerial(chunks)
        with mock.patch.object(serial_link, 'ser', fake):
            dumps = serial_link.read_all_dumps(
                1, margin=0.05, on_reply=lambda mod_id, dump: seen.append((mod_id, len(fake.chunks))))
        self.assertEqual(sorted(dumps), [0, 1])
        # Module 0 was reported once its line was complete, before module 1's arrived.
        self.assertEqual(seen, [(0, 1), (1, 0)])


if __name__ == '__main__':
    unittest.main()
