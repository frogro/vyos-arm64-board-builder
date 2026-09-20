import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('display', Path(__file__).resolve().parents[1] / 'container/kiosk-display.py')
display = importlib.util.module_from_spec(spec)
spec.loader.exec_module(display)

class DisplayTests(unittest.TestCase):
    def test_config_rejects_invalid_settings(self):
        for env in [{'KIOSK_ROTATION': '45'}, {'KIOSK_URL': '--incognito'},
                    {'KIOSK_URL': 'javascript:alert(1)'}, {'KIOSK_OUTPUT': '--auto'},
                    {'KIOSK_URL': 'https://example.org/\n--foo'}]:
            with self.assertRaises(ValueError):
                display.settings(env)

    def test_url_passed_without_shell_interpretation(self):
        url = 'https://example.org/?a=1&b=$(touch /tmp/no)'
        self.assertEqual(display.settings({'KIOSK_URL': url})[2], url)

    def test_output_selection_and_geometry(self):
        text = ('Screen 0: current 3000 x 1920, maximum 4096 x 4096\n'
                'DP-2 connected 1920x1080+0+0 (normal left inverted right)\n'
                'HDMI-2 connected primary 1080x1920+1920+0 left (normal left inverted right)\n')
        self.assertEqual(display.select_output(text, 'auto'), 'HDMI-2')
        self.assertEqual(display.geometry(text, 'HDMI-2'), (1080,1920,1920,0,3000,1920))
        with self.assertRaises(ValueError):
            display.select_output(text.replace(' primary', ''), 'auto')
        with self.assertRaises(ValueError):
            display.select_output(text, 'HDMI-1')

    def test_active_rotation_tracks_same_size_changes(self):
        for token, expected in [('', '0'), ('left ', '90'), ('inverted ', '180'), ('right ', '270')]:
            text = 'DP-1 connected primary 1920x1080+0+0 ' + token + '(normal left inverted right)'
            self.assertEqual(display.active_rotation(text, 'DP-1'), expected)
        with self.assertRaises(ValueError):
            display.active_rotation('DP-1 disconnected (normal left inverted right)', 'DP-1')

    def test_rotation_maps_corners_inside_selected_output(self):
        geom = (1080, 1920, 1920, 0, 3000, 1920)
        for rotation in display.ROTATIONS:
            m = display.touch_matrix(rotation, geom)
            corners = [(m[0]*x+m[1]*y+m[2], m[3]*x+m[4]*y+m[5])
                       for x,y in [(0,0),(0,1),(1,0),(1,1)]]
            self.assertEqual(set((round(x,4),round(y,4)) for x,y in corners),
                             {(0.64,0),(0.64,1),(1,0),(1,1)})
        self.assertEqual(display.touch_matrix('90',(1080,1920,0,0,1080,1920)),
                         [0,-1,1,1,0,0,0,0,1])

if __name__ == '__main__':
    unittest.main()
