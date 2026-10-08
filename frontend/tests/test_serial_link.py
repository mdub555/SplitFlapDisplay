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


class BrokenSerial(FakeSerial):
    """A port whose device has gone: every use fails."""

    def __init__(self):
        super().__init__([])
        self.closed = False

    def write(self, data):
        raise serial_link.serial.SerialException('device disconnected')

    @property
    def in_waiting(self):
        raise OSError(5, 'Input/output error')

    def close(self):
        self.closed = True


class ReconnectTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(serial_link, 'ser', None)
        patcher.start()
        self.addCleanup(patcher.stop)
        serial_link.state.set_hardware_connected(True)

    def test_a_failed_write_drops_the_port(self):
        broken = BrokenSerial()
        serial_link.ser = broken
        with serial_link.serial_lock:
            self.assertFalse(serial_link.write_serial('m00-A\n'))
        self.assertIsNone(serial_link.ser)
        self.assertTrue(broken.closed)
        self.assertFalse(serial_link.state.snapshot()['hardware_connected'])

    def test_sending_with_no_port_is_simulated(self):
        q = serial_link.state.subscribe_serial()
        serial_link.send_raw('m00h')
        self.assertEqual(q.get_nowait(), 'SIMULATED SENT: m00h')
        serial_link.state.unsubscribe_serial(q)

    def test_reads_give_up_when_the_port_goes(self):
        serial_link.ser = BrokenSerial()
        self.assertIsNone(serial_link.read_dump(5, timeout=0.1))
        serial_link.ser = BrokenSerial()
        self.assertEqual(serial_link.read_all_dumps(0, margin=0.01), {})
        self.assertIsNone(serial_link.ser)

    def run_watchdog_once(self):
        """keep_connected() runs for ever; stop it after one check."""
        class Stop(Exception):
            pass
        sleeps = []

        def sleep(seconds):
            if sleeps:
                raise Stop
            sleeps.append(seconds)
        with mock.patch.object(serial_link.time, 'sleep', sleep):
            with self.assertRaises(Stop):
                serial_link.keep_connected(interval=5)

    def test_the_watchdog_reopens_a_missing_port(self):
        serial_link.state.set_hardware_connected(False)
        serial_link.state.last_sent_page = 'OLD PAGE'
        opened = FakeSerial([])
        with mock.patch.object(serial_link.serial, 'Serial', return_value=opened):
            self.run_watchdog_once()
        self.assertIs(serial_link.ser, opened)
        self.assertTrue(serial_link.state.snapshot()['hardware_connected'])
        self.assertIsNone(serial_link.state.last_sent_page, 'the page is sent again')

    def test_the_watchdog_notices_an_unplugged_port_while_idle(self):
        serial_link.ser = BrokenSerial()
        self.run_watchdog_once()
        self.assertIsNone(serial_link.ser)
        self.assertFalse(serial_link.state.snapshot()['hardware_connected'])

    def test_the_watchdog_keeps_trying_while_the_port_is_missing(self):
        with mock.patch.object(serial_link.serial, 'Serial', side_effect=serial_link.serial.SerialException('no')):
            self.run_watchdog_once()
        self.assertIsNone(serial_link.ser)


if __name__ == '__main__':
    unittest.main()
