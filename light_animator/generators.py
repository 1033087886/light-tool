from __future__ import annotations

from dataclasses import dataclass
from math import pow

from .model import LightProject, clamp_byte, normalized_range


@dataclass(frozen=True)
class GeneratorRange:
    frame_start: int
    frame_end: int
    led_start: int
    led_end: int


def apply_flow(
    project: LightProject,
    area: GeneratorRange,
    start_pos: int,
    end_pos: int,
    peak: int = 255,
    tail: int = 4,
) -> None:
    frames = list(normalized_range(area.frame_start, area.frame_end, len(project.frames)))
    leds = list(normalized_range(area.led_start, area.led_end, project.led_count))
    if not frames or not leds:
        return

    peak = clamp_byte(peak)
    tail = max(0, int(tail))
    direction = 1 if end_pos >= start_pos else -1
    for order, frame_index in enumerate(frames):
        t = order / max(1, len(frames) - 1)
        center = start_pos + (end_pos - start_pos) * t
        _overwrite_leds(project, frame_index, leds, center, peak, tail, direction)
    project.touch()


def apply_meteor(
    project: LightProject,
    area: GeneratorRange,
    start_pos: int,
    end_pos: int,
    peak: int = 255,
    tail: int = 6,
    gamma: float = 1.35,
) -> None:
    frames = list(normalized_range(area.frame_start, area.frame_end, len(project.frames)))
    leds = list(normalized_range(area.led_start, area.led_end, project.led_count))
    if not frames or not leds:
        return

    peak = clamp_byte(peak)
    tail = max(0, int(tail))
    gamma = max(0.1, float(gamma))
    direction = 1 if end_pos >= start_pos else -1
    for order, frame_index in enumerate(frames):
        t = order / max(1, len(frames) - 1)
        head = start_pos + (end_pos - start_pos) * t
        frame_values = project.frames[frame_index].values
        for led_index in leds:
            distance = (head - led_index) * direction
            if distance < 0 or distance > tail:
                value = 0
            elif tail == 0:
                value = peak if abs(led_index - head) < 0.5 else 0
            else:
                value = peak * pow(1 - distance / max(1, tail), gamma)
            frame_values[led_index] = clamp_byte(value)
    project.touch()


def apply_center_gather(
    project: LightProject,
    area: GeneratorRange,
    peak: int = 255,
    tail: int = 5,
    center_width: int = 2,
    hold_frames: int = 2,
) -> None:
    frames = list(normalized_range(area.frame_start, area.frame_end, len(project.frames)))
    leds = list(normalized_range(area.led_start, area.led_end, project.led_count))
    if not frames or not leds:
        return

    peak = clamp_byte(peak)
    tail = max(0, int(tail))
    hold_frames = max(0, int(hold_frames))
    center_width = max(1, int(center_width))
    left_edge = min(leds)
    right_edge = max(leds)
    center = (left_edge + right_edge) / 2
    center_left = center - (center_width - 1) / 2
    center_right = center + (center_width - 1) / 2
    travel_frames = max(1, len(frames) - hold_frames)

    for order, frame_index in enumerate(frames):
        if order >= travel_frames:
            left_head = center_left
            right_head = center_right
        else:
            t = order / max(1, travel_frames - 1)
            left_head = left_edge + (center_left - left_edge) * t
            right_head = right_edge + (center_right - right_edge) * t

        frame_values = project.frames[frame_index].values
        for led_index in leds:
            left_value = _trail_value(led_index, left_head, -1, peak, tail)
            right_value = _trail_value(led_index, right_head, 1, peak, tail)
            if center_left <= led_index <= center_right and order >= travel_frames - 1:
                center_value = peak
            else:
                center_value = 0
            frame_values[led_index] = clamp_byte(max(left_value, right_value, center_value))
    project.touch()


def _overwrite_leds(
    project: LightProject,
    frame_index: int,
    leds: list[int],
    center: float,
    peak: int,
    tail: int,
    direction: int,
) -> None:
    frame_values = project.frames[frame_index].values
    for led_index in leds:
        distance = (center - led_index) * direction
        if distance < 0:
            value = 0
        elif tail == 0:
            value = peak if distance < 0.5 else 0
        elif distance <= tail:
            value = peak * (1 - distance / (tail + 1))
        else:
            value = 0
        frame_values[led_index] = clamp_byte(value)


def _trail_value(led_index: int, head: float, tail_direction: int, peak: int, tail: int) -> int:
    distance = (led_index - head) * tail_direction
    if distance < 0 or distance > tail:
        return 0
    if tail == 0:
        return peak if abs(led_index - head) < 0.5 else 0
    return clamp_byte(peak * (1 - distance / max(1, tail)))
