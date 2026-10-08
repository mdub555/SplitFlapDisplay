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

from apps.base import SettingField  # noqa: E402
from display.state import DisplayState  # noqa: E402


def _module(name, **attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    return mod


class SettingsRoutesTest(unittest.TestCase):
    def setUp(self):
        self.sent = []
        self.saves = 0
        self.state = DisplayState()
        self.settings = {'modules': {'1': {'autoHome': False}}, 'timezone': 'US/Eastern',
                         'saved_playlists': {}}

        def save_settings(_):
            self.saves += 1

        fakes = {
            'settings.store': _module('settings.store', settings=self.settings, save_settings=save_settings),
            'display.serial_link': _module('display.serial_link', send_raw=self.sent.append,
                                           is_connected=lambda: False, read_dump=None),
            'display.state': _module('display.state', state=self.state),
        }
        patcher = mock.patch.dict(sys.modules, fakes)
        patcher.start()
        self.addCleanup(patcher.stop)

        app = Flask(__name__)
        self.routes = {}
        for name in ('settings_routes', 'playlist_routes', 'control'):
            spec = importlib.util.spec_from_file_location(
                f'{name}_under_test', os.path.join(FRONTEND, 'routes', f'{name}.py'))
            routes = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(routes)
            app.register_blueprint(routes.bp)
            self.routes[name] = routes
        self.client = app.test_client()

    def test_get_settings(self):
        self.assertEqual(self.client.get('/settings').get_json()['timezone'], 'US/Eastern')

    def test_post_settings_only_stores_global_fields(self):
        res = self.client.post('/settings', json={'timezone': 'UTC', 'modules': 'nope'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.settings['timezone'], 'UTC')
        self.assertEqual(self.settings['modules'], {'1': {'autoHome': False}})
        self.assertEqual(self.saves, 1)

    def test_provisioning_needs_the_hardware(self):
        self.assertEqual(self.client.post('/provision_module', json={}).status_code, 503)

    def test_playlists_round_trip(self):
        self.assertEqual(self.client.get('/playlists').get_json(), {})
        res = self.client.post('/playlists', json={'name': ' Morning ', 'pages': ['HI'], 'delay': 3})
        self.assertEqual(res.get_json(), {'status': 'saved', 'name': 'Morning'})
        # A page sent as a plain string is stored as a page.
        self.assertEqual(self.client.get('/playlists').get_json(), {'Morning': {'pages': [{'text': 'HI'}], 'delay': 3}})
        self.client.delete('/playlists/Morning')
        self.assertEqual(self.client.get('/playlists').get_json(), {})

    def test_running_a_saved_playlist_plays_it_by_name(self):
        self.client.post('/playlists', json={'name': 'Morning', 'pages': ['HI', 'YO'], 'delay': '3'})
        res = self.client.post('/playlists/Morning/run')
        self.assertEqual(res.get_json(), {'status': 'running', 'name': 'Morning'})
        self.assertEqual(self.state.snapshot()['playlist'], {'name': 'Morning', 'page': 0, 'pages': 2})
        self.assertEqual(self.state.loop_delay, 3.0)

    def test_a_name_with_a_slash_runs_too(self):
        self.client.post('/playlists', json={'name': 'A/B', 'pages': ['HI']})
        self.assertEqual(self.client.post('/playlists/A/B/run').status_code, 200)
        self.assertEqual(self.state.playlist_name, 'A/B')

    def test_running_a_missing_playlist_is_a_404(self):
        self.assertEqual(self.client.post('/playlists/Nope/run').status_code, 404)

    def test_saving_the_playing_playlist_updates_the_display(self):
        self.client.post('/playlists', json={'name': 'Morning', 'pages': ['HI']})
        self.client.post('/playlists/Morning/run')
        self.client.post('/playlists', json={'name': 'Morning', 'pages': ['HI', 'THERE']})
        self.assertEqual(self.state.current_playlist, [{'text': 'HI'}, {'text': 'THERE'}])
        # Saving another one leaves the display alone.
        self.client.post('/playlists', json={'name': 'Other', 'pages': ['X']})
        self.assertEqual(self.state.playlist_name, 'Morning')

    def test_a_saved_playlist_is_stored_with_numbers(self):
        self.client.post('/playlists', json={'name': 'M', 'delay': '2.5', 'pages': [
            {'text': 'HI', 'delay': '3', 'style': 'rtl', 'speed': '20'}]})
        self.assertEqual(self.settings['saved_playlists']['M'], {
            'pages': [{'text': 'HI', 'delay': 3, 'style': 'rtl', 'speed': 20}], 'delay': 2.5})

    def test_a_bad_page_is_refused_with_the_reason(self):
        cases = [
            ({'delay': 'soon'}, 'Delay must be a number'),
            ({'delay': 0}, 'Delay must be more than 0 and at most 3600'),
            ({'pages': 'HI'}, 'Pages must be a list'),
            ({'pages': ['OK', {'text': 'X', 'delay': -1}]}, 'Page 2 delay must be more than 0 and at most 3600'),
            ({'pages': [{'text': 'X', 'speed': 2.5}]}, 'Page 1 speed must be a whole number of ms'),
            ({'pages': [{'text': 'X', 'speed': 900}]}, 'Page 1 speed must be at least 0 and at most 500'),
            ({'pages': [{'text': 'X', 'style': 'sideways'}]}, 'Page 1 has an unknown transition: sideways'),
            ({'pages': [{'delay': 5}]}, 'Page 1 needs its text'),
            ({'pages': [7]}, 'Page 1 must be an object'),
            ({'pages': [{'text': 'X', 'delay': True}]}, 'Page 1 delay must be a number'),
        ]
        for body, message in cases:
            with self.subTest(body=body):
                for url, extra in (('/playlists', {'name': 'Bad'}), ('/update_playlist', {})):
                    res = self.client.post(url, json={**body, **extra})
                    self.assertEqual(res.status_code, 400)
                    self.assertEqual(res.get_json()['message'], message)
        self.assertNotIn('Bad', self.settings['saved_playlists'])
        self.assertEqual(self.state.current_playlist, [])

    def test_pushing_a_playlist_plays_it(self):
        res = self.client.post('/update_playlist', json={'pages': [{'text': 'HI', 'delay': '4'}], 'delay': 6})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.state.current_playlist, [{'text': 'HI', 'delay': 4}])
        self.assertEqual(self.state.loop_delay, 6)

    def test_home_all_is_a_post(self):
        self.assertEqual(self.client.get('/home_all').status_code, 405)
        self.assertEqual(self.sent, [])
        self.assertEqual(self.client.post('/home_all').status_code, 200)
        self.assertEqual(self.sent, ['m*h'])

    def test_global_settings_are_type_checked(self):
        with mock.patch.object(self.routes['settings_routes'], 'GLOBAL_FIELDS', [
                SettingField('volume', 'Volume', type='number', default='5', min='0', max='10')]):
            self.assertEqual(self.client.post('/settings', json={'volume': '7'}).status_code, 200)
            self.assertEqual(self.settings['volume'], 7)
            res = self.client.post('/settings', json={'volume': 11})
            self.assertEqual((res.status_code, res.get_json()['message']), (400, 'Volume must be at most 10'))
            self.assertEqual(self.settings['volume'], 7)

    def test_deleting_answers_with_the_playlist_so_it_can_be_undone(self):
        self.client.post('/playlists', json={'name': 'Morning', 'pages': ['HI'], 'delay': 4})
        res = self.client.delete('/playlists/Morning')
        self.assertEqual(res.get_json()['playlist'], {'pages': [{'text': 'HI'}], 'delay': 4})
        self.assertIsNone(self.client.delete('/playlists/Morning').get_json()['playlist'])

    def rename(self, name, to):
        return self.client.post(f'/playlists/{name}/rename', json={'name': to})

    def test_renaming_keeps_its_place_and_its_pages(self):
        for name in ('A', 'B', 'C'):
            self.client.post('/playlists', json={'name': name, 'pages': [name]})
        res = self.rename('B', ' Bee ')
        self.assertEqual(res.get_json(), {'status': 'renamed', 'name': 'Bee', 'schedule_updated': 0})
        self.assertEqual(list(self.settings['saved_playlists']), ['A', 'Bee', 'C'])
        self.assertEqual(self.settings['saved_playlists']['Bee']['pages'], [{'text': 'B'}])

    def test_the_schedule_and_the_display_follow_a_rename(self):
        self.client.post('/playlists', json={'name': 'Morning', 'pages': ['HI']})
        self.settings['schedule'] = {'enabled': True, 'default': 'playlist:Morning', 'entries': [
            {'days': [0], 'start': '07:00', 'end': '09:00', 'target': 'playlist:Morning'},
            {'days': [0], 'start': '09:00', 'end': '10:00', 'target': 'app:time'}]}
        self.client.post('/playlists/Morning/run')
        res = self.rename('Morning', 'Dawn')
        self.assertEqual(res.get_json()['schedule_updated'], 2)
        self.assertEqual([e['target'] for e in self.settings['schedule']['entries']], ['playlist:Dawn', 'app:time'])
        self.assertEqual(self.settings['schedule']['default'], 'playlist:Dawn')
        self.assertEqual(self.state.playlist_name, 'Dawn')

    def test_a_rename_is_refused_when_it_would_clash_or_has_nothing_to_rename(self):
        for name in ('A', 'B'):
            self.client.post('/playlists', json={'name': name, 'pages': [name]})
        res = self.rename('A', 'B')
        self.assertEqual((res.status_code, res.get_json()['message']), (409, 'There is already a playlist called "B"'))
        self.assertEqual(self.rename('A', '  ').status_code, 400)
        self.assertEqual(self.rename('Nope', 'X').status_code, 404)
        self.assertEqual(list(self.settings['saved_playlists']), ['A', 'B'])

    def test_a_playlist_needs_a_name(self):
        res = self.client.post('/playlists', json={'name': '  '})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.get_json()['status'], 'error')


if __name__ == '__main__':
    unittest.main()
