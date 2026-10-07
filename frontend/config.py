import os

# Physical grid dimensions. Change these two values (or set the env vars) to
# match your hardware — everything else (module count, layout math, frontend
# grid rendering) derives from them.
GRID_ROWS = int(os.environ.get('SPLITFLAP_ROWS', 4))
GRID_COLS = int(os.environ.get('SPLITFLAP_COLS', 16))
NUM_MODULES = GRID_ROWS * GRID_COLS

# The UI is laid out for displays up to 4x16. Bigger ones work, but may not
# look as good.
if GRID_ROWS < 1 or GRID_COLS < 1:
    raise ValueError(f'Display size {GRID_ROWS}x{GRID_COLS} is not valid: SPLITFLAP_ROWS and '
                     f'SPLITFLAP_COLS must each be at least 1.')

SERIAL_PORT = os.environ.get('SPLITFLAP_SERIAL_PORT', '/dev/ttyUSB0')
BAUD_RATE = int(os.environ.get('SPLITFLAP_BAUD', 9600))

# Send each page as one frame broadcast (m*f...) instead of one message per
# module. Needs module firmware with frame support; set to 0 for older
# firmware.
FRAME_BROADCAST = os.environ.get('SPLITFLAP_FRAME_BROADCAST', '1') != '0'

# Defaults to <repo_root>/settings.json but can be overridden so this isn't
# tied to one machine's home directory.
CONFIG_PATH = os.environ.get(
    'SPLITFLAP_CONFIG_PATH',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'settings.json')
)
