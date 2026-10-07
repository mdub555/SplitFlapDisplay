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

from display.state import DisplayState  # noqa: E402


def _module(name, **attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    return mod


class ModuleRoutesTest(unittest.TestCase):
    def setUp(self):
        self.state = DisplayState()
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
                                           read_dump=None, read_all_dumps=None, calibrate_module=None),
            'display.state': _module('display.state', state=self.state),
        }
        patcher = mock.patch.dict(sys.modules, fakes)
        patcher.start()
        self.addCleanup(patcher.stop)

        spec = importlib.util.spec_from_file_location(
            'module_routes_under_test', os.path.join(FRONTEND, 'routes', 'module_routes.py'))
        routes = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(routes)
        self.routes = routes

        app = Flask(__name__)
        app.register_blueprint(routes.bp)
        self.client = app.test_client()

    def post(self, mod_id, body):
        return self.client.post(f'/modules/{mod_id}/setting', json=body)

    # ---- /modules/sync_all ------------------------------------------------

    def broadcast(self, dumps):
        """A read_all_dumps that answers with `dumps`, reporting each reply
        as it goes, and records what it was asked."""
        def read_all_dumps(max_id, on_reply=None):
            self.asked_max = max_id
            self.running_during = self.state.sync_running
            for mod_id, dump in dumps.items():
                if on_reply:
                    on_reply(mod_id, dump)
            return dumps
        self.routes.read_all_dumps = read_all_dumps

    def sync(self):
        return self.state.snapshot()['sync']

    def test_sync_all_uses_one_broadcast_and_stores_every_reply(self):
        self.settings['modules'] = {}
        self.broadcast({0: {'homeOffset': 1}, 7: {'homeOffset': 2}})
        self.routes.read_dump = lambda mod_id: self.fail('no individual reads needed')
        res = self.client.post('/modules/sync_all')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.asked_max, self.routes.NUM_MODULES - 1)
        self.assertEqual(self.settings['modules'], {'0': {'homeOffset': 1}, '7': {'homeOffset': 2}})
        self.assertEqual(self.saves, 1)
        self.assertEqual((res.get_json()['synced'], res.get_json()['failed']), ([0, 7], []))

    def test_sync_all_asks_provisioned_modules_that_missed_their_slot(self):
        self.settings['modules'] = {'3': {'homeOffset': 9}, '4': {'homeOffset': 9}}
        self.broadcast({4: {'homeOffset': 40}})
        asked = []
        self.routes.read_dump = lambda mod_id: asked.append(mod_id) or {'homeOffset': 30}
        self.client.post('/modules/sync_all')
        self.assertEqual(asked, [3])
        self.assertEqual(self.settings['modules'], {'3': {'homeOffset': 30}, '4': {'homeOffset': 40}})

    def test_sync_all_keeps_a_module_that_never_answers(self):
        self.settings['modules'] = {'3': {'homeOffset': 9}}
        self.broadcast({})
        self.routes.read_dump = lambda mod_id: None
        res = self.client.post('/modules/sync_all')
        self.assertEqual(self.settings['modules'], {'3': {'homeOffset': 9}})
        self.assertEqual(res.get_json()['failed'], [3])

    def test_sync_all_reports_progress_in_the_live_state(self):
        self.settings['modules'] = {'1': {}, '2': {}, '3': {}}
        self.broadcast({1: {'homeOffset': 1}})
        q = self.state.subscribe()
        q.get_nowait()
        self.routes.read_dump = lambda mod_id: {'homeOffset': 2} if mod_id == 2 else None
        self.client.post('/modules/sync_all')
        self.assertTrue(self.running_during)
        sync = self.sync()
        self.assertFalse(sync['running'])
        self.assertEqual(sorted(sync['ok']), ['1', '2'])
        self.assertEqual(sync['failed'], [3])
        self.assertFalse(q.empty(), 'progress was pushed to subscribers')

    def test_a_failed_module_stays_failed_until_it_syncs(self):
        self.settings['modules'] = {'3': {}}
        self.broadcast({})
        self.routes.read_dump = lambda mod_id: None
        self.client.post('/modules/sync_all')
        self.assertEqual(self.client.post('/modules/3/sync').status_code, 504)
        self.assertEqual(self.sync()['failed'], [3])
        self.routes.read_dump = lambda mod_id: {'homeOffset': 5}
        self.assertEqual(self.client.post('/modules/3/sync').status_code, 200)
        self.assertEqual((self.sync()['failed'], list(self.sync()['ok'])), ([], ['3']))

    def test_every_success_counts_anew_so_it_flashes_again(self):
        self.routes.read_dump = lambda mod_id: {'homeOffset': 5}
        self.client.post('/modules/5/sync')
        first = self.sync()['ok']['5']
        self.client.post('/modules/5/sync')
        self.assertGreater(self.sync()['ok']['5'], first)

    def test_sync_all_finishes_even_if_reading_fails(self):
        def broken(max_id, on_reply=None):
            raise OSError('unplugged')
        self.routes.read_all_dumps = broken
        self.assertEqual(self.client.post('/modules/sync_all').status_code, 500)
        self.assertFalse(self.sync()['running'])

    # ---- /adjust ----------------------------------------------------------

    def adjust(self, mod_id, delta):
        return self.client.post(f'/modules/{mod_id}/adjust', json={'delta': delta})

    def test_adjust_sends_new_offset_and_persists_it(self):
        res = self.adjust(5, 5)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json(), {'new_offset': 485})
        self.assertEqual(self.sent, ['m05O485'])
        self.assertEqual(self.settings['modules']['5']['homeOffset'], 485)
        self.assertEqual(self.saves, 1)

    def test_adjust_accepts_negative_deltas(self):
        self.assertEqual(self.adjust(5, -32).get_json(), {'new_offset': 448})
        self.assertEqual(self.sent, ['m05O448'])

    def test_adjust_must_keep_the_offset_inside_one_revolution(self):
        # 0 isn't allowed either: the firmware reads "O0" as "make here flap 0".
        for delta in (-480, -500, 4096 - 480):
            with self.subTest(delta=delta):
                res = self.adjust(5, delta)
                self.assertEqual(res.status_code, 400)
        self.assertEqual(self.adjust(5, 4095 - 480).get_json(), {'new_offset': 4095})
        self.assertEqual(self.sent, ['m05O4095'])

    def test_adjust_rejects_a_missing_or_non_integer_delta(self):
        for body in ({}, {'delta': '5'}, {'delta': 1.5}, {'delta': True}):
            with self.subTest(body=body):
                res = self.client.post('/modules/5/adjust', json=body)
                self.assertEqual(res.status_code, 400)
        self.assertEqual(self.sent, [])
        self.assertEqual(self.saves, 0)

    # ---- /sync and /calibrate failures ------------------------------------

    def test_sync_without_a_reply_is_a_504(self):
        self.routes.read_dump = lambda mod_id: None
        res = self.client.post('/modules/5/sync')
        self.assertEqual(res.status_code, 504)
        self.assertEqual(res.get_json()['status'], 'error')
        self.assertEqual(self.saves, 0)

    def test_sync_stores_the_reply(self):
        self.routes.read_dump = lambda mod_id: {'homeOffset': 7}
        res = self.client.post('/modules/9/sync')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.settings['modules']['9'], {'homeOffset': 7})

    def test_calibrate_timeout_is_a_504(self):
        self.routes.calibrate_module = lambda mod_id: None
        self.assertEqual(self.client.post('/modules/5/calibrate').status_code, 504)
        self.assertEqual(self.settings['modules']['5']['totalSteps'], 4096)

    def test_calibrate_stores_the_measurement(self):
        self.routes.calibrate_module = lambda mod_id: 4100
        res = self.client.post('/modules/5/calibrate')
        self.assertEqual(res.get_json(), {'status': 'success', 'steps': 4100})
        self.assertEqual(self.settings['modules']['5']['totalSteps'], 4100)

    def test_calibrate_unprovisioned_module_is_a_404(self):
        self.routes.calibrate_module = lambda mod_id: self.fail('must not calibrate')
        self.assertEqual(self.client.post('/modules/9/calibrate').status_code, 404)

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
            ('motorClockwise', True, 'm05C1'),
            ('motorClockwise', False, 'm05C0'),
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
        self.post(5, {'setting': 'motorClockwise', 'value': False})
        self.assertEqual(self.saves, 1)

    def test_only_the_requested_setting_changes(self):
        self.post(5, {'setting': 'motorClockwise', 'value': False})
        mod = self.settings['modules']['5']
        self.assertEqual((mod['autoHome'], mod['motorRelease'], mod['homeOffset']),
                         (False, True, 480))

    def test_three_digit_module_id_is_not_zero_padded_wrongly(self):
        self.post(123, {'setting': 'motorClockwise', 'value': False})
        self.assertEqual(self.sent, ['m123C0'])

    def test_settings_shared_by_every_module_are_not_set_per_module(self):
        # Auto-home and release-motor go to every module at once (/firmware_config).
        for setting in ('autoHome', 'motorRelease'):
            with self.subTest(setting=setting):
                self.assert_rejected(self.post(5, {'setting': setting, 'value': True}), 400)

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
        self.assert_rejected(self.post(5, {'setting': ['motorClockwise'], 'value': True}), 400)

    def test_non_boolean_values_are_rejected(self):
        # bool("false") is True in Python, so strings/ints must not be coerced.
        for bad in ('false', 'true', 0, 1, None):
            with self.subTest(value=bad):
                self.sent.clear()
                self.assert_rejected(self.post(5, {'setting': 'motorClockwise', 'value': bad}), 400)

    def test_missing_value(self):
        self.assert_rejected(self.post(5, {'setting': 'motorClockwise'}), 400)

    def test_unprovisioned_module(self):
        self.assert_rejected(self.post(9, {'setting': 'motorClockwise', 'value': True}), 404)


if __name__ == '__main__':
    unittest.main()
