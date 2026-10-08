"""Tests for the safety nets: the timezone falling back instead of breaking
every clock, and settings.json being written atomically.

Run from frontend/:   python -m unittest tests.test_robustness
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apps.builtin._shared import get_tz  # noqa: E402
from settings import store  # noqa: E402
from settings.schema import GLOBAL_FIELDS  # noqa: E402


class TimezoneTest(unittest.TestCase):
    def test_a_real_timezone_is_used(self):
        self.assertEqual(str(get_tz({'timezone': 'Europe/London'})), 'Europe/London')

    def test_an_unknown_one_falls_back_to_the_default(self):
        self.assertEqual(str(get_tz({'timezone': 'EST5'})), 'US/Eastern')
        self.assertEqual(str(get_tz({})), 'US/Eastern')

    def test_the_setting_only_takes_real_timezones(self):
        field = next(f for f in GLOBAL_FIELDS if f.key == 'timezone')
        self.assertEqual(field.clean('Asia/Tokyo'), 'Asia/Tokyo')
        self.assertIn(field.default, field.opts)
        with self.assertRaisesRegex(ValueError, '^Timezone: "Mars/Olympus" isn\'t one of the choices$'):
            field.clean('Mars/Olympus')


class AtomicSaveTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.path = os.path.join(self.folder, 'data', 'settings.json')   # its folder doesn't exist yet
        patcher = mock.patch.object(store, 'CONFIG_PATH', self.path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_saving_creates_the_folder_and_leaves_no_temporary_file(self):
        store.save_settings({'a': 1})
        with open(self.path) as f:
            self.assertEqual(json.load(f), {'a': 1})
        self.assertEqual(os.listdir(os.path.dirname(self.path)), ['settings.json'])

    def test_a_save_that_fails_part_way_leaves_the_old_file_whole(self):
        store.save_settings({'calibrated': True})
        with mock.patch.object(store.json, 'dump', side_effect=OSError('power cut')):
            with self.assertRaises(OSError):
                store.save_settings({'calibrated': False})
        with open(self.path) as f:
            self.assertEqual(json.load(f), {'calibrated': True})


if __name__ == '__main__':
    unittest.main()
