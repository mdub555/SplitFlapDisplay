"""Tests for GET/POST /schedule in routes/schedule_routes.py.

Run from frontend/:   python -m unittest tests.test_schedule_routes

The route file is loaded with the settings store, app registry and the
scheduler's clock faked, so nothing reads settings.json or the real time.
"""
import importlib.util
import os
import sys
import types
import unittest
from datetime import datetime
from unittest import mock

from flask import Flask

FRONTEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, FRONTEND)

from display import scheduler as real_scheduler  # noqa: E402


def _module(name, **attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    return mod


class ScheduleRoutesTest(unittest.TestCase):
    def setUp(self):
        self.settings = {}
        self.saves = 0
        self.checks = 0

        def save_settings(_):
            self.saves += 1

        test = self

        class FakeScheduler:
            def check_soon(self):
                test.checks += 1

        apps = [types.SimpleNamespace(key='time'), types.SimpleNamespace(key='weather')]
        fake_scheduler = _module('display.scheduler', **{
            name: getattr(real_scheduler, name) for name in ('target_for', 'validate')})
        fake_scheduler.get_scheduler = FakeScheduler
        fake_scheduler.local_now = lambda settings: datetime(2026, 10, 6, 8, 5)   # a Tuesday
        fakes = {
            'settings.store': _module('settings.store', settings=self.settings, save_settings=save_settings),
            'apps.registry': _module('apps.registry', registry=types.SimpleNamespace(list_all=lambda: apps)),
            'display.scheduler': fake_scheduler,
        }
        patcher = mock.patch.dict(sys.modules, fakes)
        patcher.start()
        self.addCleanup(patcher.stop)

        spec = importlib.util.spec_from_file_location(
            'schedule_routes_under_test', os.path.join(FRONTEND, 'routes', 'schedule_routes.py'))
        routes = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(routes)
        app = Flask(__name__)
        app.register_blueprint(routes.bp)
        self.client = app.test_client()

    def test_no_schedule_yet_is_an_empty_one(self):
        self.assertEqual(self.client.get('/schedule').get_json(), {
            'schedule': {'enabled': False, 'default': '', 'entries': []},
            'now': 'Tue 08:05', 'current': ''})

    def test_saving_stores_it_and_checks_it_straight_away(self):
        body = {'enabled': True, 'default': 'app:time', 'entries': [
            {'days': [1], 'start': '08:00', 'end': '09:00', 'target': 'app:weather'}]}
        res = self.client.post('/schedule', json=body)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()['current'], 'app:weather')
        self.assertEqual(self.settings['schedule'], body)
        self.assertEqual((self.saves, self.checks), (1, 1))

    def test_a_bad_schedule_is_refused_and_not_stored(self):
        res = self.client.post('/schedule', json={'enabled': True, 'entries': [
            {'days': [1], 'start': '08:00', 'end': '09:00', 'target': ''}]})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.get_json()['message'], 'Entry 1 needs something to show')
        self.assertNotIn('schedule', self.settings)
        self.assertEqual((self.saves, self.checks), (0, 0))


if __name__ == '__main__':
    unittest.main()
