"""The commands the Debug page can send: every command in the firmware's
protocol, the same set firmware/splitflapfirmwarev8/splitflap_test.py offers.

Each command is a dict the page reads from CONFIG.debug_commands:

  key       unique name
  group     the heading it's listed under in the dropdown
  label     how the dropdown names it
  cmd       the command letter (see Cmd)
  target    'module': sent to the chosen module ID, or * to broadcast
            'single': sent to the chosen module ID only
            'broadcast': always sent to every module (m*...)
            'none': the message is typed out in full
  format    how the message is built: 'plain' (m<ID><cmd><value>),
            'frame' (m*f<interval>:<pairs>) or 'raw' (sent as typed)
  params    the inputs it takes, in order (see _int, _bool, ...). An int's
            bias is added to the value typed before it's sent
  hint      shown under the inputs
  confirm   if set, asked before sending ({target} is the module it goes to)
  dump_after  offer to request a state dump straight afterwards
"""

from display.charset import NUM_FLAPS
from display.module_protocol import (
    FLAP_OFFSET_ZERO, FRAME_MAX_MODULES, GLOBAL_SETTINGS, MODULE_TOGGLES, UNPROVISIONED_ID, Cmd)


def _int(name, label, lo, hi, default=None, unit='', bias=0):
    return {'name': name, 'kind': 'int', 'label': label, 'min': lo, 'max': hi,
            'default': default, 'unit': unit, 'bias': bias}


def _bool(name, label, on='Yes (1)', off='No (0)', default=True):
    return {'name': name, 'kind': 'bool', 'label': label, 'on': on, 'off': off, 'default': default}


def _command(key, group, label, cmd, params=(), hint='', target='module', fmt='plain',
             confirm=None, dump_after=False):
    return {'key': key, 'group': group, 'label': label, 'cmd': cmd, 'target': target,
            'format': fmt, 'params': list(params), 'hint': hint, 'confirm': confirm,
            'dump_after': dump_after}


def _global_setting(key):
    """A broadcast-able setting command from GLOBAL_SETTINGS."""
    spec = GLOBAL_SETTINGS[key]
    if spec['type'] == 'bool':
        param = _bool('value', spec['label'], default=spec['default'])
    else:
        param = _int('value', spec['label'], spec['min'], spec['max'], spec['default'], spec['unit'])
    return _command(key, SETTINGS, f"Set {spec['label'].lower()}", spec['cmd'], [param], spec['hint'])


def _toggle(key, on, off):
    toggle = MODULE_TOGGLES[key]
    return _command(key, SETTINGS, f'Set {toggle.label.lower()}', toggle.cmd,
                    [_bool('value', toggle.label, on, off)], toggle.hint)


ACTIONS = 'Actions'
MODULE = 'Module'
SETTINGS = 'Settings (saved to EEPROM)'
UTILITIES = 'Utilities'

DEBUG_COMMANDS = [
    # Actions
    _command('show_char', ACTIONS, 'Show character', Cmd.DISPLAY_CHAR,
             [{'name': 'char', 'kind': 'char', 'label': 'Character'}],
             'One character from the reel. Special flaps: " (or q), ° (or d), ♥ (or h), '
             'and the colours r o y g b p w (or their emoji).'),
    _command('show_index', ACTIONS, 'Show by flap index', Cmd.DISPLAY_INDEX,
             [_int('index', 'Flap index', 0, NUM_FLAPS - 1, 0)],
             'See the flap character table below for what each index shows.'),
    _command('home', ACTIONS, 'Home module', Cmd.HOME),
    _command('calibrate', ACTIONS, 'Calibrate revolution', Cmd.CALIBRATE,
             hint='The module spins to measure one revolution and saves it as its total steps.',
             dump_after=True),
    _command('nudge', ACTIONS, 'Nudge steps', Cmd.NUDGE,
             [_int('steps', 'Steps to nudge', 0, 65535, 1, 'steps')],
             'Moves forward without changing the home offset (less than total steps). '
             'Set home offset to 0 afterwards to save this position as the blank flap.'),
    _command('goto_step', ACTIONS, 'Go to raw step position', Cmd.MOVE_TO_STEP,
             [_int('step', 'Target step', 0, 65535, 0, 'steps')],
             'Less than total steps. Ignored until the module has been homed.'),
    _command('stop', ACTIONS, 'Stop motor', Cmd.STOP),
    _command('exercise', ACTIONS, 'Exercise (step every flap)', Cmd.EXERCISE,
             [_int('laps', 'Laps of the reel', 1, 255, 1)],
             'Steps through every flap one at a time. Any other motion command, or Stop, ends it.'),
    _command('identify', ACTIONS, 'Identify (blink LED)', Cmd.IDENTIFY,
             hint="Blinks the module's status LED quickly for 10 seconds."),
    _command('reboot', ACTIONS, 'Reboot module', Cmd.REBOOT, confirm='Reboot {target}?'),
    _command('frame', ACTIONS, 'Frame broadcast (all modules)', Cmd.FRAME, [
        {'name': 'text', 'kind': 'text', 'label': 'Text', 'max_length': FRAME_MAX_MODULES},
        _int('interval', 'Cascade interval per rank', 0, 255, 0, 'ms'),
        {'name': 'order', 'kind': 'select', 'label': 'Order', 'default': 'ltr',
         'options': [['ltr', 'Left to right'], ['rtl', 'Right to left'], ['all', 'All at once']]},
    ], f'Each character goes to module ID 0, 1, 2, … in order (up to {FRAME_MAX_MODULES}). '
       'Special flaps as for Show character.', target='broadcast', fmt='frame'),
    # Module
    _command('dump', MODULE, 'Dump module state', Cmd.DUMP_STATE,
             hint='A busy module replies once it finishes moving. A broadcast is answered by '
                  'each provisioned module in turn. Replies appear in the log below.'),
    _command('set_id', MODULE, 'Set module ID', Cmd.SET_MODULE_ID,
             [_int('id', 'New module ID', 0, UNPROVISIONED_ID, None)],
             f"Changes the module's address ({UNPROVISIONED_ID} = unprovisioned). A broadcast is "
             f'only accepted by unprovisioned modules.',
             confirm='Change the ID of {target}?'),
    _command('reset_settings', MODULE, 'Reset settings to defaults', Cmd.RESET_SETTINGS,
             hint='Resets every setting to its firmware default, keeping the ID, then reboots.',
             confirm='Reset ALL settings on {target} to their defaults?'),
    _command('flap_offsets', MODULE, 'Dump flap offsets', Cmd.SET_FLAP_OFFSET,
             hint="Every flap's offset, from the module's EEPROM. A busy module replies once it "
                  'finishes moving. The reply appears in the log below.',
             target='single'),
    # Settings
    _command('offset', SETTINGS, 'Set home offset', Cmd.SET_OFFSET,
             [_int('value', 'Home offset', 0, 65535, None, 'steps')],
             '0 makes the current position the blank flap. Changing it marks the position '
             'unknown; the next move homes first.'),
    _command('total_steps', SETTINGS, 'Set total steps/rev', Cmd.SET_TOTAL_STEPS,
             [_int('value', 'Total steps per revolution', 1, 65535, None, 'steps')],
             'Stops any move and marks the position unknown.'),
    _global_setting('debounceMs'),
    _global_setting('recalculateHome'),
    _global_setting('autoHome'),
    _toggle('motorClockwise', 'Clockwise (1)', 'Counter-clockwise (0)'),
    _global_setting('motorRelease'),
    _global_setting('stepDelayUs'),
    _global_setting('homingStepDelayUs'),
    _global_setting('rampStartDelayUs'),
    _global_setting('rampSteps'),
    _global_setting('settleMs'),
    _global_setting('staggerMs'),
    _command('flap_offset', SETTINGS, 'Set flap offset (flap showing)', Cmd.SET_FLAP_OFFSET,
             [_int('offset', 'Offset', -FLAP_OFFSET_ZERO, 255 - FLAP_OFFSET_ZERO, 0, 'steps',
                   bias=FLAP_OFFSET_ZERO)],
             'Shifts the flap showing (show it first) this many steps from its even position, '
             'and turns to it; lowering an offset takes nearly a full revolution. Ignored for '
             'flap 0 (set the home offset instead), or while the module is moving.',
             target='single'),
    # Utilities
    _command('raw', UTILITIES, 'Send raw message', None,
             [{'name': 'message', 'kind': 'text', 'label': 'Message', 'placeholder': 'e.g. m05-B'}],
             'Sent exactly as typed (a newline is added).', target='none', fmt='raw'),
]
