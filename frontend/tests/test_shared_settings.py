"""Tests for settings/shared.py: the settings every module shares, and
bringing an older settings.json up to date.

Run from frontend/:   python -m unittest tests.test_shared_settings
"""
import os
import sys
import unittest

FRONTEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, FRONTEND)

from settings.shared import current_firmware_values, migrate  # noqa: E402


class MigrateTest(unittest.TestCase):
    def test_old_auto_home_switch_becomes_a_shared_setting(self):
        stored = migrate({'auto_home': False, 'modules': {}})
        self.assertNotIn('auto_home', stored)
        self.assertIs(stored['firmware']['autoHome'], False)

    def test_release_motor_carries_over_when_every_module_agrees(self):
        stored = migrate({'modules': {'0': {'motorRelease': False}, '1': {'motorRelease': False}}})
        self.assertIs(stored['firmware']['motorRelease'], False)

    def test_release_motor_is_left_at_its_default_when_modules_disagree(self):
        stored = migrate({'modules': {'0': {'motorRelease': False}, '1': {'motorRelease': True}}})
        self.assertNotIn('firmware', stored)
        self.assertIs(current_firmware_values(stored)['motorRelease'], True)

    def test_an_existing_shared_value_wins(self):
        stored = migrate({'auto_home': False, 'firmware': {'autoHome': True, 'stepDelayUs': 1500}})
        self.assertEqual(stored['firmware'], {'autoHome': True, 'stepDelayUs': 1500})

    def test_up_to_date_settings_are_unchanged(self):
        stored = {'modules': {'0': {'homeOffset': 480}}, 'firmware': {'autoHome': False}}
        self.assertEqual(migrate(dict(stored)), stored)


if __name__ == '__main__':
    unittest.main()
