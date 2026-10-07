"""Tests for the SSE subscriber queues in display/state.py.

Run from frontend/:   python -m unittest tests.test_state
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from display.state import DisplayState  # noqa: E402


class StateSubscribersTest(unittest.TestCase):
    def setUp(self):
        self.state = DisplayState()

    def test_a_new_subscriber_starts_with_the_current_snapshot(self):
        q = self.state.subscribe()
        self.assertEqual(q.get_nowait(), self.state.snapshot())

    def test_a_slow_subscriber_only_keeps_the_latest_snapshot(self):
        q = self.state.subscribe()
        self.state.set_active_app('weather')
        self.state.set_active_app('time')
        self.assertEqual(q.get_nowait()['active_app'], 'time')
        self.assertTrue(q.empty())

    def test_unsubscribed_queues_get_nothing(self):
        q = self.state.subscribe()
        q.get_nowait()
        self.state.unsubscribe(q)
        self.state.set_active_app('weather')
        self.assertTrue(q.empty())


class PlayingTest(unittest.TestCase):
    """What the snapshot says is playing, and the run/stop helpers."""

    def setUp(self):
        self.state = DisplayState()

    def test_nothing_is_playing_at_first(self):
        snap = self.state.snapshot()
        self.assertIsNone(snap['playlist'])
        self.assertFalse(snap['scheduled'])
        self.assertFalse(snap['hardware_connected'])

    def test_a_playlist_reports_its_name_and_page(self):
        self.state.run_playlist(['A', 'B', 'C'], '3', 'Morning')
        self.state.set_playlist_page(2)
        self.assertEqual(self.state.snapshot()['playlist'], {'name': 'Morning', 'page': 2, 'pages': 3})
        self.assertEqual(self.state.loop_delay, 3.0)
        self.assertEqual(self.state.current_target(), 'playlist:Morning')

    def test_a_page_change_is_pushed_to_subscribers(self):
        self.state.run_playlist(['A', 'B'])
        q = self.state.subscribe()
        q.get_nowait()
        self.state.set_playlist_page(1)
        self.assertEqual(q.get_nowait()['playlist']['page'], 1)
        self.state.set_playlist_page(1)
        self.assertTrue(q.empty(), 'the same page again is not news')

    def test_a_bad_delay_falls_back_to_five_seconds(self):
        for delay in (None, '', 'abc', 0, -2):
            with self.subTest(delay=delay):
                self.state.run_playlist(['A'], delay)
                self.assertEqual(self.state.loop_delay, 5)

    def test_an_unsaved_playlist_is_no_target(self):
        self.state.run_playlist(['A'])
        self.assertIsNone(self.state.current_target())
        self.assertEqual(self.state.snapshot()['playlist']['name'], None)

    def test_running_an_app_replaces_the_playlist(self):
        self.state.run_playlist(['A'], 5, 'Morning')
        self.state.run_app('weather')
        snap = self.state.snapshot()
        self.assertEqual(snap['active_app'], 'weather')
        self.assertIsNone(snap['playlist'])
        self.assertTrue(self.state.stop_event.is_set())

    def test_stop_stops_a_playlist_too(self):
        self.state.run_playlist(['A', 'B'], 5, 'Morning')
        self.state.stop()
        self.assertIsNone(self.state.snapshot()['playlist'])
        self.assertEqual(self.state.current_playlist, [])

    def test_a_settings_save_is_pushed_to_subscribers(self):
        q = self.state.subscribe()
        self.assertEqual(q.get_nowait()['settings_version'], 0)
        self.state.settings_changed()
        self.assertEqual(q.get_nowait()['settings_version'], 1)

    def test_scheduled_only_while_the_scheduled_thing_runs(self):
        self.state.run_app('time')
        self.state.set_scheduled_target('app:time')
        self.assertTrue(self.state.snapshot()['scheduled'])
        self.state.run_app('weather')
        self.assertFalse(self.state.snapshot()['scheduled'])


class SerialSubscribersTest(unittest.TestCase):
    def setUp(self):
        self.state = DisplayState()

    def test_every_message_is_delivered_in_order(self):
        q = self.state.subscribe_serial()
        for msg in ('SENT: m05h', 'SENT: m05x', 'RECV: m05?'):
            self.state.log_serial(msg)
        self.assertEqual([q.get_nowait() for _ in range(3)], ['SENT: m05h', 'SENT: m05x', 'RECV: m05?'])

    def test_unsubscribed_queues_get_nothing(self):
        q = self.state.subscribe_serial()
        self.state.unsubscribe_serial(q)
        self.state.log_serial('SENT: m05h')
        self.assertTrue(q.empty())


if __name__ == '__main__':
    unittest.main()
