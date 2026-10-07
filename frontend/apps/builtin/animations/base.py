from apps.base import App, Frame, SettingField
from display.layout import STYLES


class AnimationApp(App):
    """A loop of colour frames, with settings for the update order and the
    time per frame (stored as <key>_style and <key>_speed).

    Subclasses set key/name/icon/desc and the speed range, and implement
    frames(). Setting `fixed_style` always uses that order, with no setting
    for it."""

    default_speed = '0.5'   # seconds per frame, as the settings field shows it
    min_speed = 0.1
    max_speed = '3'
    speed_step = '0.1'
    fixed_style = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.settings_fields = [
            SettingField(f'{cls.key}_speed', 'Frame Speed (seconds)', type='number',
                         default=cls.default_speed, placeholder=cls.default_speed,
                         min=str(cls.min_speed), max=cls.max_speed, step=cls.speed_step),
        ]
        if cls.fixed_style is None:
            cls.settings_fields.insert(0, SettingField(
                f'{cls.key}_style', 'Update Order', type='select', default='ltr', opts=list(STYLES)))

    def frames(self):
        """The page strings to show, one per frame."""
        raise NotImplementedError

    def get_pages(self, settings, cache):
        style = self.fixed_style or self.setting(settings, f'{self.key}_style')
        speed = max(self.min_speed, float(self.setting(settings, f'{self.key}_speed')))
        return [Frame(text=page, delay=speed, style=style, raw=True) for page in self.frames()]
