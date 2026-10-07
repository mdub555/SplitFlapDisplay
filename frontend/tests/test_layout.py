"""Tests for the animation orders in display/layout.py.

Run from frontend/:   python -m unittest tests.test_layout
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from display import layout  # noqa: E402


def grid(rows, cols):
    """Patch the grid size the orders are computed for."""
    return mock.patch.multiple(layout, GRID_ROWS=rows, GRID_COLS=cols, NUM_MODULES=rows * cols)


class AnimationOrderTest(unittest.TestCase):
    def test_every_style_sends_every_module_once(self):
        for rows, cols in [(4, 16), (3, 15), (1, 1), (1, 5), (5, 1), (2, 7), (6, 6)]:
            for style in layout.STYLES:
                with self.subTest(grid=f'{rows}x{cols}', style=style), grid(rows, cols):
                    self.assertEqual(sorted(layout.get_animation_order(style)), list(range(rows * cols)))

    def test_unknown_style_is_left_to_right(self):
        with grid(2, 3):
            self.assertEqual(layout.get_animation_order('bogus'), [0, 1, 2, 3, 4, 5])

    def test_orders_on_a_small_grid(self):
        # 2 rows of 3:   0 1 2
        #                3 4 5
        expected = {
            'rtl': [5, 4, 3, 2, 1, 0],
            'center_out': [1, 4, 0, 2, 3, 5],
            'outside_in': [5, 3, 2, 0, 4, 1],
            'spiral': [0, 1, 2, 5, 4, 3],
            'diagonal': [0, 1, 3, 2, 4, 5],
            'anti_diagonal': [2, 1, 5, 0, 4, 3],
            'reverse_rain': [3, 4, 5, 0, 1, 2],
            'columns': [0, 3, 1, 4, 2, 5],
            'columns_rtl': [2, 5, 1, 4, 0, 3],
            'alternating': [0, 5, 1, 4, 2, 3],
        }
        with grid(2, 3):
            for style, order in expected.items():
                with self.subTest(style=style):
                    self.assertEqual(layout.get_animation_order(style), order)

    def test_format_lines_centers_and_pads_rows(self):
        with grid(2, 4):
            self.assertEqual(layout.format_lines('AB'), ' AB     ')
            self.assertEqual(layout.format_lines('A', 'B', 'dropped'), ' A   B  ')


if __name__ == '__main__':
    unittest.main()
