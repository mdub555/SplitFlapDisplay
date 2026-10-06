"""Tests for display/module_protocol.py, including that its command letters
and shared constants match the firmware source.

Run from frontend/:   python -m unittest tests.test_module_protocol
"""
import os
import re
import sys
import unittest

FRONTEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIRMWARE = os.path.join(os.path.dirname(FRONTEND), 'firmware', 'splitflapfirmwarev8')
sys.path.insert(0, FRONTEND)

from display.module_protocol import (  # noqa: E402
    BROADCAST, DUMP_SLOT_S, UNPROVISIONED_ID, Cmd, dump_reply_pattern, message)


def _firmware(name):
    with open(os.path.join(FIRMWARE, name)) as f:
        return f.read()


def _cmd_letters():
    return {name: value for name, value in vars(Cmd).items() if not name.startswith('_')}


class MatchesFirmwareTest(unittest.TestCase):
    """The frontend and firmware are flashed and deployed together; these
    catch one side changing a letter or constant without the other."""

    def firmware_commands(self):
        source = _firmware('transceiver.cpp')
        # Named letters used in the table, e.g. const char DUMP_CODE = '?';
        codes = dict(re.findall(r"const char (\w+_CODE) = '(.)';", source))
        table = source[source.index('const CommandSpec COMMANDS[]'):]
        table = table[:table.index('};')]
        commands = {}
        for code, name in re.findall(r"\{\s*('.'|\w+_CODE)\s*,\s*(\w+)\s*,", table):
            commands[name] = code[1] if code.startswith("'") else codes[code]
        # FRAME is only reached through the frame header, not the table.
        commands['FRAME'] = codes['FRAME_CODE']
        return commands

    def test_every_command_letter_matches(self):
        self.assertEqual(_cmd_letters(), self.firmware_commands())

    def test_letters_are_unique(self):
        letters = list(_cmd_letters().values())
        self.assertEqual(len(letters), len(set(letters)))

    def test_letters_avoid_the_protocol_characters(self):
        # 'm' starts a message, '*' is the broadcast ID, ':' separates frame
        # and dump fields, and digits are read as part of the ID.
        for name, letter in _cmd_letters().items():
            with self.subTest(command=name):
                self.assertNotIn(letter, 'm*:0123456789')

    def test_dump_slot_matches(self):
        slot_ms = re.search(r'DUMP_SLOT_MS = (\d+);', _firmware('splitflapfirmwarev8.ino')).group(1)
        self.assertAlmostEqual(DUMP_SLOT_S, int(slot_ms) / 1000)

    def test_unprovisioned_id_matches(self):
        firmware_id = re.search(r'UNPROVISIONED_ID = (\d+);', _firmware('eeprom_store.h')).group(1)
        self.assertEqual(UNPROVISIONED_ID, int(firmware_id))


class MessageTest(unittest.TestCase):
    def test_module_ids_are_at_least_two_digits(self):
        self.assertEqual(message(5, Cmd.HOME), 'm05h')
        self.assertEqual(message(123, Cmd.SET_MOTOR_RELEASE, 0), 'm123F0')

    def test_broadcast(self):
        self.assertEqual(message(BROADCAST, Cmd.SET_STEP_DELAY, 1250), 'm*S1250')

    def test_data_is_appended_as_given(self):
        self.assertEqual(message(5, Cmd.DISPLAY_CHAR, 'A'), 'm05-A')
        self.assertEqual(message(5, Cmd.DISPLAY_CHAR, ' '), 'm05- ')


class DumpReplyPatternTest(unittest.TestCase):
    def test_any_id(self):
        buf = 'junk m05?:1:2\r\nm7?:3\n'
        self.assertEqual(re.findall(dump_reply_pattern(), buf), [('05', '1:2'), ('7', '3')])

    def test_given_id_must_match_exactly(self):
        self.assertEqual(re.findall(dump_reply_pattern('05'), 'm105?:1\nm05?:2\n'), [('05', '2')])

    def test_incomplete_line_does_not_match(self):
        self.assertEqual(re.findall(dump_reply_pattern(), 'm05?:1:2'), [])


if __name__ == '__main__':
    unittest.main()
