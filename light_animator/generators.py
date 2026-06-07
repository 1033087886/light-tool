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


def apply_breathe(
    project: LightProject,
    area: GeneratorRange,
    start_pos: int,
    end_pos: int,
    peak: int = 255,
    tail: int = 3,
    hold_frames: int = 2,
) -> None:
    frames = list(normalized_range(area.frame_start, area.frame_end, len(project.frames)))
    leds = _effect_leds(project, area, start_pos, end_pos)
    if not frames or not leds:
        return

    peak = clamp_byte(peak)
    tail = max(0, int(tail))
    hold_frames = max(0, int(hold_frames))
    left_edge = min(leds)
    right_edge = max(leds)

    for order, frame_index in enumerate(frames):
        level = _pulse_level(order, len(frames), hold_frames)
        frame_values = project.frames[frame_index].values
        for led_index in leds:
            value = _soft_region_value(led_index, left_edge, right_edge, peak * level, tail)
            frame_values[led_index] = value
    project.touch()


def apply_center_pulse(
    project: LightProject,
    area: GeneratorRange,
    start_pos: int,
    end_pos: int,
    peak: int = 255,
    tail: int = 4,
    center_width: int = 4,
    hold_frames: int = 2,
) -> None:
    frames = list(normalized_range(area.frame_start, area.frame_end, len(project.frames)))
    leds = _effect_leds(project, area, start_pos, end_pos)
    if not frames or not leds:
        return

    peak = clamp_byte(peak)
    tail = max(0, int(tail))
    hold_frames = max(0, int(hold_frames))
    center_width = max(1, int(center_width))
    center_left, center_right = _center_band(leds, center_width)

    for order, frame_index in enumerate(frames):
        level = _pulse_level(order, len(frames), hold_frames)
        frame_values = project.frames[frame_index].values
        for led_index in leds:
            frame_values[led_index] = _soft_region_value(
                led_index,
                center_left,
                center_right,
                peak * level,
                tail,
            )
    project.touch()


def apply_center_expand(
    project: LightProject,
    area: GeneratorRange,
    start_pos: int,
    end_pos: int,
    peak: int = 255,
    tail: int = 4,
    center_width: int = 2,
    hold_frames: int = 2,
) -> None:
    frames = list(normalized_range(area.frame_start, area.frame_end, len(project.frames)))
    leds = _effect_leds(project, area, start_pos, end_pos)
    if not frames or not leds:
        return

    peak = clamp_byte(peak)
    tail = max(0, int(tail))
    hold_frames = max(0, int(hold_frames))
    center_width = max(1, int(center_width))
    center_left, center_right = _center_band(leds, center_width)
    travel_frames = max(1, len(frames) - hold_frames)
    max_radius = max(center_left - min(leds), max(leds) - center_right)

    for order, frame_index in enumerate(frames):
        if order >= travel_frames:
            radius = max_radius
        else:
            t = order / max(1, travel_frames - 1)
            radius = max_radius * _smoothstep(t)
        left_edge = center_left - radius
        right_edge = center_right + radius
        frame_values = project.frames[frame_index].values
        for led_index in leds:
            frame_values[led_index] = _soft_region_value(led_index, left_edge, right_edge, peak, tail)
    project.touch()


def apply_edge_fill(
    project: LightProject,
    area: GeneratorRange,
    start_pos: int,
    end_pos: int,
    peak: int = 255,
    tail: int = 4,
    center_width: int = 2,
    hold_frames: int = 2,
) -> None:
    frames = list(normalized_range(area.frame_start, area.frame_end, len(project.frames)))
    leds = _effect_leds(project, area, start_pos, end_pos)
    if not frames or not leds:
        return

    peak = clamp_byte(peak)
    tail = max(0, int(tail))
    hold_frames = max(0, int(hold_frames))
    center_width = max(1, int(center_width))
    left_edge = min(leds)
    right_edge = max(leds)
    center_left, center_right = _center_band(leds, center_width)
    travel_frames = max(1, len(frames) - hold_frames)

    for order, frame_index in enumerate(frames):
        if order >= travel_frames:
            left_front = center_right
            right_front = center_left
        else:
            t = order / max(1, travel_frames - 1)
            eased = _smoothstep(t)
            left_front = left_edge + (center_right - left_edge) * eased
            right_front = right_edge + (center_left - right_edge) * eased

        frame_values = project.frames[frame_index].values
        for led_index in leds:
            left_value = _soft_region_value(led_index, left_edge, left_front, peak, tail)
            right_value = _soft_region_value(led_index, right_front, right_edge, peak, tail)
            frame_values[led_index] = max(left_value, right_value)
    project.touch()


def apply_segment_blink(
    project: LightProject,
    area: GeneratorRange,
    start_pos: int,
    end_pos: int,
    peak: int = 255,
    tail: int = 2,
    segment_width: int = 3,
    hold_frames: int = 2,
) -> None:
    frames = list(normalized_range(area.frame_start, area.frame_end, len(project.frames)))
    leds = _effect_leds(project, area, start_pos, end_pos)
    if not frames or not leds:
        return

    peak = clamp_byte(peak)
    tail = max(0, int(tail))
    segment_width = max(1, int(segment_width))
    phase_frames = max(1, int(hold_frames))
    left_edge = min(leds)
    right_edge = max(leds)
    center_left, center_right = _center_band(leds, segment_width)
    side_gap = max(segment_width + 1, (right_edge - left_edge + 1) // 3)
    segments = [
        (left_edge, min(right_edge, left_edge + segment_width - 1)),
        (center_left, center_right),
        (max(left_edge, right_edge - segment_width + 1), right_edge),
    ]
    if right_edge - left_edge + 1 >= segment_width * 4:
        segments.insert(1, (left_edge + side_gap, min(right_edge, left_edge + side_gap + segment_width - 1)))
        segments.insert(
            -1,
            (max(left_edge, right_edge - side_gap - segment_width + 1), right_edge - side_gap),
        )

    for order, frame_index in enumerate(frames):
        phase = (order // phase_frames) % 4
        if phase == 0:
            active = segments
            level = peak
        elif phase == 1:
            active = [segments[len(segments) // 2]]
            level = peak
        elif phase == 2:
            active = [segments[0], segments[-1]]
            level = peak
        else:
            active = []
            level = 0

        frame_values = project.frames[frame_index].values
        for led_index in leds:
            value = 0
            for segment_left, segment_right in active:
                value = max(value, _soft_region_value(led_index, segment_left, segment_right, level, tail))
            frame_values[led_index] = value
    project.touch()


def apply_center_bloom_chase(
    project: LightProject,
    area: GeneratorRange,
    start_pos: int,
    end_pos: int,
    peak: int = 255,
    tail: int = 0,
    center_width: int = 4,
    hold_frames: int = 1,
) -> None:
    frames = list(normalized_range(area.frame_start, area.frame_end, len(project.frames)))
    leds = _effect_leds(project, area, start_pos, end_pos)
    if not frames or not leds:
        return

    peak = clamp_byte(peak)
    tail = max(0, int(tail))
    block_width = max(1, int(center_width))
    phase_frames = max(1, int(hold_frames))
    left_edge = min(leds)
    right_edge = max(leds)
    center_seam = (left_edge + right_edge + 1) // 2
    fill_base_left = max(left_edge, center_seam - block_width)
    fill_base_right = min(right_edge, center_seam + block_width - 1)
    max_radius = max(fill_base_left - left_edge, right_edge - fill_base_right)
    span_width = right_edge - left_edge + 1
    half_span = max(1, (span_width + 1) // 2)
    chase_steps = max(1, (half_span + block_width - 1) // block_width)
    meet_frame = min(max(0, (chase_steps - 1) * phase_frames), max(0, len(frames) - 1))

    for order, frame_index in enumerate(frames):
        step = (order // phase_frames) % chase_steps
        left_block_left = min(right_edge, left_edge + step * block_width)
        left_block_right = min(right_edge, left_block_left + block_width - 1)
        right_block_right = max(left_edge, right_edge - step * block_width)
        right_block_left = max(left_edge, right_block_right - block_width + 1)

        if order < meet_frame:
            fill_left = None
            fill_right = None
        else:
            t = (order - meet_frame) / max(1, len(frames) - 1 - meet_frame)
            radius = max_radius * t
            fill_left = fill_base_left - radius
            fill_right = fill_base_right + radius

        frame_values = project.frames[frame_index].values
        for led_index in leds:
            draw_left_block = True
            draw_right_block = True
            if fill_left is not None and fill_right is not None:
                draw_left_block = left_block_right < fill_left
                draw_right_block = right_block_left > fill_right

            value = 0
            if draw_left_block:
                value = max(
                    value,
                    _soft_region_value(led_index, left_block_left, left_block_right, peak, tail),
                )
            if draw_right_block:
                value = max(
                    value,
                    _soft_region_value(led_index, right_block_left, right_block_right, peak, tail),
                )
            if fill_left is not None and fill_right is not None:
                value = max(value, _soft_region_value(led_index, fill_left, fill_right, peak, tail))
            frame_values[led_index] = value
    project.touch()


def apply_layered_stack_chase(
    project: LightProject,
    area: GeneratorRange,
    start_pos: int,
    end_pos: int,
    peak: int = 255,
    tail: int = 0,
    center_width: int = 4,
    hold_frames: int = 1,
) -> None:
    frames = list(normalized_range(area.frame_start, area.frame_end, len(project.frames)))
    leds = _effect_leds(project, area, start_pos, end_pos)
    if not frames or not leds:
        return

    peak = clamp_byte(peak)
    tail = max(0, int(tail))
    block_width = max(1, int(center_width))
    phase_frames = max(1, int(hold_frames))
    left_edge = min(leds)
    right_edge = max(leds)
    center_seam = (left_edge + right_edge + 1) // 2
    base_left = max(left_edge, center_seam - block_width)
    base_right = min(right_edge, center_seam + block_width - 1)
    max_radius = max(base_left - left_edge, right_edge - base_right)
    layer_count = max(0, (int(max_radius) + block_width - 1) // block_width)

    span_width = right_edge - left_edge + 1
    tail_finish_threshold = block_width * 2
    waves: list[tuple[int, int, int, bool]] = []
    travel_distances: list[int] = []
    for layer in range(layer_count + 1):
        target_left = max(left_edge, base_left - layer * block_width)
        target_right = min(right_edge, base_right + layer * block_width)

        use_tail_fill = False
        if layer > 0:
            previous_left, previous_right = _layer_fill_edges(
                left_edge,
                right_edge,
                base_left,
                base_right,
                block_width,
                layer - 1,
            )
            previous_width = previous_right - previous_left + 1
            use_tail_fill = (
                previous_width * 3 >= span_width * 2
                and target_left - left_edge <= tail_finish_threshold
                and right_edge - target_right <= tail_finish_threshold
            )

        if use_tail_fill:
            travel_distance = max(previous_left - target_left, target_right - previous_right)
            travel_distances.append(max(0, travel_distance * phase_frames - 1))
        else:
            travel_distance = max(0, target_left - left_edge)
            travel_distances.append(travel_distance * phase_frames)
        waves.append((layer, target_left, target_right, use_tail_fill))

    wave_frame_counts = _allocate_layer_frame_counts(travel_distances, len(frames))
    frame_order = 0
    for active_layer, target_left, target_right, use_tail_fill in waves:
        wave_frame_count = wave_frame_counts[active_layer]
        if wave_frame_count <= 0:
            continue

        travel_distance = max(0, target_left - left_edge)
        for wave_frame in range(wave_frame_count):
            if frame_order >= len(frames):
                break
            frame_values = project.frames[frames[frame_order]].values

            if use_tail_fill:
                previous_left, previous_right = _layer_fill_edges(
                    left_edge,
                    right_edge,
                    base_left,
                    base_right,
                    block_width,
                    active_layer - 1,
                )
                left_steps = max(0, previous_left - target_left)
                right_steps = max(0, target_right - previous_right)
                max_steps = max(left_steps, right_steps)
                step = max_steps
                if max_steps > 0:
                    step = ((wave_frame + 1) * max_steps + wave_frame_count - 1) // wave_frame_count
                fill_left = previous_left - min(left_steps, step)
                fill_right = previous_right + min(right_steps, step)

                for led_index in leds:
                    frame_values[led_index] = _soft_region_value(led_index, fill_left, fill_right, peak, tail)
                frame_order += 1
                continue

            if travel_distance <= 0:
                t = 1.0
            elif wave_frame_count <= 1:
                t = 0.0 if active_layer == 0 else 1.0
            else:
                t = wave_frame / (wave_frame_count - 1)

            left_block_left = int(round(left_edge + (target_left - left_edge) * t))
            right_block_right = int(round(right_edge + (target_right - right_edge) * t))
            left_block_right = min(right_edge, left_block_left + block_width - 1)
            right_block_left = max(left_edge, right_block_right - block_width + 1)

            completed_layer = active_layer if t >= 1.0 else active_layer - 1
            if completed_layer >= 0:
                fill_left, fill_right = _layer_fill_edges(
                    left_edge,
                    right_edge,
                    base_left,
                    base_right,
                    block_width,
                    completed_layer,
                )
            else:
                fill_left = None
                fill_right = None

            for led_index in leds:
                value = 0
                if fill_left is None or left_block_right < fill_left:
                    value = max(
                        value,
                        _soft_region_value(led_index, left_block_left, left_block_right, peak, tail),
                    )
                if fill_right is None or right_block_left > fill_right:
                    value = max(
                        value,
                        _soft_region_value(led_index, right_block_left, right_block_right, peak, tail),
                    )
                if fill_left is not None and fill_right is not None:
                    value = max(value, _soft_region_value(led_index, fill_left, fill_right, peak, tail))
                frame_values[led_index] = value
            frame_order += 1
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


def _effect_leds(project: LightProject, area: GeneratorRange, start_pos: int, end_pos: int) -> list[int]:
    area_left = min(area.led_start, area.led_end)
    area_right = max(area.led_start, area.led_end)
    effect_left = min(start_pos, end_pos)
    effect_right = max(start_pos, end_pos)
    left = max(area_left, effect_left)
    right = min(area_right, effect_right)
    return list(normalized_range(left, right, project.led_count)) if left <= right else []


def _center_band(leds: list[int], width: int) -> tuple[float, float]:
    center = (min(leds) + max(leds)) / 2
    left = center - (width - 1) / 2
    right = center + (width - 1) / 2
    return left, right


def _allocate_layer_frame_counts(travel_distances: list[int], frame_count: int) -> list[int]:
    wave_count = len(travel_distances)
    if wave_count == 0:
        return []

    frame_count = max(0, int(frame_count))
    if frame_count == 0:
        return [0] * wave_count

    if frame_count < wave_count:
        counts = [0] * wave_count
        if frame_count == 1:
            counts[0] = 1
            return counts
        for order in range(frame_count):
            layer = int(round(order * (wave_count - 1) / (frame_count - 1)))
            counts[layer] += 1
        return counts

    capacities = [max(1, distance + 1) for distance in travel_distances]
    counts = [1] * wave_count
    remaining = frame_count - wave_count

    for layer, distance in enumerate(travel_distances):
        if remaining <= 0:
            break
        if distance > 0 and counts[layer] < capacities[layer]:
            counts[layer] += 1
            remaining -= 1

    while remaining > 0:
        candidates = [layer for layer in range(wave_count) if counts[layer] < capacities[layer]]
        if not candidates:
            break
        layer = max(
            candidates,
            key=lambda index: (
                max(1, travel_distances[index]) / (counts[index] + 1),
                travel_distances[index],
                -index,
            ),
        )
        counts[layer] += 1
        remaining -= 1

    if remaining > 0:
        counts[-1] += remaining
    return counts


def _layer_fill_edges(
    left_edge: int,
    right_edge: int,
    base_left: int,
    base_right: int,
    block_width: int,
    layer: int,
) -> tuple[int, int]:
    radius = max(0, int(layer)) * max(1, int(block_width))
    return max(left_edge, base_left - radius), min(right_edge, base_right + radius)


def _soft_region_value(
    led_index: int,
    left_edge: float,
    right_edge: float,
    peak: int | float,
    softness: int,
) -> int:
    if left_edge <= led_index <= right_edge:
        return clamp_byte(peak)
    if softness <= 0:
        return 0
    distance = min(abs(led_index - left_edge), abs(led_index - right_edge))
    if distance > softness:
        return 0
    return clamp_byte(peak * (1 - distance / (softness + 1)))


def _pulse_level(order: int, frame_count: int, hold_frames: int) -> float:
    if frame_count <= 1:
        return 1.0
    hold_frames = max(0, min(int(hold_frames), frame_count))
    ramp_frames = frame_count - hold_frames
    if ramp_frames <= 1:
        return 1.0
    fade_in_frames = max(1, ramp_frames // 2)
    hold_start = fade_in_frames
    hold_end = hold_start + hold_frames
    if order < hold_start:
        return _smoothstep(order / max(1, fade_in_frames - 1))
    if order < hold_end:
        return 1.0
    fade_order = order - hold_end
    fade_out_frames = max(1, frame_count - hold_end)
    return 1.0 - _smoothstep(fade_order / max(1, fade_out_frames - 1))


def _smoothstep(value: float) -> float:
    value = max(0.0, min(1.0, float(value)))
    return value * value * (3 - 2 * value)
