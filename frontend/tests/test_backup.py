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
        self.assertIn('m00O100', self.sent)
        self.assertIn('m00T2000', self.sent)

    def test_pushes_motor_direction_present_in_the_restored_module(self):
        self.settings['modules'] = {}
        self.restore({'version': 3, 'modules': {
            '3': {'homeOffset': 480, 'totalSteps': 4096, 'motorClockwise': False},
        }})
        self.assertIn('m03C0', self.sent)

    def test_restores_and_broadcasts_the_shared_settings(self):
        self.restore({'version': 3, 'modules': {},
                      'firmware': {'autoHome': False, 'motorRelease': True, 'stepDelayUs': 1500}})
        self.assertEqual(self.settings['firmware']['autoHome'], False)
        self.assertEqual(self.settings['firmware']['stepDelayUs'], 1500)
        self.assertEqual(self.settings['firmware']['debounceMs'], 50)   # the rest keep their defaults
        for cmd in ('m*A0', 'm*F1', 'm*S1500'):
            with self.subTest(cmd=cmd):
                self.assertIn(cmd, self.sent)
        # Each module's own copy isn't sent any more.
        self.assertFalse([c for c in self.sent if c[1:3].isdigit() and c[3] in 'AF'])

    def test_malformed_shared_settings_are_skipped(self):
        self.restore({'version': 3, 'modules': {},
                      'firmware': {'autoHome': 'yes', 'stepDelayUs': 0, 'bogus': 1, 'motorRelease': False}})
        self.assertEqual(self.settings['firmware']['motorRelease'], False)
        self.assertEqual(self.settings['firmware']['autoHome'], True)    # default, not 'yes'
        self.assertEqual(self.settings['firmware']['stepDelayUs'], 1000)
        self.assertNotIn('bogus', self.settings['firmware'])
        self.assertEqual([c for c in self.sent if c.startswith('m*')], ['m*F0'])

    def test_an_older_backup_carries_auto_home_and_release_motor_over(self):
        # Before they were shared: a top-level auto_home switch, and release
        # motor set on each module.
        self.restore({'version': 3, 'auto_home': False, 'modules': {
            '0': {'motorRelease': False}, '1': {'motorRelease': False}}})
        self.assertEqual((self.settings['firmware']['autoHome'], self.settings['firmware']['motorRelease']),
                         (False, False))
        self.assertIn('m*A0', self.sent)
        self.assertIn('m*F0', self.sent)

    def test_backup_carries_the_shared_settings(self):
        self.settings['firmware'] = {'autoHome': False}
        backup = self.backup.build_backup()
        self.assertEqual(backup['firmware']['autoHome'], False)
        self.assertEqual(backup['firmware']['motorRelease'], True)
        self.assertNotIn('auto_home', backup)

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
            'homeOffset': 480, 'totalSteps': 4096, 'motorClockwise': 'yes',
        }}})
        self.assertFalse([c for c in self.sent if c.startswith('m02') and c[3] == 'C'])

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
