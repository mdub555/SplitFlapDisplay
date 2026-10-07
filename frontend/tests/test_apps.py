"""Tests for the app base classes in apps/.

Run from frontend/:   python -m unittest tests.test_apps
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apps.base import App, SettingField  # noqa: E402
from apps.builtin.animations.base import AnimationApp  # noqa: E402
from display.layout import STYLES  # noqa: E402


class Sparkle(AnimationApp):
    key = 'anim_test'
    default_speed = '0.3'
    min_speed = 0.2

    def frames(self):
        return ['AB', 'CD']


class Fixed(AnimationApp):
    key = 'anim_fixed'
    fixed_style = 'random'

    def frames(self):
        return ['AB']


class AnimationAppTest(unittest.TestCase):
    def test_settings_fields_are_built_from_the_key(self):
        style, speed = Sparkle.settings_fields
        self.assertEqual((style.key, style.type, style.opts), ('anim_test_style', 'select', list(STYLES)))
        self.assertEqual((speed.key, speed.default, speed.min), ('anim_test_speed', '0.3', '0.2'))

    def test_a_fixed_style_has_no_style_setting(self):
        self.assertEqual([f.key for f in Fixed.settings_fields], ['anim_fixed_speed'])

    def test_frames_use_the_settings(self):
        frames = Sparkle().get_pages({'anim_test_style': 'spiral', 'anim_test_speed': '0.5'}, {})
        self.assertEqual([(f.text, f.delay, f.style, f.raw) for f in frames],
                         [('AB', 0.5, 'spiral', True), ('CD', 0.5, 'spiral', True)])

    def test_defaults_and_the_minimum_speed(self):
        self.assertEqual(Sparkle().get_pages({}, {})[0].delay, 0.3)
        self.assertEqual(Sparkle().get_pages({'anim_test_speed': '0.01'}, {})[0].delay, 0.2)
        self.assertEqual(Fixed().get_pages({}, {})[0].style, 'random')


class SettingTest(unittest.TestCase):
    class Example(App):
        settings_fields = [SettingField('example_city', 'City', default='BOSTON')]

    def test_falls_back_to_the_field_default(self):
        self.assertEqual(self.Example().setting({}, 'example_city'), 'BOSTON')
        self.assertEqual(self.Example().setting({'example_city': 'NYC'}, 'example_city'), 'NYC')


if __name__ == '__main__':
    unittest.main()
