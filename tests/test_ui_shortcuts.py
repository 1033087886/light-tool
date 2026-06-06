import unittest

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from light_animator.app import MainWindow


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


if __name__ == "__main__":
    unittest.main()
