"""Tests for the app base classes in apps/.

Run from frontend/:   python -m unittest tests.test_apps
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apps.base import App, Frame, Grid, SettingField, clean_settings  # noqa: E402
from apps.registry import AppRegistry, discover, registry  # noqa: E402
from apps.builtin.animations.base import AnimationApp  # noqa: E402
from display.layout import STYLES  # noqa: E402


GRID = Grid(3, 15)


class Sparkle(AnimationApp):
    key = 'anim_test'
    default_speed = '0.3'
    min_speed = 0.2

    def frames(self, grid):
        return ['AB', 'CD']


class Fixed(AnimationApp):
    key = 'anim_fixed'
    fixed_style = 'random'

    def frames(self, grid):
        return ['AB']


class AnimationAppTest(unittest.TestCase):
    def test_settings_fields_are_built_from_the_key(self):
        style, speed = Sparkle.settings_fields
        self.assertEqual((style.key, style.type, style.opts), ('anim_test_style', 'select', list(STYLES)))
        self.assertEqual((speed.key, speed.default, speed.min), ('anim_test_speed', '0.3', '0.2'))

    def test_a_fixed_style_has_no_style_setting(self):
        self.assertEqual([f.key for f in Fixed.settings_fields], ['anim_fixed_speed'])

    def test_frames_use_the_settings(self):
        frames = Sparkle().get_pages({'anim_test_style': 'spiral', 'anim_test_speed': '0.5'}, {}, GRID)
        self.assertEqual([(f.text, f.delay, f.style, f.raw) for f in frames],
                         [('AB', 0.5, 'spiral', True), ('CD', 0.5, 'spiral', True)])

    def test_defaults_and_the_minimum_speed(self):
        self.assertEqual(Sparkle().get_pages({}, {}, GRID)[0].delay, 0.3)
        self.assertEqual(Sparkle().get_pages({'anim_test_speed': '0.01'}, {}, GRID)[0].delay, 0.2)
        self.assertEqual(Fixed().get_pages({}, {}, GRID)[0].style, 'random')


class GridTest(unittest.TestCase):
    """Grid: pages built to fit the display, whatever its size."""

    def lines(self, grid, page):
        return [page[i:i + grid.cols] for i in range(0, grid.size, grid.cols)]

    def test_a_page_is_centred_both_ways(self):
        grid = Grid(4, 6)
        self.assertEqual(self.lines(grid, grid.page('AB', 'C')), ['      ', '  AB  ', '  C   ', '      '])
        grid = Grid(3, 6)
        self.assertEqual(self.lines(grid, grid.page('AB')), ['      ', '  AB  ', '      '])

    def test_a_page_never_overflows(self):
        grid = Grid(2, 4)
        self.assertEqual(grid.page('ABCDEF', 'G', 'H'), 'ABCD G  ')
        self.assertEqual(grid.page(), ' ' * 8)

    def test_cells(self):
        self.assertEqual(Grid(2, 3).cells(lambda r, c: str(r * 3 + c)), '012345')

    def test_wrap_breaks_between_words_and_stops_at_the_rows(self):
        grid = Grid(2, 8)
        self.assertEqual(grid.wrap('ONE TWO THREE FOUR'), ['ONE TWO', 'THREE'])
        self.assertEqual(grid.wrap('ONE TWO THREE FOUR', max_lines=1), ['ONE TWO'])
        self.assertEqual(grid.wrap('ABCDEFGHIJ'), ['ABCDEFGH', 'IJ'])
        self.assertEqual(grid.wrap(''), [''])

    def test_chunks_are_a_row_each_by_default(self):
        self.assertEqual(Grid(2, 8).chunks([1, 2, 3]), [[1, 2], [3]])
        self.assertEqual(Grid(2, 8).chunks([1, 2, 3], per_page=3), [[1, 2, 3]])


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

    def test_global_fields_fall_back_too(self):
        self.assertEqual(self.Example().setting({}, 'timezone'), 'US/Eastern')

    def test_an_unknown_setting_says_so(self):
        with self.assertRaisesRegex(KeyError, "Example has no setting 'nope'"):
            self.Example().setting({}, 'nope')


def _app(key, fields=(), uses=()):
    return type(f'App_{key}', (App,), {'key': key, 'name': key, 'settings_fields': list(fields),
                                       'global_settings': list(uses)})()


class RegistryTest(unittest.TestCase):
    """AppRegistry.register() refuses an app that would clash with another."""

    def test_a_duplicate_key(self):
        reg = AppRegistry()
        reg.register(_app('one'))
        with self.assertRaisesRegex(ValueError, "app key 'one' is already used"):
            reg.register(_app('one'))

    def test_a_missing_key(self):
        with self.assertRaisesRegex(ValueError, 'has no key'):
            AppRegistry().register(_app(''))

    def test_a_setting_another_app_uses(self):
        reg = AppRegistry()
        reg.register(_app('one', [SettingField('city', 'City')]))
        with self.assertRaisesRegex(ValueError, "setting 'city' is already used by App_one"):
            reg.register(_app('two', [SettingField('city', 'City')]))

    def test_a_global_or_reserved_setting(self):
        for key in ('timezone', 'modules'):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, f"setting '{key}' is already used"):
                AppRegistry().register(_app('one', [SettingField(key, 'X')]))

    def test_an_unknown_global_setting(self):
        with self.assertRaisesRegex(ValueError, r"unknown fields \['yt_nope'\]"):
            AppRegistry().register(_app('one', uses=['yt_nope']))

    def test_the_order_then_the_name(self):
        reg = AppRegistry()
        for key, order in (('b', 5), ('a', 5), ('c', 1)):
            app = _app(key)
            app.order = order
            reg.register(app)
        self.assertEqual([a.key for a in reg.list_all()], ['c', 'a', 'b'])

    def test_clearing_the_caches(self):
        reg = AppRegistry()
        reg.cache_for('one')['x'] = 1
        self.assertEqual(reg.cache_for('one'), {'x': 1})
        reg.clear_caches()
        self.assertEqual(reg.cache_for('one'), {})


class BuiltinAppsTest(unittest.TestCase):
    """Every app under apps/builtin/: found, and well-formed. A new app gets
    these checks just by being there."""

    def test_discovery_finds_the_apps_but_not_bases_or_disabled_ones(self):
        keys = {cls.key for cls in discover()}
        self.assertIn('weather', keys)
        self.assertIn('anim_rainbow', keys)   # in a sub-package
        self.assertNotIn('stocks', keys)      # enabled = False
        self.assertNotIn(AnimationApp, discover())

    def test_every_app_is_described(self):
        for app in registry.list_all():
            with self.subTest(app=app.key):
                self.assertTrue(app.name and app.icon and app.desc)

    def test_every_app_fills_the_display_offline(self):
        # No network: every request fails, as it would with the Pi offline.
        # An app may catch that or not (the player shows an error page), but
        # anything else going wrong is a bug. It's tried at a few sizes, as
        # apps mustn't assume one, and every page must be exactly the size
        # of the display.
        import requests
        from settings.store import build_defaults
        settings = build_defaults()
        with mock.patch.object(requests, 'get', side_effect=requests.ConnectionError('offline')):
            for grid in (Grid(4, 16), Grid(3, 15), Grid(2, 10)):
                for app in registry.list_all():
                    with self.subTest(app=app.key, grid=grid):
                        try:
                            frames = app.get_pages(settings, {}, grid)
                        except requests.ConnectionError:
                            continue
                        self.assertIsInstance(frames, list)
                        for frame in frames:
                            self.assertIsInstance(frame, Frame)
                            self.assertEqual(len(frame.text), grid.size)


if __name__ == '__main__':
    unittest.main()
