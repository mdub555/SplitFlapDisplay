"""Tests for display/player.py's send_to_display(): pages go out as one
frame broadcast (m*f...) when the firmware supports it, or one message per
module otherwise.

Run from frontend/:   python -m unittest tests.test_player

The player is loaded from its file with the serial link, display state, app
registry and settings store swapped for fakes, so nothing touches a serial
port or the real app registry.
"""
import importlib.util
import os
import sys
import threading
import types
import unittest
from unittest import mock

FRONTEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, FRONTEND)

from config import NUM_MODULES  # noqa: E402
from display.charset import FLAP_CHARS  # noqa: E402
from display.layout import get_animation_order  # noqa: E402


def _module(name, **attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    return mod


class FakeSerial:
    def __init__(self):
        self.written = []

    def write(self, data):
        self.written.append(data.decode())

    def flush(self):
        pass


class FakeState:
    def __init__(self):
        self.lock = threading.Lock()
        self.current_indices = [0] * NUM_MODULES
        self.shown = None

    def set_display(self, text, indices):
        self.shown = (text, indices)


class SendToDisplayTest(unittest.TestCase):
    def write_serial(self, data):
        if self.port_gone:
            return False
        self.ser.write(data.encode())
        return True

    def setUp(self):
        self.port_gone = False
        self.ser = FakeSerial()
        self.state = FakeState()
        fakes = {
            'display.serial_link': _module('display.serial_link', serial_lock=threading.Lock(),
                                           write_serial=self.write_serial),
            'display.state': _module('display.state', state=self.state),
            'apps.registry': _module('apps.registry', registry=None),
            'settings.store': _module('settings.store', settings={}),
        }
        patcher = mock.patch.dict(sys.modules, fakes)
        patcher.start()
        self.addCleanup(patcher.stop)

        spec = importlib.util.spec_from_file_location(
            'player_under_test', os.path.join(FRONTEND, 'display', 'player.py'))
        self.player = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.player)
        self.player.time = types.SimpleNamespace(sleep=lambda s: None, time=lambda: 0)

    def page(self, text):
        return text.ljust(NUM_MODULES)[:NUM_MODULES]

    # ---- frame_message ----------------------------------------------------

    def test_frame_message_pairs_each_module_with_its_rank(self):
        msg = self.player.frame_message('ABC', [2, 0, 1], 21)
        # module 0 is second in the order (rank 1), module 1 third, module 2 first
        self.assertEqual(msg, 'm*f21:A"B#C!\n')

    # ---- frame path -------------------------------------------------------

    def test_a_page_is_one_frame_broadcast(self):
        order = get_animation_order('rtl')
        self.player.send_to_display('HELLO', order, step_delay_ms=15)
        self.assertEqual(len(self.ser.written), 1)
        msg = self.ser.written[0]
        # 15 ms plus the ~6 ms one per-module message used to take on the bus
        self.assertTrue(msg.startswith('m*f21:'))
        pairs = msg[len('m*f21:'):-1]
        self.assertEqual(len(pairs), 2 * NUM_MODULES)
        text = self.page('HELLO')
        for i in range(NUM_MODULES):
            self.assertEqual(pairs[2 * i], text[i])
            self.assertEqual(ord(pairs[2 * i + 1]) - ord('!'), order.index(i))

    def test_frame_wait_covers_the_cascade_and_the_turn(self):
        busy_s = self.player.send_to_display('A', list(range(NUM_MODULES)), step_delay_ms=15)
        cascade = (NUM_MODULES - 1) * 21 / 1000.0
        turn = FLAP_CHARS.index('A') * self.player.SECONDS_PER_FLAP  # from flap 0
        self.assertAlmostEqual(busy_s, cascade + turn)

    def test_state_matches_the_page(self):
        self.player.send_to_display('HI', step_delay_ms=15)
        text, indices = self.state.shown
        self.assertEqual(text, self.page('HI'))
        self.assertEqual(indices[:3], [FLAP_CHARS.index('H'), FLAP_CHARS.index('I'), 0])

    # ---- one message per module -------------------------------------------

    def assert_one_message_per_module(self):
        self.assertEqual(len(self.ser.written), NUM_MODULES)
        self.assertEqual(self.ser.written[0], 'm00-H\n')
        self.assertEqual(self.ser.written[1], 'm01-I\n')

    def test_slow_speeds_fall_back_to_one_message_per_module(self):
        # 250 ms + bus time doesn't fit the frame's 255 ms interval
        busy_s = self.player.send_to_display('HI', step_delay_ms=250)
        self.assert_one_message_per_module()
        self.assertAlmostEqual(busy_s, FLAP_CHARS.index('I') * self.player.SECONDS_PER_FLAP)

    def test_frame_broadcast_can_be_turned_off(self):
        self.player.FRAME_BROADCAST = False
        self.player.send_to_display('HI', step_delay_ms=15)
        self.assert_one_message_per_module()

    # ---- when the port goes, or anything else goes wrong --------------------

    def test_no_port_means_no_waiting_on_the_bus(self):
        self.port_gone = True
        slept = []
        self.player.time = types.SimpleNamespace(sleep=slept.append, time=lambda: 0)
        self.player.send_to_display('HI', step_delay_ms=250)   # one message per module
        self.assertEqual(slept, [])
        self.assertEqual(self.state.shown[0], self.page('HI'))   # the page still shows on screen

    def test_the_playlist_loop_carries_on_after_an_error(self):
        class Stop(Exception):
            pass
        passes = []

        def play_once(cache):
            passes.append(1)
            raise RuntimeError('serial write failed')

        self.player._play_once = play_once
        self.player.time = types.SimpleNamespace(sleep=lambda s: None, time=lambda: 0)
        # Every error is logged and the loop goes round again. The test ends
        # it by having the second log call raise, which nothing catches.
        with mock.patch.object(self.player.logging, 'exception', side_effect=[None, Stop()]):
            with self.assertRaises(Stop):
                self.player.playlist_loop()
        self.assertEqual(len(passes), 2)

if __name__ == '__main__':
    unittest.main()
