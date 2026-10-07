"""Tests for GET/POST /firmware_config in routes/firmware_routes.py: the
settings every module shares (step delays, debounce, auto-home, ...).

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

DEFAULTS = {'stepDelayUs': 1000, 'homingStepDelayUs': 1000, 'debounceMs': 50, 'recalculateHome': True,
            'rampStartDelayUs': 3000, 'rampSteps': 0, 'motorRelease': True, 'settleMs': 0,
            'autoHome': True, 'staggerMs': 150}


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
        self.settings['firmware'] = {'stepDelayUs': 4000}
        self.assertEqual(self.client.get('/firmware_config').get_json()['values'],
                         {**DEFAULTS, 'stepDelayUs': 4000})

    def test_get_ignores_the_old_millisecond_keys(self):
        # A settings.json from before the step delays moved to microseconds:
        # the old values must not be read as microseconds.
        self.settings['firmware'] = {'stepDelay': 2, 'homingStepDelay': 3, 'rampStartDelay': 4}
        self.assertEqual(self.client.get('/firmware_config').get_json()['values'], DEFAULTS)

    def test_get_describes_the_limits(self):
        limits = self.client.get('/firmware_config').get_json()['limits']
        self.assertEqual(limits['stepDelayUs'], {'type': 'int', 'min': 1, 'max': 65535})
        self.assertEqual(limits['rampStartDelayUs'], {'type': 'int', 'min': 1, 'max': 65535})
        self.assertEqual(limits['debounceMs'], {'type': 'int', 'min': 0, 'max': 65535})
        self.assertEqual(limits['recalculateHome']['type'], 'bool')

    # ---- POST: success ----------------------------------------------------

    def test_post_broadcasts_each_setting_saves_and_returns_values(self):
        body = {'stepDelayUs': 1250, 'homingStepDelayUs': 1800, 'debounceMs': 150, 'recalculateHome': False,
                'rampStartDelayUs': 6000, 'rampSteps': 40, 'motorRelease': False, 'settleMs': 120,
                'autoHome': False, 'staggerMs': 80}
        res = self.post(body)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()['values'], body)
        self.assertCountEqual(self.sent, ['m*S1250', 'm*H1800', 'm*D150', 'm*E0', 'm*R6000', 'm*L40',
                                          'm*F0', 'm*W120', 'm*A0', 'm*P80'])
        self.assertEqual(self.settings['firmware'], body)
        self.assertEqual(self.saves, 1)

    def test_post_boolean_true_sends_one(self):
        self.post({'recalculateHome': True})
        self.assertEqual(self.sent, ['m*E1'])

    def test_auto_home_and_release_motor_go_to_every_module(self):
        self.post({'autoHome': False, 'motorRelease': True})
        self.assertCountEqual(self.sent, ['m*A0', 'm*F1'])

    def test_non_boolean_auto_home_is_rejected(self):
        self.assert_rejected(self.post({'autoHome': 1}))

    def test_partial_post_sends_only_those_and_keeps_the_rest(self):
        self.settings['firmware'] = {'stepDelayUs': 4000, 'homingStepDelayUs': 5000,
                                     'debounceMs': 60, 'recalculateHome': False}
        self.post({'debounceMs': 0})
        self.assertEqual(self.sent, ['m*D0'])
        self.assertEqual(self.settings['firmware'],
                         {**DEFAULTS, 'stepDelayUs': 4000, 'homingStepDelayUs': 5000, 'debounceMs': 0,
                          'recalculateHome': False})

    def test_range_edges_are_accepted(self):
        body = {'stepDelayUs': 65535, 'homingStepDelayUs': 1, 'debounceMs': 0}
        self.assertEqual(self.post(body).status_code, 200)
        self.assertEqual(self.post({'debounceMs': 65535}).status_code, 200)
        self.assertEqual(self.post({'rampStartDelayUs': 1, 'rampSteps': 0, 'settleMs': 0}).status_code, 200)
        self.assertEqual(self.post({'rampStartDelayUs': 65535, 'rampSteps': 255, 'settleMs': 255}).status_code, 200)
        self.assertEqual(self.post({'staggerMs': 0}).status_code, 200)
        self.assertEqual(self.post({'staggerMs': 255}).status_code, 200)

    # ---- POST: rejected, nothing sent or saved ----------------------------

    def assert_rejected(self, res):
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.get_json()['status'], 'error')
        self.assertEqual(self.sent, [])
        self.assertEqual(self.saves, 0)
        self.assertNotIn('firmware', self.settings)

    def test_out_of_range_integers(self):
        for key, bad in [('stepDelayUs', 0), ('stepDelayUs', 65536), ('homingStepDelayUs', 0),
                         ('homingStepDelayUs', 65536), ('debounceMs', -1), ('debounceMs', 65536),
                         ('rampStartDelayUs', 0), ('rampStartDelayUs', 65536), ('rampSteps', -1),
                         ('rampSteps', 256), ('settleMs', -1), ('settleMs', 256),
                         ('staggerMs', -1), ('staggerMs', 256)]:
            with self.subTest(key=key, value=bad):
                self.assert_rejected(self.post({key: bad}))

    def test_non_integer_values(self):
        for bad in ('5', 1.5, True, None, [5]):
            with self.subTest(value=bad):
                self.assert_rejected(self.post({'stepDelayUs': bad}))

    def test_non_boolean_recalculate_home(self):
        for bad in (1, 0, 'true', None):
            with self.subTest(value=bad):
                self.assert_rejected(self.post({'recalculateHome': bad}))

    def test_unknown_key(self):
        self.assert_rejected(self.post({'bogus': 1}))

    def test_old_millisecond_keys_are_rejected(self):
        for key in ('stepDelay', 'homingStepDelay', 'rampStartDelay'):
            with self.subTest(key=key):
                self.assert_rejected(self.post({key: 1}))

    def test_one_bad_value_rejects_the_whole_request(self):
        self.assert_rejected(self.post({'stepDelayUs': 2000, 'debounceMs': 65536}))

    def test_empty_or_non_object_body(self):
        for body in ({}, [], [1], 'x'):
            with self.subTest(body=body):
                self.assert_rejected(self.post(body))


if __name__ == '__main__':
    unittest.main()
