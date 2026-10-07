"""Tests for the settings and saved-playlist endpoints in
routes/settings_routes.py and routes/playlist_routes.py.

Run from frontend/:   python -m unittest tests.test_settings_routes

The route modules are loaded straight from their files with the settings
store and serial link swapped for fakes.
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


class SettingsRoutesTest(unittest.TestCase):
    def setUp(self):
        self.sent = []
        self.saves = 0
        self.settings = {'modules': {'1': {'autoHome': False}}, 'timezone': 'US/Eastern',
                         'auto_home': False, 'saved_playlists': {}}

        def save_settings(_):
            self.saves += 1

        fakes = {
            'settings.store': _module('settings.store', settings=self.settings, save_settings=save_settings),
            'display.serial_link': _module('display.serial_link', send_raw=self.sent.append,
                                           is_connected=lambda: False, read_dump=None),
        }
        patcher = mock.patch.dict(sys.modules, fakes)
        patcher.start()
        self.addCleanup(patcher.stop)

        app = Flask(__name__)
        for name in ('settings_routes', 'playlist_routes'):
            spec = importlib.util.spec_from_file_location(
                f'{name}_under_test', os.path.join(FRONTEND, 'routes', f'{name}.py'))
            routes = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(routes)
            app.register_blueprint(routes.bp)
        self.client = app.test_client()

    def test_get_settings(self):
        self.assertEqual(self.client.get('/settings').get_json()['timezone'], 'US/Eastern')

    def test_post_settings_only_stores_global_fields(self):
        res = self.client.post('/settings', json={'timezone': 'UTC', 'modules': 'nope'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.settings['timezone'], 'UTC')
        self.assertEqual(self.settings['modules'], {'1': {'autoHome': False}})
        self.assertEqual(self.saves, 1)

    def test_toggle_autohome_updates_every_module_and_broadcasts(self):
        self.client.post('/toggle_autohome', json={'enabled': True})
        self.assertTrue(self.settings['auto_home'])
        self.assertTrue(self.settings['modules']['1']['autoHome'])
        self.assertEqual(self.sent, ['m*A1'])

    def test_provisioning_needs_the_hardware(self):
        self.assertEqual(self.client.post('/provision_module', json={}).status_code, 503)

    def test_playlists_round_trip(self):
        self.assertEqual(self.client.get('/playlists').get_json(), {})
        res = self.client.post('/playlists', json={'name': ' Morning ', 'pages': ['HI'], 'delay': 3})
        self.assertEqual(res.get_json(), {'status': 'saved', 'name': 'Morning'})
        self.assertEqual(self.client.get('/playlists').get_json(), {'Morning': {'pages': ['HI'], 'delay': 3}})
        self.client.delete('/playlists/Morning')
        self.assertEqual(self.client.get('/playlists').get_json(), {})

    def test_a_playlist_needs_a_name(self):
        res = self.client.post('/playlists', json={'name': '  '})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.get_json()['status'], 'error')


if __name__ == '__main__':
    unittest.main()
