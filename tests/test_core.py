import json
import unittest

from light_animator.exporter import export_c_header
from light_animator.generators import GeneratorRange, apply_center_gather, apply_flow, apply_meteor
from light_animator.model import LightProject


class CoreTestCase(unittest.TestCase):
    def test_led_count_resize_preserves_and_extends_values(self):
        project = LightProject.create(led_count=3, frame_count=1)
        project.frames[0].values = [10, 20, 30]

        project.set_led_count(5)
        self.assertEqual(project.frames[0].values, [10, 20, 30, 0, 0])

        project.set_led_count(2)
        self.assertEqual(project.frames[0].values, [10, 20])

    def test_frame_operations_and_duration(self):
        project = LightProject.create(led_count=4, frame_count=1)
        project.frames[0].values = [1, 2, 3, 4]
        project.set_duration(0, 55)

        duplicated = project.duplicate_frame(0)
        self.assertEqual(duplicated, 1)
        self.assertEqual(project.frames[1].values, [1, 2, 3, 4])
        self.assertEqual(project.frames[1].duration_ms, 55)

        selected = project.delete_frame(0)
        self.assertEqual(selected, 0)
        self.assertEqual(len(project.frames), 1)
        self.assertEqual(project.frames[0].values, [1, 2, 3, 4])

    def test_generators_only_touch_selected_range(self):
        project = LightProject.create(led_count=8, frame_count=4)
        project.fill_range(0, 3, 0, 7, 11)
        area = GeneratorRange(1, 2, 2, 5)

        apply_flow(project, area, start_pos=2, end_pos=5, peak=200, tail=1)

        self.assertEqual(project.frames[0].values, [11] * 8)
        self.assertEqual(project.frames[3].values, [11] * 8)
        for frame_index in (1, 2):
            self.assertEqual(project.frames[frame_index].values[:2], [11, 11])
            self.assertEqual(project.frames[frame_index].values[6:], [11, 11])
            self.assertGreater(max(project.frames[frame_index].values[2:6]), 11)

    def test_meteor_and_center_gather_produce_brightness(self):
        project = LightProject.create(led_count=12, frame_count=6)
        area = GeneratorRange(0, 5, 0, 11)

        apply_meteor(project, area, start_pos=0, end_pos=11, peak=220, tail=3)
        self.assertEqual(max(max(frame.values) for frame in project.frames), 220)

        apply_center_gather(project, area, peak=180, tail=2, center_width=2, hold_frames=1)
        self.assertEqual(max(project.frames[-1].values), 180)
        self.assertTrue(project.frames[-1].values[5] == 180 or project.frames[-1].values[6] == 180)

    def test_json_shape_round_trip_and_c_export(self):
        project = LightProject.create(led_count=3, frame_count=2)
        project.frames[0].duration_ms = 10
        project.frames[0].values = [1, 2, 3]
        project.frames[1].duration_ms = 20
        project.frames[1].values = [4, 5, 6]

        data = project.to_dict()
        loaded = LightProject.from_dict(json.loads(json.dumps(data)))
        self.assertEqual(loaded.led_count, 3)
        self.assertEqual(loaded.frames[1].duration_ms, 20)
        self.assertEqual(loaded.frames[1].values, [4, 5, 6])

        header = export_c_header(loaded, "demo_light")
        self.assertIn("#define DEMO_LIGHT_LED_COUNT 3", header)
        self.assertIn("#define DEMO_LIGHT_FRAME_COUNT 2", header)
        self.assertIn("const uint16_t demo_light_frame_duration_ms[DEMO_LIGHT_FRAME_COUNT]", header)
        self.assertIn("const uint8_t demo_light_frames[DEMO_LIGHT_FRAME_COUNT][DEMO_LIGHT_LED_COUNT]", header)
        self.assertIn("{  1,   2,   3}", header)


if __name__ == "__main__":
    unittest.main()
