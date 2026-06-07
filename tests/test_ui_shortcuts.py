import unittest

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QSpinBox

from light_animator.app import MainWindow, PlaybackPreviewCanvas


class ShortcutTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow()
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.app.processEvents()

    def test_ctrl_c_v_copies_current_frame_values_and_duration(self):
        self.window.project.frames[0].values = [7] * self.window.project.led_count
        self.window.project.frames[0].duration_ms = 77
        self.window.select_frame(0)

        QTest.keyClick(self.window, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        self.window.project.frames[1].values = [0] * self.window.project.led_count
        self.window.project.frames[1].duration_ms = 10
        self.window.select_frame(1)
        QTest.keyClick(self.window, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)

        self.assertEqual(self.window.project.frames[1].values[0], 7)
        self.assertEqual(self.window.project.frames[1].duration_ms, 77)

    def test_ctrl_shift_c_v_copies_selection_values_only(self):
        self.window.project.frames[0].values = [0] * self.window.project.led_count
        self.window.project.frames[1].values = [0] * self.window.project.led_count
        self.window.project.frames[0].values[2:5] = [21, 22, 23]
        self.window.project.frames[1].values[2:5] = [31, 32, 33]
        self.window.project.frames[2].duration_ms = 99

        self.window.frame_start_spin.setValue(1)
        self.window.frame_end_spin.setValue(2)
        self.window.led_start_spin.setValue(2)
        self.window.led_end_spin.setValue(4)
        QTest.keyClick(
            self.window,
            Qt.Key.Key_C,
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
        )

        self.window.frame_start_spin.setValue(3)
        self.window.frame_end_spin.setValue(4)
        self.window.led_start_spin.setValue(5)
        self.window.led_end_spin.setValue(7)
        QTest.keyClick(
            self.window,
            Qt.Key.Key_V,
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
        )

        self.assertEqual(self.window.project.frames[2].values[5:8], [21, 22, 23])
        self.assertEqual(self.window.project.frames[3].values[5:8], [31, 32, 33])
        self.assertEqual(self.window.project.frames[2].duration_ms, 99)

    def test_led_count_spin_resizes_without_confirmation(self):
        self.window.project.frames[0].values = list(range(self.window.project.led_count))

        self.window.led_count_spin.setValue(8)
        self.app.processEvents()

        self.assertEqual(self.window.project.led_count, 8)
        self.assertEqual(self.window.project.frames[0].values, list(range(8)))

    def test_frame_count_spin_resizes_and_clamps_current_frame(self):
        self.window.select_frame(10)

        self.window.frame_count_spin.setValue(6)
        self.app.processEvents()

        self.assertEqual(len(self.window.project.frames), 6)
        self.assertEqual(self.window.current_frame, 5)
        self.assertEqual(self.window.frame_start_spin.maximum(), 6)

    def test_frame_list_duration_text_edit_updates_duration(self):
        item = self.window.frame_list.item(0)
        item.setText("001    66 ms")
        self.app.processEvents()

        self.assertEqual(self.window.project.frames[0].duration_ms, 66)

        item = self.window.frame_list.item(0)
        item.setText("88")
        self.app.processEvents()

        self.assertEqual(self.window.project.frames[0].duration_ms, 88)

    def test_frame_list_uses_numeric_duration_editor(self):
        index = self.window.frame_list.model().index(0, 0)
        editor = self.window.frame_list.itemDelegate().createEditor(self.window.frame_list, None, index)

        self.assertIsInstance(editor, QSpinBox)
        self.assertEqual(editor.suffix(), " ms")

    def test_playback_preview_keeps_off_leds_black_with_red_preview_color(self):
        canvas = PlaybackPreviewCanvas()
        canvas.set_preview_color(QColor("#ff0000"))

        self.assertEqual(canvas._color_for_value(0).name(), "#000000")
        self.assertNotEqual(canvas._color_for_value(1).name(), "#000000")

    def test_playback_preview_does_not_fill_off_leds_with_previous_glow(self):
        canvas = PlaybackPreviewCanvas()
        values = [0] * 8
        values[0] = 255
        canvas.resize(520, 220)
        canvas.set_preview_color(QColor("#f6f8ff"))
        canvas.set_frame(values, 0, 1)

        image = QImage(canvas.size(), QImage.Format.Format_ARGB32)
        image.fill(QColor("#000000"))
        painter = QPainter(image)
        canvas.render(painter)
        painter.end()
        margin = 28
        gap = 5
        width = max(1, canvas.width() - margin * 2)
        cell_w = max(5, int((width - gap * (len(values) - 1)) / max(1, len(values))))
        cell_h = max(34, min(96, canvas.height() - 78))
        y = (canvas.height() - cell_h) // 2 + 8
        off_led_x = margin + (cell_w + gap) + cell_w // 2
        off_led_y = y + cell_h // 2
        off_color = image.pixelColor(off_led_x, off_led_y)

        self.assertEqual(off_color.name(), "#000000")


if __name__ == "__main__":
    unittest.main()
