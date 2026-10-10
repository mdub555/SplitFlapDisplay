"""Tests for the flap offset endpoints in routes/module_routes.py:
/modules/<id>/flap_offsets, /modules/<id>/show_flap and
/modules/<id>/flap_offset.

Run from frontend/:   python -m unittest tests.test_flap_offset_routes

Loads the route module straight from its file with the serial link faked by
a small simulated module (same approach as test_module_routes.py), so
nothing here touches a serial port or settings.json.
"""
import importlib.util
import os
import re
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


class FakeModule:
    """Answers read_flap_offsets() as module 5 would: it shows the flaps
    it's sent, and sets the offset of the flap it's showing (except flap 0)."""

    def __init__(self):
        self.showing = None
        self.offsets = [0] * 64
        self.answers = True
        self.ignores_offsets = False  # as it does mid-move, say
        self.requests = []   # (messages sent before the dump, timeout)

    def read_flap_offsets(self, mod_id, before=(), timeout=5.0):
        self.requests.append((list(before), timeout))
        if mod_id != 5 or not self.answers:
            return None
        for msg in before:
            if m := re.fullmatch(r'm05\+(\d+)', msg):
                self.showing = int(m.group(1))
            elif (m := re.fullmatch(r'm05J(\d+)', msg)) and self.showing and not self.ignores_offsets:
                self.offsets[self.showing] = int(m.group(1)) - 128
        return list(self.offsets)


class FlapOffsetRoutesTest(unittest.TestCase):
    def setUp(self):
        self.module = FakeModule()
        self.marked = []
        fakes = {
            'settings.store': _module('settings.store', settings={'modules': {}}, save_settings=None),
            'display.serial_link': _module('display.serial_link', send_raw=None, read_dump=None,
                                           read_all_dumps=None, calibrate_module=None,
                                           read_flap_offsets=self.module.read_flap_offsets),
            'display.state': _module('display.state', state=types.SimpleNamespace(
                mark_module_char=lambda mod_id, char: self.marked.append((mod_id, char)))),
        }
        patcher = mock.patch.dict(sys.modules, fakes)
        patcher.start()
        self.addCleanup(patcher.stop)

        spec = importlib.util.spec_from_file_location(
            'module_routes_flap_offsets_under_test', os.path.join(FRONTEND, 'routes', 'module_routes.py'))
        routes = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(routes)
        app = Flask(__name__)
        app.register_blueprint(routes.bp)
        self.client = app.test_client()

    def post(self, path, body):
        return self.client.post(f'/modules/5/{path}', json=body)

    # ---- reading them ------------------------------------------------------

    def test_reads_every_flaps_offset(self):
        self.module.offsets[3] = -2
        res = self.client.get('/modules/5/flap_offsets')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()['offsets'][:4], [0, 0, 0, -2])
        self.assertEqual(self.module.requests, [([], 5.0)])

    def test_no_reply_is_a_gateway_timeout(self):
        self.module.answers = False
        self.assertEqual(self.client.get('/modules/5/flap_offsets').status_code, 504)

    # ---- showing a flap -----------------------------------------------------

    def test_showing_a_flap_waits_for_it_and_returns_the_offsets(self):
        res = self.post('show_flap', {'flap': 7})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()['flap'], 7)
        self.assertEqual(len(res.get_json()['offsets']), 64)
        # The dump is asked for straight after the move, and answered once
        # the module has stopped, so it gets long enough for a revolution.
        self.assertEqual(self.module.requests, [(['m05+7'], 15.0)])
        self.assertEqual(self.marked, [(5, 'G')])

    def test_showing_rejects_a_flap_that_does_not_exist(self):
        for bad in (-1, 64, '7', 7.5, True, None):
            with self.subTest(flap=bad):
                self.assertEqual(self.post('show_flap', {'flap': bad}).status_code, 400)
        self.assertEqual(self.module.requests, [])

    def test_showing_with_no_reply_is_a_gateway_timeout(self):
        self.module.answers = False
        self.assertEqual(self.post('show_flap', {'flap': 7}).status_code, 504)
        # It was sent all the same, so the live display follows it.
        self.assertEqual(self.marked, [(5, 'G')])

    # ---- setting an offset ------------------------------------------------

    def test_setting_an_offset_shows_the_flap_first_then_sets_it(self):
        res = self.post('flap_offset', {'flap': 7, 'offset': -3})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()['offsets'][7], -3)
        # The module only sets the flap showing's offset, and not mid-move,
        # so the flap is shown and waited for before the offset is sent.
        self.assertEqual([before for before, _ in self.module.requests], [['m05+7'], ['m05J125']])

    def test_the_whole_offset_range_is_accepted(self):
        for offset in (-128, 0, 127):
            with self.subTest(offset=offset):
                self.assertEqual(self.post('flap_offset', {'flap': 1, 'offset': offset}).status_code, 200)
                self.assertEqual(self.module.offsets[1], offset)

    def test_setting_rejects_bad_values(self):
        for body in ({'flap': 0, 'offset': 1}, {'flap': 64, 'offset': 1}, {'flap': 7, 'offset': -129},
                     {'flap': 7, 'offset': 128}, {'flap': 7, 'offset': '3'}, {'flap': 7}, {'offset': 3}):
            with self.subTest(body=body):
                self.assertEqual(self.post('flap_offset', body).status_code, 400)
        self.assertEqual(self.module.requests, [])

    def test_an_offset_the_module_did_not_take_is_a_conflict(self):
        self.module.ignores_offsets = True
        res = self.post('flap_offset', {'flap': 7, 'offset': 3})
        self.assertEqual(res.status_code, 409)
        self.assertIn('still at 0', res.get_json()['message'])

    def test_setting_with_no_reply_is_a_gateway_timeout(self):
        self.module.answers = False
        self.assertEqual(self.post('flap_offset', {'flap': 7, 'offset': 3}).status_code, 504)
        self.assertEqual(len(self.module.requests), 1)  # it stops after the first


if __name__ == '__main__':
    unittest.main()
