"""Tests for the manual-control endpoints in routes/module_routes.py:
/modules/<id>/total_steps, /modules/<id>/display and /modules/<id>/goto_step.

Run from frontend/:   python -m unittest tests.test_module_manual_controls

Loads the route module straight from its file with the settings store, serial
link and display state faked (same approach as test_module_routes.py), so
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


def _module(name, **attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    return mod


class ManualControlRoutesTest(unittest.TestCase):
    def setUp(self):
        self.sent = []      # every command written to the bus
        self.marked = []    # (module id, char) pairs pushed to the live display
        self.saves = 0
        self.settings = {'modules': {
            '5': {'homeOffset': 480, 'totalSteps': 4096,
                  'autoHome': False, 'motorClockwise': True, 'motorRelease': True},
        }}

        fakes = {
            'settings.store': _module('settings.store', settings=self.settings,
                                      save_settings=lambda _: setattr(self, 'saves', self.saves + 1)),
            'display.serial_link': _module('display.serial_link', send_raw=self.sent.append,
                                           read_dump=None, calibrate_module=None),
            'display.state': _module('display.state', state=types.SimpleNamespace(
                mark_module_char=lambda mod_id, char: self.marked.append((mod_id, char)))),
        }
        patcher = mock.patch.dict(sys.modules, fakes)
        patcher.start()
        self.addCleanup(patcher.stop)

        spec = importlib.util.spec_from_file_location(
            'module_routes_manual_under_test', os.path.join(FRONTEND, 'routes', 'module_routes.py'))
        routes = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(routes)
        self.routes = routes

        app = Flask(__name__)
        app.register_blueprint(routes.bp)
        self.client = app.test_client()

    def post(self, mod_id, action, body):
        return self.client.post(f'/modules/{mod_id}/{action}', json=body)

    def assert_rejected(self, res, status):
        self.assertEqual(res.status_code, status)
        self.assertEqual(res.get_json()['status'], 'error')
        self.assertEqual(self.sent, [])
        self.assertEqual(self.marked, [])
        self.assertEqual(self.saves, 0)

    # ---- total_steps ------------------------------------------------------

    def test_total_steps_sends_command_and_persists(self):
        res = self.post(5, 'total_steps', {'steps': 4100})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json(), {'status': 'success', 'steps': 4100})
        self.assertEqual(self.sent, ['m05t4100'])
        self.assertEqual(self.settings['modules']['5']['totalSteps'], 4100)
        self.assertEqual(self.saves, 1)

    def test_total_steps_only_changes_total_steps(self):
        self.post(5, 'total_steps', {'steps': 4100})
        mod = self.settings['modules']['5']
        self.assertEqual((mod['homeOffset'], mod['autoHome'], mod['motorClockwise']),
                         (480, False, True))

    def test_total_steps_bounds(self):
        for good in (1, 32767):
            with self.subTest(steps=good):
                self.assertEqual(self.post(5, 'total_steps', {'steps': good}).status_code, 200)

    def test_total_steps_rejects_bad_values(self):
        for bad in (0, -1, 32768, '4096', 1.5, True, None, [4096]):
            with self.subTest(steps=bad):
                self.assert_rejected(self.post(5, 'total_steps', {'steps': bad}), 400)

    def test_total_steps_missing(self):
        self.assert_rejected(self.post(5, 'total_steps', {}), 400)

    def test_total_steps_unprovisioned_module(self):
        self.assert_rejected(self.post(9, 'total_steps', {'steps': 4096}), 404)

    # ---- display ----------------------------------------------------------

    def test_display_char_normalisation(self):
        cases = [
            ('A', 'm05-A', 'A'),
            ('a', 'm05-A', 'A'),          # uppercased, like the compose page
            ('7', 'm05-7', '7'),
            (' ', 'm05- ', ' '),          # blank flap
            ('\U0001f7e5', 'm05-r', 'r'),  # red tile
            ('"', 'm05-q', 'q'),          # the quote flap travels as q
            ('\u00b0', 'm05-d', 'd'),      # degree sign
            ('\u2665', 'm05-h', 'h'),      # heart
        ]
        for typed, command, char in cases:
            with self.subTest(typed=typed):
                self.sent.clear()
                self.marked.clear()
                res = self.post(5, 'display', {'char': typed})
                self.assertEqual(res.status_code, 200)
                self.assertEqual(self.sent, [command])
                self.assertEqual(self.marked, [(5, char)])
                self.assertEqual(res.get_json()['char'], char)

    def test_display_char_rejects_unusable_input(self):
        # ';' has no flap on the v8 reels; 'AB' is two characters; 5 isn't a string.
        for bad in ('', 'AB', ';', "'", 5, None):
            with self.subTest(char=bad):
                self.assert_rejected(self.post(5, 'display', {'char': bad}), 400)

    def test_display_index(self):
        res = self.post(5, 'display', {'index': 7})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.sent, ['m05+7'])
        self.assertEqual(self.marked, [(5, 'G')])
        self.assertEqual(res.get_json(), {'status': 'success', 'char': 'G', 'index': 7})

    def test_display_index_bounds(self):
        for good in (0, 63):
            with self.subTest(index=good):
                self.assertEqual(self.post(5, 'display', {'index': good}).status_code, 200)
        for bad in (-1, 64, '7', 7.5, True, None):
            with self.subTest(index=bad):
                self.sent.clear()
                self.marked.clear()
                self.saves = 0
                self.assert_rejected(self.post(5, 'display', {'index': bad}), 400)

    def test_display_needs_exactly_one_of_char_or_index(self):
        self.assert_rejected(self.post(5, 'display', {}), 400)
        self.assert_rejected(self.post(5, 'display', {'char': 'A', 'index': 1}), 400)

    def test_display_unprovisioned_module(self):
        self.assert_rejected(self.post(9, 'display', {'char': 'A'}), 404)
        self.assert_rejected(self.post(9, 'display', {'index': 3}), 404)

    # ---- goto_step --------------------------------------------------------

    def test_goto_step_sends_command(self):
        res = self.post(5, 'goto_step', {'step': 512})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json(), {'status': 'success', 'step': 512})
        self.assertEqual(self.sent, ['m05g512'])
        self.assertEqual(self.saves, 0)  # a one-off move isn't a setting

    def test_goto_step_must_be_inside_one_revolution(self):
        self.assertEqual(self.post(5, 'goto_step', {'step': 0}).status_code, 200)
        self.assertEqual(self.post(5, 'goto_step', {'step': 4095}).status_code, 200)
        self.sent.clear()
        self.assert_rejected(self.post(5, 'goto_step', {'step': 4096}), 400)

    def test_goto_step_rejects_bad_values(self):
        for bad in (-1, '10', 1.5, True, None):
            with self.subTest(step=bad):
                self.assert_rejected(self.post(5, 'goto_step', {'step': bad}), 400)

    def test_goto_step_unprovisioned_module(self):
        self.assert_rejected(self.post(9, 'goto_step', {'step': 10}), 404)

    # ---- exercise / stop ----------------------------------------------------

    def test_exercise_sends_command(self):
        res = self.post(5, 'exercise', {'cycles': 3})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.sent, ['m05v3'])

    def test_exercise_bounds(self):
        for good in (1, 255):
            with self.subTest(cycles=good):
                self.assertEqual(self.post(5, 'exercise', {'cycles': good}).status_code, 200)
        self.sent.clear()
        for bad in (0, 256, -1, '3', 1.5, True, None):
            with self.subTest(cycles=bad):
                self.assert_rejected(self.post(5, 'exercise', {'cycles': bad}), 400)

    def test_exercise_unprovisioned_module(self):
        self.assert_rejected(self.post(9, 'exercise', {'cycles': 1}), 404)

    def test_stop_sends_command(self):
        self.assertEqual(self.post(5, 'stop', {}).status_code, 200)
        self.assertEqual(self.sent, ['m05x'])

    # ---- reboot / reset_settings -------------------------------------------

    def test_reboot_sends_command(self):
        self.assertEqual(self.post(5, 'reboot', {}).status_code, 200)
        self.assertEqual(self.sent, ['m05z'])
        self.assertEqual(self.saves, 0)

    def test_reset_settings_sends_command_then_stores_the_dump(self):
        dump = {'homeOffset': 480, 'totalSteps': 4096, 'autoHome': False,
                'motorClockwise': True, 'motorRelease': True}
        self.routes.REBOOT_WAIT_S = 0
        self.routes.read_dump = lambda mod_id: dump if mod_id == 5 else None
        res = self.post(5, 'reset_settings', {})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.sent, ['m05q'])
        self.assertEqual(self.settings['modules']['5'], dump)
        self.assertEqual(self.saves, 1)

    def test_reset_settings_without_a_reply_is_an_error(self):
        self.routes.REBOOT_WAIT_S = 0
        self.routes.read_dump = lambda mod_id: None
        res = self.post(5, 'reset_settings', {})
        self.assertEqual(res.status_code, 504)
        self.assertEqual(self.sent, ['m05q'])
        self.assertEqual(self.saves, 0)

    def test_reset_settings_unprovisioned_module(self):
        self.assert_rejected(self.post(9, 'reset_settings', {}), 404)

    # ---- identify ---------------------------------------------------------

    def test_identify_sends_command(self):
        res = self.post(5, 'identify', {})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.sent, ['m05f'])
        self.assertEqual(self.saves, 0)

    def test_identify_works_for_unprovisioned_ids(self):
        # Finding a module is useful before it's provisioned, too.
        self.assertEqual(self.post(255, 'identify', {}).status_code, 200)
        self.assertEqual(self.sent, ['m255f'])


if __name__ == '__main__':
    unittest.main()
