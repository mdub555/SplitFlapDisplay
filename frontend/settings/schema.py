from apps.base import SettingField

# Fields that are genuinely shared across more than one app (timezone is used
# by nearly everything with a clock; the YouTube fields are used by the
# YouTube, Comments, and Livestream apps) live here ONCE and render once in
# the Global Settings tab, instead of being re-collected in every app's
# individual settings modal like the old APP_SETTINGS_CONFIG did.
GLOBAL_FIELDS = [
    SettingField('timezone', 'Timezone', default='US/Eastern', placeholder='US/Eastern', scope='global'),
    SettingField('yt_channel_id', 'YouTube Channel ID', placeholder='UC...', scope='global'),
    SettingField('yt_api_key', 'YouTube Data API Key', type='password', scope='global'),
    SettingField('yt_video_id', 'YouTube Video ID (live / comments)', placeholder='dQw4w9WgXcQ', scope='global'),
]
