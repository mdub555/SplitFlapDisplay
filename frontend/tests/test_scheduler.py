"""Tests for the schedule in display/scheduler.py: which time slot covers a
moment, checking a schedule the page sends, and the scheduler only acting
when what the schedule calls for changes.

Run from frontend/:   python -m unittest tests.test_scheduler
"""
import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from display.scheduler import Scheduler, entry_covers, target_for, validate  # noqa: E402
from display.state import DisplayState  # noqa: E402

WEEKDAYS = [0, 1, 2, 3, 4]


def at(day, time):
    """A moment in the week of Monday 2026-10-05: day 0 is Monday."""
    hour, minute = map(int, time.split(':'))
    return datetime(2026, 10, 5 + day, hour, minute)


def slot(start, end, days=WEEKDAYS, target='app:time'):
    return {'days': days, 'start': start, 'end': end, 'target': target}


class EntryCoversTest(unittest.TestCase):
    def test_a_slot_covers_its_start_but_not_its_end(self):
        entry = slot('07:00', '09:30')
        self.assertFalse(entry_covers(entry, at(0, '06:59')))
        self.assertTrue(entry_covers(entry, at(0, '07:00')))
        self.assertTrue(entry_covers(entry, at(0, '09:29')))
        self.assertFalse(entry_covers(entry, at(0, '09:30')))

    def test_only_on_its_days(self):
        self.assertFalse(entry_covers(slot('07:00', '09:30'), at(5, '08:00')))   # Saturday

    def test_a_slot_ending_before_it_starts_runs_past_midnight(self):
        entry = slot('22:00', '06:00', days=[4])   # Friday night
        self.assertTrue(entry_covers(entry, at(4, '23:00')))
        self.assertTrue(entry_covers(entry, at(5, '05:59')))    # into Saturday morning
        self.assertFalse(entry_covers(entry, at(5, '06:00')))
        self.assertFalse(entry_covers(entry, at(4, '05:00')))   # Friday morning belongs to Thursday
        self.assertFalse(entry_covers(entry, at(5, '23:00')))

    def test_sunday_night_runs_into_monday(self):
        self.assertTrue(entry_covers(slot('22:00', '06:00', days=[6]), at(0, '01:00')))

    def test_the_same_start_and_end_is_all_day(self):
        entry = slot('00:00', '00:00', days=[2])
        self.assertTrue(entry_covers(entry, at(2, '00:00')))
        self.assertTrue(entry_covers(entry, at(2, '23:59')))
        self.assertFalse(entry_covers(entry, at(3, '00:00')))


class TargetForTest(unittest.TestCase):
    def test_the_first_slot_that_covers_the_time_wins(self):
        schedule = {'default': 'app:time', 'entries': [
            slot('07:00', '09:00', target='playlist:Morning'),
            slot('00:00', '00:00', target='app:weather'),
        ]}
        self.assertEqual(target_for(schedule, at(0, '08:00')), 'playlist:Morning')
        self.assertEqual(target_for(schedule, at(0, '10:00')), 'app:weather')
        self.assertEqual(target_for(schedule, at(6, '10:00')), 'app:time')

    def test_no_default_is_nothing(self):
        self.assertEqual(target_for({'entries': []}, at(0, '10:00')), '')


class ValidateTest(unittest.TestCase):
    APPS = {'time', 'weather'}

    def check(self, data):
        return validate(data, self.APPS)

    def test_a_good_schedule_is_cleaned_up(self):
        schedule, problem = self.check({'enabled': 1, 'default': '', 'entries': [
            {'days': [4, 0, 0], 'start': '07:00', 'end': '23:59', 'target': 'playlist:Any name: here', 'x': 1}]})
        self.assertIsNone(problem)
        self.assertEqual(schedule, {'enabled': True, 'default': '', 'entries': [
            {'days': [0, 4], 'start': '07:00', 'end': '23:59', 'target': 'playlist:Any name: here'}]})

    def test_problems_are_named(self):
        cases = [
            ({'default': 'app:nope'}, 'Unknown default: app:nope'),
            ({'entries': [slot('07:00', '09:00', days=[])]}, 'Entry 1 needs at least one day'),
            ({'entries': [slot('07:00', '09:00', days=[7])]}, 'Entry 1 needs at least one day'),
            ({'entries': [slot('07:00', '09:00', days=[True])]}, 'Entry 1 needs at least one day'),
            ({'entries': [slot('7:00', '09:00')]}, 'Entry 1 needs a start and end time (HH:MM)'),
            ({'entries': [slot('07:00', '24:00')]}, 'Entry 1 needs a start and end time (HH:MM)'),
            ({'entries': [slot('07:00', '09:00'), slot('07:00', '09:00', target='')]},
             'Entry 2 needs something to show'),
            ({'entries': [slot('07:00', '09:00', target='playlist:')]}, 'Entry 1 needs something to show'),
            ({'entries': [slot('07:00', '09:00', target='app:nope')]}, 'Entry 1 needs something to show'),
            ([], 'Schedule must be an object'),
        ]
        for data, message in cases:
            with self.subTest(data=data):
                self.assertEqual(self.check(data), (None, message))


class SchedulerTest(unittest.TestCase):
    def setUp(self):
        self.state = DisplayState()
        self.settings = {
            'saved_playlists': {'Morning': {'pages': [{'text': 'HI'}], 'delay': '4'}},
            'schedule': {'enabled': True, 'default': 'app:time', 'entries': [
                slot('07:00', '09:00', target='playlist:Morning')]},
        }
        self.now = at(0, '06:00')
        self.scheduler = Scheduler(self.state, self.settings, lambda: self.now,
                                   lambda key: key in {'time', 'weather'})

    def test_the_first_check_starts_what_is_scheduled(self):
        self.scheduler.tick()
        self.assertEqual(self.state.active_app, 'time')
        self.assertTrue(self.state.snapshot()['scheduled'])

    def test_a_slot_starting_plays_its_playlist_by_name(self):
        self.scheduler.tick()
        self.now = at(0, '07:00')
        self.scheduler.tick()
        snap = self.state.snapshot()
        self.assertIsNone(snap['active_app'])
        self.assertEqual(snap['playlist'], {'name': 'Morning', 'page': 0, 'pages': 1})
        self.assertEqual(self.state.loop_delay, 4.0)

    def test_something_started_by_hand_stays_until_the_schedule_changes(self):
        self.scheduler.tick()
        self.state.run_app('weather')
        self.now = at(0, '06:30')
        self.scheduler.tick()
        self.assertEqual(self.state.active_app, 'weather')
        self.assertFalse(self.state.snapshot()['scheduled'])
        self.now = at(0, '07:00')
        self.scheduler.tick()
        self.assertEqual(self.state.playlist_name, 'Morning')

    def test_leaving_a_slot_with_no_default_stops_what_it_started(self):
        self.settings['schedule']['default'] = ''
        self.now = at(0, '08:00')
        self.scheduler.tick()
        self.now = at(0, '09:00')
        self.scheduler.tick()
        self.assertIsNone(self.state.current_target())

    def test_but_not_something_started_by_hand(self):
        self.settings['schedule']['default'] = ''
        self.now = at(0, '08:00')
        self.scheduler.tick()
        self.state.run_app('weather')
        self.now = at(0, '09:00')
        self.scheduler.tick()
        self.assertEqual(self.state.active_app, 'weather')

    def test_saving_the_schedule_applies_it_again(self):
        self.scheduler.tick()
        self.state.stop()
        self.scheduler.check_soon()
        self.scheduler.tick()
        self.assertEqual(self.state.active_app, 'time')

    def test_a_disabled_schedule_does_nothing(self):
        self.settings['schedule']['enabled'] = False
        self.scheduler.tick()
        self.assertIsNone(self.state.current_target())

    def test_turning_it_off_forgets_it_was_scheduled(self):
        self.scheduler.tick()
        self.settings['schedule']['enabled'] = False
        self.scheduler.tick()
        self.assertEqual(self.state.active_app, 'time')   # still running, just not scheduled
        self.assertFalse(self.state.snapshot()['scheduled'])

    def test_a_missing_playlist_or_app_is_skipped(self):
        self.settings['schedule']['default'] = 'playlist:Gone'
        self.scheduler.tick()
        self.assertIsNone(self.state.current_target())
        self.settings['schedule']['default'] = 'app:gone'
        self.scheduler.check_soon()
        self.scheduler.tick()
        self.assertIsNone(self.state.current_target())

    def test_what_is_already_running_is_not_restarted(self):
        self.state.run_playlist([{'text': 'A'}, {'text': 'B'}], 5, 'Morning')
        self.state.set_playlist_page(1)
        self.now = at(0, '08:00')
        self.scheduler.tick()
        self.assertEqual(self.state.playlist_page, 1)
        self.assertTrue(self.state.snapshot()['scheduled'])


if __name__ == '__main__':
    unittest.main()
