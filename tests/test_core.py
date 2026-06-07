import json
import unittest

from light_animator.exporter import export_c_header
from light_animator.generators import (
    GeneratorRange,
    apply_breathe,
    apply_center_bloom_chase,
    apply_center_expand,
    apply_center_gather,
    apply_center_pulse,
    apply_edge_fill,
    apply_flow,
    apply_layered_stack_chase,
    apply_meteor,
    apply_segment_blink,
)
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

    def test_frame_count_resize_preserves_existing_frames(self):
        project = LightProject.create(led_count=4, frame_count=2)
        project.frames[0].values = [1, 2, 3, 4]
        project.frames[0].duration_ms = 77
        project.frames[1].values = [5, 6, 7, 8]

        project.set_frame_count(4)
        self.assertEqual(len(project.frames), 4)
        self.assertEqual(project.frames[0].values, [1, 2, 3, 4])
        self.assertEqual(project.frames[0].duration_ms, 77)
        self.assertEqual(project.frames[2].values, [0, 0, 0, 0])

        project.set_frame_count(1)
        self.assertEqual(len(project.frames), 1)
        self.assertEqual(project.frames[0].values, [1, 2, 3, 4])
        self.assertEqual(project.frames[0].duration_ms, 77)

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

    def test_flow_keeps_unreached_leds_off(self):
        project = LightProject.create(led_count=8, frame_count=1)

        apply_flow(project, GeneratorRange(0, 0, 0, 7), start_pos=2, end_pos=6, peak=200, tail=3)

        self.assertEqual(project.frames[0].values[2], 200)
        self.assertEqual(project.frames[0].values[3:], [0, 0, 0, 0, 0])

    def test_reverse_flow_keeps_unreached_leds_off(self):
        project = LightProject.create(led_count=8, frame_count=1)

        apply_flow(project, GeneratorRange(0, 0, 0, 7), start_pos=5, end_pos=1, peak=200, tail=3)

        self.assertEqual(project.frames[0].values[5], 200)
        self.assertEqual(project.frames[0].values[:5], [0, 0, 0, 0, 0])

    def test_meteor_and_center_gather_produce_brightness(self):
        project = LightProject.create(led_count=12, frame_count=6)
        area = GeneratorRange(0, 5, 0, 11)

        apply_meteor(project, area, start_pos=0, end_pos=11, peak=220, tail=3)
        self.assertEqual(max(max(frame.values) for frame in project.frames), 220)

        apply_center_gather(project, area, peak=180, tail=2, center_width=2, hold_frames=1)
        self.assertEqual(max(project.frames[-1].values), 180)
        self.assertTrue(project.frames[-1].values[5] == 180 or project.frames[-1].values[6] == 180)

    def test_video_style_generators_produce_expected_shapes(self):
        area = GeneratorRange(0, 7, 2, 13)

        breathe = LightProject.create(led_count=16, frame_count=8)
        breathe.fill_range(0, 7, 0, 15, 9)
        apply_breathe(breathe, area, start_pos=2, end_pos=13, peak=210, tail=0, hold_frames=2)
        self.assertEqual(breathe.frames[0].values[:2], [9, 9])
        self.assertEqual(breathe.frames[0].values[14:], [9, 9])
        self.assertEqual(max(breathe.frames[3].values[2:14]), 210)
        self.assertGreater(max(breathe.frames[3].values[2:14]), max(breathe.frames[0].values[2:14]))

        center = LightProject.create(led_count=16, frame_count=8)
        apply_center_pulse(center, area, start_pos=2, end_pos=13, peak=220, tail=1, center_width=2, hold_frames=2)
        self.assertEqual(max(center.frames[3].values), 220)
        self.assertEqual(center.frames[3].values[7], 220)
        self.assertEqual(center.frames[3].values[8], 220)
        self.assertEqual(center.frames[3].values[2], 0)

        expand = LightProject.create(led_count=16, frame_count=8)
        apply_center_expand(expand, area, start_pos=2, end_pos=13, peak=230, tail=0, center_width=2, hold_frames=1)
        self.assertEqual(expand.frames[0].values[7], 230)
        self.assertEqual(expand.frames[0].values[2], 0)
        self.assertEqual(expand.frames[-1].values[2:14], [230] * 12)

        edge = LightProject.create(led_count=16, frame_count=8)
        apply_edge_fill(edge, area, start_pos=2, end_pos=13, peak=240, tail=0, center_width=2, hold_frames=1)
        self.assertEqual(edge.frames[0].values[2], 240)
        self.assertEqual(edge.frames[0].values[13], 240)
        self.assertEqual(edge.frames[0].values[7], 0)
        self.assertEqual(edge.frames[-1].values[2:14], [240] * 12)

    def test_segment_blink_cycles_common_tail_light_blocks(self):
        project = LightProject.create(led_count=18, frame_count=8)
        area = GeneratorRange(0, 7, 1, 16)

        apply_segment_blink(project, area, start_pos=1, end_pos=16, peak=200, tail=0, segment_width=2, hold_frames=1)

        self.assertEqual(project.frames[0].values[1], 200)
        self.assertEqual(project.frames[0].values[8], 200)
        self.assertEqual(project.frames[0].values[16], 200)
        self.assertEqual(project.frames[1].values[8], 200)
        self.assertEqual(project.frames[1].values[1], 0)
        self.assertEqual(project.frames[2].values[1], 200)
        self.assertEqual(project.frames[2].values[16], 200)
        self.assertEqual(max(project.frames[3].values[1:17]), 0)

    def test_center_bloom_chase_combines_side_blocks_and_growing_center(self):
        project = LightProject.create(led_count=32, frame_count=32)
        area = GeneratorRange(0, 31, 0, 31)

        apply_center_bloom_chase(project, area, start_pos=0, end_pos=31, peak=255, tail=0, center_width=4, hold_frames=1)

        self.assertEqual(project.frames[0].values[:4], [255] * 4)
        self.assertEqual(project.frames[0].values[28:], [255] * 4)
        self.assertEqual(max(project.frames[0].values[12:20]), 0)

        self.assertEqual(project.frames[3].values[12:20], [255] * 8)
        self.assertEqual(project.frames[4].values[0:4], [255] * 4)
        self.assertEqual(project.frames[4].values[12:20], [255] * 8)
        self.assertEqual(project.frames[4].values[28:32], [255] * 4)

        self.assertEqual(project.frames[10].values[9:23], [255] * 14)
        self.assertEqual(project.frames[16].values[0:4], [255] * 4)
        self.assertEqual(project.frames[16].values[28:32], [255] * 4)
        self.assertGreater(sum(1 for value in project.frames[16].values if value == 255), 20)
        self.assertEqual(project.frames[-1].values, [255] * 32)

    def test_layered_stack_chase_builds_center_in_locked_layers(self):
        project = LightProject.create(led_count=32, frame_count=20)
        area = GeneratorRange(0, 19, 0, 31)

        apply_layered_stack_chase(
            project,
            area,
            start_pos=0,
            end_pos=31,
            peak=255,
            tail=0,
            center_width=4,
            hold_frames=1,
        )

        self.assertEqual(project.frames[0].values[:4], [255] * 4)
        self.assertEqual(project.frames[0].values[28:], [255] * 4)
        self.assertEqual(max(project.frames[0].values[12:20]), 0)

        self.assertTrue(any(frame.values[12:20] == [255] * 8 for frame in project.frames))
        self.assertTrue(any(frame.values[8:24] == [255] * 16 for frame in project.frames))
        self.assertTrue(any(frame.values[4:28] == [255] * 24 for frame in project.frames))
        self.assertEqual(project.frames[-1].values, [255] * 32)

    def test_layered_stack_chase_has_no_adjacent_duplicate_frames_for_72_leds(self):
        project = LightProject.create(led_count=72, frame_count=48)
        area = GeneratorRange(0, 47, 0, 71)

        apply_layered_stack_chase(
            project,
            area,
            start_pos=0,
            end_pos=71,
            peak=255,
            tail=0,
            center_width=4,
            hold_frames=1,
        )

        states = [tuple(frame.values) for frame in project.frames]
        duplicate_frames = [
            frame_number
            for frame_number in range(2, len(states) + 1)
            if states[frame_number - 1] == states[frame_number - 2]
        ]

        self.assertEqual(duplicate_frames, [])
        self.assertEqual(project.frames[0].values[:4], [255] * 4)
        self.assertEqual(project.frames[0].values[68:], [255] * 4)
        self.assertTrue(any(frame.values[32:40] == [255] * 8 for frame in project.frames))
        self.assertEqual(project.frames[-1].values, [255] * 72)

    def test_layered_stack_chase_finishes_without_detached_edge_blocks(self):
        project = LightProject.create(led_count=72, frame_count=60)
        area = GeneratorRange(0, 59, 0, 71)

        apply_layered_stack_chase(
            project,
            area,
            start_pos=0,
            end_pos=71,
            peak=255,
            tail=0,
            center_width=4,
            hold_frames=1,
        )

        for frame in project.frames[-6:]:
            active_indexes = [index for index, value in enumerate(frame.values) if value == 255]
            self.assertEqual(active_indexes, list(range(active_indexes[0], active_indexes[-1] + 1)))
        self.assertEqual(project.frames[-1].values, [255] * 72)

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
