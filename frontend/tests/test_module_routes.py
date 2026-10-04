"""Tests for the /modules/<id>/adjust and /modules/<id>/setting endpoints in
routes/module_routes.py.

Run from frontend/:   python -m unittest tests.test_module_routes

The route module is loaded straight from its file (not via the `routes`
package, whose __init__ imports every blueprint) with the settings store and
serial link swapped for fakes, so nothing here touches a serial port or
settings.json.
"""
import importlib.util
import os
import sys
import types
import unittest
from unittest import mock

from flask import Flask

FRONTEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, FRONTEND)


def _module(name, **attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    return mod


class ModuleRoutesTest(unittest.TestCase):
    def setUp(self):
        self.sent = []       # every command the route wrote to the bus
        self.saves = 0       # times settings were persisted
        self.settings = {'modules': {
            '5': {'homeOffset': 480, 'totalSteps': 4096,
                  'autoHome': False, 'motorClockwise': True, 'motorRelease': True},
            '123': {'homeOffset': 480, 'totalSteps': 4096,
                    'autoHome': False, 'motorClockwise': True, 'motorRelease': True},
        }}

        def save_settings(_):
            self.saves += 1

        fakes = {
            'settings.store': _module('settings.store', settings=self.settings,
                                      save_settings=save_settings),
            'display.serial_link': _module('display.serial_link', send_raw=self.sent.append,
                                           read_dump=None, calibrate_module=None),
            'display.state': _module('display.state', state=None),
        }
        patcher = mock.patch.dict(sys.modules, fakes)
        patcher.start()
        self.addCleanup(patcher.stop)

        spec = importlib.util.spec_from_file_location(
            'module_routes_under_test', os.path.join(FRONTEND, 'routes', 'module_routes.py'))
        routes = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(routes)

        app = Flask(__name__)
        app.register_blueprint(routes.bp)
        self.client = app.test_client()

    def post(self, mod_id, body):
        return self.client.post(f'/modules/{mod_id}/setting', json=body)

    # ---- /adjust ----------------------------------------------------------

    def adjust(self, mod_id, delta):
        return self.client.post(f'/modules/{mod_id}/adjust', json={'delta': delta})

    def test_adjust_sends_new_offset_and_persists_it(self):
        res = self.adjust(5, 5)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json(), {'new_offset': 485})
        self.assertEqual(self.sent, ['m05o485'])
        self.assertEqual(self.settings['modules']['5']['homeOffset'], 485)
        self.assertEqual(self.saves, 1)

    def test_adjust_accepts_negative_deltas(self):
        self.assertEqual(self.adjust(5, -32).get_json(), {'new_offset': 448})
        self.assertEqual(self.sent, ['m05o448'])

    def test_adjust_unprovisioned_module_is_a_404_not_a_fake_success(self):
        # This used to return 200 {"status": "failed"}, which the client
        # didn't check and treated as success.
        res = self.adjust(9, 5)
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.get_json(), {'status': 'error', 'message': 'Unprovisioned module'})
        self.assertEqual(self.sent, [])
        self.assertEqual(self.saves, 0)
        self.assertNotIn('9', self.settings['modules'])

    # ---- /setting: right firmware command, value persisted ----------------

    def test_each_setting_sends_its_firmware_command(self):
        cases = [
            ('autoHome', True, 'm05a1'),
            ('autoHome', False, 'm05a0'),
            ('motorClockwise', True, 'm05w1'),
            ('motorClockwise', False, 'm05w0'),
            ('motorRelease', True, 'm05r1'),
            ('motorRelease', False, 'm05r0'),
        ]
        for setting, value, expected in cases:
            with self.subTest(setting=setting, value=value):
                self.sent.clear()
                res = self.post(5, {'setting': setting, 'value': value})
                self.assertEqual(res.status_code, 200)
                self.assertEqual(self.sent, [expected])
                self.assertEqual(res.get_json(),
                                 {'status': 'success', 'setting': setting, 'value': value})
                self.assertIs(self.settings['modules']['5'][setting], value)

    def test_success_persists_settings(self):
        self.post(5, {'setting': 'autoHome', 'value': True})
        self.assertEqual(self.saves, 1)

    def test_only_the_requested_setting_changes(self):
        self.post(5, {'setting': 'autoHome', 'value': True})
        mod = self.settings['modules']['5']
        self.assertEqual((mod['motorClockwise'], mod['motorRelease'], mod['homeOffset']),
                         (True, True, 480))

    def test_three_digit_module_id_is_not_zero_padded_wrongly(self):
        self.post(123, {'setting': 'motorRelease', 'value': False})
        self.assertEqual(self.sent, ['m123r0'])

    # ---- rejected requests: nothing sent, nothing saved -------------------

    def assert_rejected(self, res, status):
        self.assertEqual(res.status_code, status)
        self.assertEqual(res.get_json()['status'], 'error')
        self.assertEqual(self.sent, [])
        self.assertEqual(self.saves, 0)

    def test_unknown_setting(self):
        self.assert_rejected(self.post(5, {'setting': 'homeOffset', 'value': True}), 400)

    def test_missing_setting(self):
        self.assert_rejected(self.post(5, {'value': True}), 400)

    def test_unhashable_setting_is_a_400_not_a_crash(self):
        self.assert_rejected(self.post(5, {'setting': ['autoHome'], 'value': True}), 400)

    def test_non_boolean_values_are_rejected(self):
        # bool("false") is True in Python, so strings/ints must not be coerced.
        for bad in ('false', 'true', 0, 1, None):
            with self.subTest(value=bad):
                self.sent.clear()
                self.assert_rejected(self.post(5, {'setting': 'autoHome', 'value': bad}), 400)

    def test_missing_value(self):
        self.assert_rejected(self.post(5, {'setting': 'autoHome'}), 400)

    def test_unprovisioned_module(self):
        self.assert_rejected(self.post(9, {'setting': 'autoHome', 'value': True}), 404)


if __name__ == '__main__':
    unittest.main()
