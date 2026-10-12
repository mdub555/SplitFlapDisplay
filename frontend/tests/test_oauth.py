"""Tests for signing in with OAuth (apps/oauth.py and routes/oauth_routes.py)
and the Spotify app that uses it. The services are faked; tokens go to a
temporary file.

Run from frontend/:   python -m unittest tests.test_oauth
"""
import base64
import hashlib
import os
import sys
import tempfile
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlparse

import requests
from flask import Flask

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apps import oauth  # noqa: E402
from apps.base import App, Grid, SettingField  # noqa: E402
from apps.builtin import spotify  # noqa: E402
from apps.registry import AppRegistry  # noqa: E402

PROVIDER = oauth.OAuthProvider(name='Service', authorize_url='https://service.test/authorize',
                               token_url='https://service.test/token', client_id_key='svc_client_id',
                               scopes=['read', 'write'])


class ServiceApp(App):
    key = 'svc'
    name = 'Service'
    settings_fields = [SettingField('svc_client_id', 'Client ID')]
    oauth = PROVIDER


def _token_response(status=200, **body):
    res = mock.Mock(ok=200 <= status < 300, status_code=status)
    res.json = lambda: body
    return res


class TokenFileTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        patcher = mock.patch.object(oauth, 'TOKENS_PATH', os.path.join(folder.name, 'oauth_tokens.json'))
        patcher.start()
        self.addCleanup(patcher.stop)
        oauth._pending.clear()
        self.app = ServiceApp()
        self.settings = {'svc_client_id': 'client-1'}

    def connect(self, **token):
        url, _ = oauth.start(self.app, self.settings, 'http://pi.local/apps/svc/oauth/callback')
        state = parse_qs(urlparse(url).query)['state'][0]
        body = {'access_token': 'A1', 'refresh_token': 'R1', 'expires_in': 3600, **token}
        with mock.patch.object(requests, 'post', return_value=_token_response(**body)) as post:
            oauth.finish(self.app, self.settings, 'the-code', state)
        return url, post


class OAuthTest(TokenFileTest):
    def test_the_authorize_url_uses_pkce(self):
        url, redirect = oauth.start(self.app, self.settings, 'http://pi.local/apps/svc/oauth/callback')
        query = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
        self.assertTrue(url.startswith('https://service.test/authorize?'))
        self.assertEqual(redirect, 'http://pi.local/apps/svc/oauth/callback')
        self.assertEqual((query['client_id'], query['scope'], query['code_challenge_method'], query['response_type']),
                         ('client-1', 'read write', 'S256', 'code'))
        verifier = oauth._pending[query['state']]['verifier']
        expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        self.assertEqual(query['code_challenge'], expected)

    def test_no_client_id_says_so(self):
        with self.assertRaisesRegex(oauth.OAuthError, 'Enter the Service Client ID first'):
            oauth.start(self.app, {}, 'http://x/cb')

    def test_finishing_keeps_the_tokens(self):
        _, post = self.connect()
        sent = post.call_args.kwargs['data']
        self.assertEqual((sent['grant_type'], sent['code'], sent['client_id'], sent['redirect_uri']),
                         ('authorization_code', 'the-code', 'client-1', 'http://pi.local/apps/svc/oauth/callback'))
        self.assertIn('code_verifier', sent)
        self.assertTrue(oauth.is_connected('svc'))
        self.assertEqual(oauth.access_token(self.app, self.settings), 'A1')
        self.assertEqual(os.stat(oauth.TOKENS_PATH).st_mode & 0o777, 0o600)

    def test_a_state_is_used_once(self):
        url, _ = oauth.start(self.app, self.settings, 'http://x/cb')
        state = parse_qs(urlparse(url).query)['state'][0]
        with mock.patch.object(requests, 'post', return_value=_token_response(access_token='A')):
            oauth.finish(self.app, self.settings, 'c', state)
            with self.assertRaisesRegex(oauth.OAuthError, 'expired'):
                oauth.finish(self.app, self.settings, 'c', state)

    def test_a_refused_exchange_says_why(self):
        url, _ = oauth.start(self.app, self.settings, 'http://x/cb')
        state = parse_qs(urlparse(url).query)['state'][0]
        refused = _token_response(400, error='invalid_grant', error_description='Invalid authorization code')
        with mock.patch.object(requests, 'post', return_value=refused):
            with self.assertRaisesRegex(oauth.OAuthError, 'Service refused: Invalid authorization code'):
                oauth.finish(self.app, self.settings, 'c', state)
        self.assertFalse(oauth.is_connected('svc'))

    def test_an_expired_token_is_refreshed(self):
        self.connect(expires_in=30)   # inside the minute's margin
        fresh = _token_response(access_token='A2', expires_in=3600)   # no new refresh token
        with mock.patch.object(requests, 'post', return_value=fresh) as post:
            self.assertEqual(oauth.access_token(self.app, self.settings), 'A2')
            self.assertEqual(oauth.access_token(self.app, self.settings), 'A2')   # no second refresh
        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args.kwargs['data']['refresh_token'], 'R1')
        self.assertEqual(oauth._load()['svc']['refresh_token'], 'R1')   # kept

    def test_a_failed_refresh_gives_no_token(self):
        self.connect(expires_in=0)
        with mock.patch.object(requests, 'post', return_value=_token_response(400, error='invalid_grant')):
            self.assertIsNone(oauth.access_token(self.app, self.settings))

    def test_disconnecting(self):
        self.connect()
        oauth.disconnect('svc')
        self.assertFalse(oauth.is_connected('svc'))
        self.assertIsNone(oauth.access_token(self.app, self.settings))

    def test_reading_the_code_from_the_address(self):
        self.assertEqual(oauth.code_from_url(' http://127.0.0.1:8888/callback?code=abc&state=xyz '), ('abc', 'xyz'))
        with self.assertRaisesRegex(oauth.OAuthError, 'refused: access_denied'):
            oauth.code_from_url('http://127.0.0.1:8888/callback?error=access_denied&state=xyz')
        with self.assertRaisesRegex(oauth.OAuthError, 'no sign-in code'):
            oauth.code_from_url('http://127.0.0.1:8888/callback')

    def test_the_registry_checks_the_client_id_field(self):
        class Broken(App):
            key = 'broken'
            oauth = PROVIDER
        with self.assertRaisesRegex(ValueError, "oauth needs a settings field 'svc_client_id'"):
            AppRegistry().register(Broken())


class RoutesTest(TokenFileTest):
    def setUp(self):
        super().setUp()
        from routes import oauth_routes
        self.routes = oauth_routes
        registry = AppRegistry()
        registry.register(self.app)
        for name, value in (('registry', registry), ('settings', self.settings)):
            patcher = mock.patch.object(oauth_routes, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        flask_app = Flask(__name__)
        flask_app.register_blueprint(oauth_routes.bp)
        self.client = flask_app.test_client()

    def test_connecting_through_the_callback(self):
        started = self.client.post('/apps/svc/oauth/start').get_json()
        self.assertFalse(started['paste'])
        self.assertEqual(started['redirect_uri'], 'http://localhost/apps/svc/oauth/callback')
        state = parse_qs(urlparse(started['authorize_url']).query)['state'][0]
        with mock.patch.object(requests, 'post', return_value=_token_response(access_token='A')):
            page = self.client.get(f'/apps/svc/oauth/callback?code=c&state={state}')
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'Service is connected', page.data)
        self.assertTrue(oauth.is_connected('svc'))

    def test_connecting_by_pasting_the_address(self):
        with mock.patch.object(PROVIDER, 'redirect_uri', 'http://127.0.0.1:8888/callback'):
            started = self.client.post('/apps/svc/oauth/start').get_json()
            self.assertTrue(started['paste'])
            state = parse_qs(urlparse(started['authorize_url']).query)['state'][0]
            bad = self.client.post('/apps/svc/oauth/finish', json={'url': 'http://127.0.0.1:8888/callback'})
            self.assertEqual(bad.status_code, 400)
            with mock.patch.object(requests, 'post', return_value=_token_response(access_token='A')):
                done = self.client.post('/apps/svc/oauth/finish',
                                        json={'url': f'http://127.0.0.1:8888/callback?code=c&state={state}'})
        self.assertEqual(done.get_json()['connected'], True)
        self.client.post('/apps/svc/oauth/disconnect')
        self.assertFalse(oauth.is_connected('svc'))

    def test_errors(self):
        self.assertEqual(self.client.post('/apps/nope/oauth/start').status_code, 404)
        self.settings.clear()
        reply = self.client.post('/apps/svc/oauth/start')
        self.assertEqual((reply.status_code, reply.get_json()['message']), (400, 'Enter the Service Client ID first'))


class SpotifyTest(unittest.TestCase):
    def playing(self, status=200, **body):
        res = mock.Mock(ok=200 <= status < 300, status_code=status, text='')
        res.json = lambda: body
        with mock.patch.object(requests, 'get', return_value=res) as get:
            track = spotify._fetch('T')
        self.assertEqual(get.call_args.kwargs['headers'], {'Authorization': 'Bearer T'})
        return track

    def test_a_track(self):
        track = self.playing(is_playing=True, item={'type': 'track', 'name': 'Here Comes the Sun - Remastered 2009',
                                                    'artists': [{'name': 'The Beatles'}]})
        self.assertEqual(track, {'playing': True, 'title': 'Here Comes the Sun', 'by': 'The Beatles'})

    def test_an_episode_and_nothing(self):
        track = self.playing(is_playing=False, item={'type': 'episode', 'name': 'Ep 1', 'show': {'name': 'A Show'}})
        self.assertEqual(track, {'playing': False, 'title': 'Ep 1', 'by': 'A Show'})
        self.assertIsNone(self.playing(204))
        self.assertIsNone(self.playing(is_playing=True, item=None))   # an ad
        self.assertEqual(self.playing(401), 'error')

    def test_cleaning_titles(self):
        for title, clean in (('Song (feat. Someone)', 'Song'), ('Song - 2011 Remaster', 'Song'),
                             ('Song - Live', 'Song - Live'), ('(feat. X)', '(feat. X)')):
            with self.subTest(title=title):
                self.assertEqual(spotify.clean_title(title), clean)

    def test_the_page(self):
        grid = Grid(4, 16)
        page = spotify.now_playing_page(grid, {'title': 'Here Comes the Sun', 'by': 'The Beatles'})
        self.assertEqual([page[i:i + 16] for i in range(0, 64, 16)],
                         [' HERE COMES THE ', '      SUN       ', ' ' * 16, '  THE BEATLES   '])
        page = spotify.now_playing_page(grid, {'title': 'Yesterday', 'by': 'The Beatles'})
        self.assertEqual([page[i:i + 16] for i in range(0, 64, 16)],
                         [' ' * 16, '   YESTERDAY    ', ' ' * 16, '  THE BEATLES   '])

    def test_not_connected(self):
        with mock.patch.object(spotify.SpotifyApp, 'access_token', return_value=None):
            frames = spotify.SpotifyApp().get_pages({}, {}, Grid(3, 15))
        self.assertIn('NOT CONNECTED', frames[0].text)


if __name__ == '__main__':
    unittest.main()
