"""Tests for the page and its configuration in routes/pages.py.

Run from frontend/:   python -m unittest tests.test_pages
"""
import json
import os
import re
import sys
import unittest

from flask import Flask

FRONTEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, FRONTEND)

from config import NUM_MODULES  # noqa: E402
from display.charset import FLAP_CHARS  # noqa: E402
from display.layout import STYLES  # noqa: E402
from display.debug_commands import DEBUG_COMMANDS  # noqa: E402
from display.module_protocol import GLOBAL_SETTINGS, MODULE_TOGGLES, Cmd  # noqa: E402
from routes import pages  # noqa: E402


class PageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = Flask(__name__, template_folder=os.path.join(FRONTEND, 'templates'),
                    static_folder=os.path.join(FRONTEND, 'static'))
        app.register_blueprint(pages.bp)
        cls.client = app.test_client()
        cls.html = cls.client.get('/').get_data(as_text=True)

    def test_every_firmware_setting_has_an_input(self):
        for key, spec in GLOBAL_SETTINGS.items():
            with self.subTest(key=key):
                self.assertIn(f'id="fw-{key}"', self.html)
                self.assertIn(spec['label'], self.html)

    def test_every_module_toggle_has_a_working_checkbox(self):
        # The attributes must come out as attributes, not escaped text.
        for key in MODULE_TOGGLES:
            with self.subTest(key=key):
                self.assertRegex(self.html, rf'id="modToggle-{key}"[^>]* data-onchange="toggleModuleSetting" '
                                            rf'data-setting="{key}"')

    def test_config_carries_what_the_scripts_read(self):
        config = json.loads(re.search(r'const CONFIG = (.*?);</script>', self.html).group(1))
        self.assertEqual(config['num_modules'], NUM_MODULES)
        self.assertEqual(config['flap_chars'], FLAP_CHARS)
        self.assertEqual([s['value'] for s in config['styles']], list(STYLES))
        self.assertEqual(config['display_chars']['q'], '"')
        self.assertEqual(len(config['color_tiles']), 8)

    def test_config_carries_what_the_preview_needs(self):
        config = json.loads(re.search(r'const CONFIG = (.*?);</script>', self.html).group(1))
        for style in config['styles']:
            with self.subTest(style=style['value']):
                self.assertEqual(sorted(style['order']), list(range(NUM_MODULES)))
        self.assertGreater(config['seconds_per_flap'], 0)
        self.assertGreater(config['bus_ms_per_module'], 0)

    def test_debug_page_offers_every_command(self):
        letters = {value for name, value in vars(Cmd).items() if not name.startswith('_')}
        offered = [command['cmd'] for command in DEBUG_COMMANDS if command['cmd']]
        self.assertEqual(set(offered), letters)
        self.assertEqual(len(offered), len(set(offered)), 'a command is offered twice')
        for command in DEBUG_COMMANDS:
            with self.subTest(command=command['key']):
                self.assertIn(f'<option value="{command["key"]}">', self.html)

    def test_the_page_can_be_installed_as_an_app(self):
        self.assertIn('<link rel="manifest" href="/manifest.webmanifest">', self.html)
        self.assertIn('apple-touch-icon', self.html)
        res = self.client.get('/manifest.webmanifest')
        self.assertEqual(res.mimetype, 'application/manifest+json')
        manifest = res.get_json(force=True)
        self.assertEqual((manifest['start_url'], manifest['display']), ('/', 'standalone'))
        self.assertIn('maskable', [icon['purpose'] for icon in manifest['icons']])
        for icon in manifest['icons']:
            with self.subTest(icon=icon['src']):
                self.assertTrue(os.path.exists(os.path.join(FRONTEND, icon['src'].lstrip('/'))))
        self.assertTrue(os.path.exists(os.path.join(FRONTEND, 'static/icons/apple-touch-icon.png')))

    def test_every_script_exists(self):
        scripts = re.findall(r'<script src="/(static/js/[^"]+)"', self.html)
        self.assertTrue(scripts)
        for src in scripts:
            with self.subTest(src=src):
                self.assertTrue(os.path.exists(os.path.join(FRONTEND, src)))


if __name__ == '__main__':
    unittest.main()
