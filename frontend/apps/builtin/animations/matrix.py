from apps.base import App, SettingField
from apps.builtin._shared import center_page, matrix_burst_frames
from display.layout import STYLES


class MatrixApp(App):
    key = 'anim_matrix'
    name = 'Matrix'
    icon = '💻'
    desc = 'Cascade reveal'
    settings_fields = [
        SettingField('anim_matrix_text', 'Reveal Text', default='SPLIT  FLAP  DISPLAY',
                     placeholder='SPLIT  FLAP  DISPLAY'),
        SettingField('anim_matrix_style', 'Final Reveal Order', type='select', default='ltr', opts=list(STYLES)),
        SettingField('anim_matrix_speed', 'Frame Speed (seconds)', type='number', default='0.4',
                     placeholder='0.4', min='0.1', max='2', step='0.1'),
    ]

    def get_pages(self, settings, cache):
        speed = max(0.1, float(self.setting(settings, 'anim_matrix_speed')))
        return matrix_burst_frames(
            center_page(self.setting(settings, 'anim_matrix_text').upper()),
            reveal_style=self.setting(settings, 'anim_matrix_style'),
            noise_delay=speed, reveal_delay=speed)
