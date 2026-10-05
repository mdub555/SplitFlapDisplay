"""Tests for GET/POST /firmware_config in routes/firmware_routes.py: the
settings every module shares (step delays, debounce, recalculate-home).

Run from frontend/:   python -m unittest tests.test_firmware_routes

The route module is loaded straight from its file with the settings store and
serial link swapped for fakes (same approach as test_module_routes.py), so
nothing here touches a serial port or settings.json.
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

DEFAULTS = {'stepDelay': 1, 'homingStepDelay': 1, 'debounceMs': 100, 'recalculateHome': True}


def _module(name, **attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    return mod


class FirmwareRoutesTest(unittest.TestCase):
    def setUp(self):
        self.sent = []
        self.saves = 0
        self.settings = {'modules': {}}   # no 'firmware' key, like an old settings.json

        fakes = {
            'settings.store': _module('settings.store', settings=self.settings,
                                      save_settings=lambda _: setattr(self, 'saves', self.saves + 1)),
            'display.serial_link': _module('display.serial_link', send_raw=self.sent.append),
        }
        patcher = mock.patch.dict(sys.modules, fakes)
        patcher.start()
        self.addCleanup(patcher.stop)

        spec = importlib.util.spec_from_file_location(
            'firmware_routes_under_test', os.path.join(FRONTEND, 'routes', 'firmware_routes.py'))
        routes = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(routes)

        app = Flask(__name__)
        app.register_blueprint(routes.bp)
        self.client = app.test_client()

    def post(self, body):
        return self.client.post('/firmware_config', json=body)

    # ---- GET --------------------------------------------------------------

    def test_get_returns_defaults_when_nothing_is_stored(self):
        self.assertEqual(self.client.get('/firmware_config').get_json()['values'], DEFAULTS)

    def test_get_fills_gaps_in_a_partial_stored_dict(self):
        self.settings['firmware'] = {'stepDelay': 4}
        self.assertEqual(self.client.get('/firmware_config').get_json()['values'],
                         {**DEFAULTS, 'stepDelay': 4})

    def test_get_describes_the_limits(self):
        limits = self.client.get('/firmware_config').get_json()['limits']
        self.assertEqual(limits['stepDelay'], {'type': 'int', 'min': 1, 'max': 255})
        self.assertEqual(limits['debounceMs'], {'type': 'int', 'min': 0, 'max': 255})
        self.assertEqual(limits['recalculateHome']['type'], 'bool')

    # ---- POST: success ----------------------------------------------------

    def test_post_broadcasts_each_setting_saves_and_returns_values(self):
        body = {'stepDelay': 2, 'homingStepDelay': 3, 'debounceMs': 150, 'recalculateHome': False}
        res = self.post(body)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()['values'], body)
        self.assertCountEqual(self.sent, ['m*k2', 'm*l3', 'm*b150', 'm*j0'])
        self.assertEqual(self.settings['firmware'], body)
        self.assertEqual(self.saves, 1)

    def test_post_boolean_true_sends_one(self):
        self.post({'recalculateHome': True})
        self.assertEqual(self.sent, ['m*j1'])

    def test_partial_post_sends_only_those_and_keeps_the_rest(self):
        self.settings['firmware'] = {'stepDelay': 4, 'homingStepDelay': 5,
                                     'debounceMs': 60, 'recalculateHome': False}
        self.post({'debounceMs': 0})
        self.assertEqual(self.sent, ['m*b0'])
        self.assertEqual(self.settings['firmware'],
                         {'stepDelay': 4, 'homingStepDelay': 5, 'debounceMs': 0, 'recalculateHome': False})

    def test_range_edges_are_accepted(self):
        body = {'stepDelay': 255, 'homingStepDelay': 1, 'debounceMs': 0}
        self.assertEqual(self.post(body).status_code, 200)

    # ---- POST: rejected, nothing sent or saved ----------------------------

    def assert_rejected(self, res):
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.get_json()['status'], 'error')
        self.assertEqual(self.sent, [])
        self.assertEqual(self.saves, 0)
        self.assertNotIn('firmware', self.settings)

    def test_out_of_range_integers(self):
        for key, bad in [('stepDelay', 0), ('stepDelay', 256), ('homingStepDelay', 0),
                         ('debounceMs', -1), ('debounceMs', 256)]:
            with self.subTest(key=key, value=bad):
                self.assert_rejected(self.post({key: bad}))

    def test_non_integer_values(self):
        for bad in ('5', 1.5, True, None, [5]):
            with self.subTest(value=bad):
                self.assert_rejected(self.post({'stepDelay': bad}))

    def test_non_boolean_recalculate_home(self):
        for bad in (1, 0, 'true', None):
            with self.subTest(value=bad):
                self.assert_rejected(self.post({'recalculateHome': bad}))

    def test_unknown_key(self):
        self.assert_rejected(self.post({'bogus': 1}))

    def test_one_bad_value_rejects_the_whole_request(self):
        self.assert_rejected(self.post({'stepDelay': 2, 'debounceMs': 999}))

    def test_empty_or_non_object_body(self):
        for body in ({}, [], [1], 'x'):
            with self.subTest(body=body):
                self.assert_rejected(self.post(body))


if __name__ == '__main__':
    unittest.main()
