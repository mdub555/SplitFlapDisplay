"""Tests for settings/backup.py's restore_backup().

Run from frontend/:   python -m unittest tests.test_backup
"""
import os
import sys
import types
import unittest
from unittest import mock

FRONTEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, FRONTEND)


def _module(name, **attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    return mod


class RestoreBackupTest(unittest.TestCase):
    def setUp(self):
        self.sent = []
        self.saves = 0
        self.connected = True
        self.settings = {'modules': {}}

        fakes = {
            'settings.store': _module('settings.store', settings=self.settings,
                                      save_settings=lambda _: setattr(self, 'saves', self.saves + 1)),
            'display.serial_link': _module('display.serial_link', send_raw=self.sent.append,
                                           is_connected=lambda: self.connected),
        }
        patcher = mock.patch.dict(sys.modules, fakes)
        patcher.start()
        self.addCleanup(patcher.stop)

        # Each test imports fresh so the module-level `from X import Y`
        # bindings above pick up this test's fakes rather than a previous
        # test's, or the real (unmocked) modules from an earlier import.
        sys.modules.pop('settings.backup', None)
        import settings.backup as backup
        self.backup = backup

    def restore(self, data):
        return self.backup.restore_backup(data)

    def test_pushes_offset_and_steps_for_every_module_slot(self):
        self.settings['modules'] = {'0': {'homeOffset': 100, 'totalSteps': 2000}}
        self.restore({'version': 3, 'modules': {}})
        # NUM_MODULES comes from the real config.py; just check module 0's pair
        # of commands appear, each exactly once, before any toggle commands.
        self.assertIn('m00o100', self.sent)
        self.assertIn('m00t2000', self.sent)

    def test_pushes_toggles_present_in_the_restored_module(self):
        self.settings['modules'] = {}
        self.restore({'version': 3, 'modules': {
            '3': {'homeOffset': 480, 'totalSteps': 4096,
                  'autoHome': True, 'motorClockwise': False, 'motorRelease': True},
        }})
        for cmd in ('m03a1', 'm03w0', 'm03r1'):
            with self.subTest(cmd=cmd):
                self.assertIn(cmd, self.sent)

    def test_does_not_invent_toggle_values_for_a_backup_without_them(self):
        # Older backups (pre-toggle feature) only have homeOffset/totalSteps.
        self.settings['modules'] = {}
        self.restore({'version': 3, 'modules': {'4': {'homeOffset': 480, 'totalSteps': 4096}}})
        self.assertFalse([c for c in self.sent if c.startswith('m04') and c[3] in ('a', 'w', 'r')])

    def test_no_config_module_gets_no_toggle_commands_either(self):
        self.settings['modules'] = {}
        self.restore({'version': 3, 'modules': {}})
        self.assertFalse([c for c in self.sent if c.startswith('m00') and c[3] in ('a', 'w', 'r')])

    def test_non_boolean_toggle_value_is_not_pushed(self):
        # Defensive: a hand-edited or corrupted backup shouldn't crash restore
        # or coerce a stray string/number into a firmware command.
        self.settings['modules'] = {}
        self.restore({'version': 3, 'modules': {'2': {
            'homeOffset': 480, 'totalSteps': 4096, 'autoHome': 'yes', 'motorRelease': 1,
        }}})
        self.assertFalse([c for c in self.sent if c.startswith('m02') and c[3] in ('a', 'r')])

    def test_merges_into_existing_modules_rather_than_replacing(self):
        self.settings['modules'] = {'7': {'homeOffset': 1, 'totalSteps': 2,
                                           'autoHome': False, 'motorClockwise': False, 'motorRelease': False}}
        self.restore({'version': 3, 'modules': {'7': {'motorRelease': True}}})
        self.assertEqual(self.settings['modules']['7'],
                         {'homeOffset': 1, 'totalSteps': 2, 'autoHome': False,
                          'motorClockwise': False, 'motorRelease': True})

    def test_returns_false_and_sends_nothing_when_hardware_disconnected(self):
        self.connected = False
        self.settings['modules'] = {'0': {'homeOffset': 1, 'totalSteps': 2, 'autoHome': True}}
        result = self.restore({'version': 3, 'modules': {}})
        self.assertFalse(result)
        self.assertEqual(self.sent, [])

    def test_returns_true_when_hardware_connected(self):
        self.settings['modules'] = {}
        self.assertTrue(self.restore({'version': 3, 'modules': {}}))

    def test_settings_saved_exactly_once(self):
        self.restore({'version': 3, 'modules': {'0': {'autoHome': True}}})
        self.assertEqual(self.saves, 1)


if __name__ == '__main__':
    unittest.main()
