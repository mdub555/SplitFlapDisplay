"""Tests for the app base classes in apps/.

Run from frontend/:   python -m unittest tests.test_apps
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apps.base import App, SettingField, clean_settings  # noqa: E402
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


class CleanTest(unittest.TestCase):
    """SettingField.clean(): values from the page as the field's type."""

    SPEED = SettingField('speed', 'Speed', type='number', default='0.4', min='0.1', max='5')

    def test_numbers(self):
        self.assertEqual(self.SPEED.clean('2'), 2)
        self.assertEqual(self.SPEED.clean(0.5), 0.5)
        self.assertEqual(self.SPEED.clean(''), 0.4)      # blank is the default
        self.assertEqual(self.SPEED.clean(None), 0.4)

    def test_bad_numbers_name_the_field(self):
        for value, message in (('fast', 'Speed must be a number'), (True, 'Speed must be a number'),
                               ('nan', 'Speed must be a number'), (0, 'Speed must be at least 0.1'),
                               (6, 'Speed must be at most 5'), ([1], 'Speed must be a number')):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, f'^{message}$'):
                    self.SPEED.clean(value)

    def test_checkboxes(self):
        box = SettingField('on', 'On', type='checkbox')
        self.assertIs(box.clean(True), True)
        self.assertIs(box.clean('false'), False)
        with self.assertRaisesRegex(ValueError, 'On must be on or off'):
            box.clean('yes')

    def test_selects_and_text(self):
        order = SettingField('order', 'Order', type='select', opts=['ltr', 'rtl'])
        self.assertEqual(order.clean('rtl'), 'rtl')
        with self.assertRaisesRegex(ValueError, 'Order must be one of: ltr, rtl'):
            order.clean('up')
        name = SettingField('name', 'Name')
        self.assertEqual(name.clean(42), '42')
        with self.assertRaisesRegex(ValueError, 'Name must be text'):
            name.clean({'a': 1})

    def test_clean_settings_keeps_only_the_fields(self):
        self.assertEqual(clean_settings([self.SPEED], {'speed': '1', 'other': 'x'}), {'speed': 1})


class SettingTest(unittest.TestCase):
    class Example(App):
        settings_fields = [SettingField('example_city', 'City', default='BOSTON')]

    def test_falls_back_to_the_field_default(self):
        self.assertEqual(self.Example().setting({}, 'example_city'), 'BOSTON')
        self.assertEqual(self.Example().setting({'example_city': 'NYC'}, 'example_city'), 'NYC')


if __name__ == '__main__':
    unittest.main()
