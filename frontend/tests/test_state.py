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
