from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


PROJECT_VERSION = 1
DEFAULT_LED_COUNT = 32
DEFAULT_DURATION_MS = 40


def clamp_byte(value: int | float) -> int:
    return max(0, min(255, int(round(value))))


def clamp_duration(value: int | float) -> int:
    return max(1, int(round(value)))


@dataclass
class AnimationFrame:
    duration_ms: int = DEFAULT_DURATION_MS
    values: list[int] = field(default_factory=list)

    def normalized(self, led_count: int) -> "AnimationFrame":
        values = [clamp_byte(value) for value in self.values[:led_count]]
        if len(values) < led_count:
            values.extend([0] * (led_count - len(values)))
        return AnimationFrame(clamp_duration(self.duration_ms), values)


@dataclass
class LightProject:
    led_count: int = DEFAULT_LED_COUNT
    frames: list[AnimationFrame] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    version: int = PROJECT_VERSION

    @classmethod
    def create(cls, led_count: int = DEFAULT_LED_COUNT, frame_count: int = 16) -> "LightProject":
        now = iso_now()
        project = cls(
            led_count=max(1, int(led_count)),
            frames=[],
            metadata={"name": "Light Animation", "createdAt": now, "updatedAt": now},
        )
        project.frames = [
            AnimationFrame(DEFAULT_DURATION_MS, [0] * project.led_count)
            for _ in range(max(1, int(frame_count)))
        ]
        return project

    def normalize(self) -> None:
        self.led_count = max(1, int(self.led_count))
        if not self.frames:
            self.frames.append(AnimationFrame(DEFAULT_DURATION_MS, [0] * self.led_count))
        self.frames = [frame.normalized(self.led_count) for frame in self.frames]
        self.touch()

    def touch(self) -> None:
        self.metadata["updatedAt"] = iso_now()
        self.metadata.setdefault("createdAt", self.metadata["updatedAt"])
        self.metadata.setdefault("name", "Light Animation")

    def set_led_count(self, led_count: int) -> None:
        self.led_count = max(1, int(led_count))
        self.frames = [frame.normalized(self.led_count) for frame in self.frames]
        self.touch()

    def insert_frame(self, index: int, frame: AnimationFrame | None = None) -> int:
        index = max(0, min(len(self.frames), int(index)))
        new_frame = frame.normalized(self.led_count) if frame else AnimationFrame(
            DEFAULT_DURATION_MS, [0] * self.led_count
        )
        self.frames.insert(index, new_frame)
        self.touch()
        return index

    def add_frame(self) -> int:
        return self.insert_frame(len(self.frames))

    def duplicate_frame(self, index: int) -> int:
        index = self.valid_frame_index(index)
        source = self.frames[index]
        return self.insert_frame(index + 1, AnimationFrame(source.duration_ms, list(source.values)))

    def delete_frame(self, index: int) -> int:
        index = self.valid_frame_index(index)
        if len(self.frames) == 1:
            self.frames[0] = AnimationFrame(DEFAULT_DURATION_MS, [0] * self.led_count)
            self.touch()
            return 0
        del self.frames[index]
        self.touch()
        return min(index, len(self.frames) - 1)

    def copy_previous_frame(self, index: int) -> None:
        index = self.valid_frame_index(index)
        if index <= 0:
            return
        self.frames[index].values = list(self.frames[index - 1].values)
        self.touch()

    def clear_range(self, frame_start: int, frame_end: int, led_start: int, led_end: int) -> None:
        for frame_index in normalized_range(frame_start, frame_end, len(self.frames)):
            for led_index in normalized_range(led_start, led_end, self.led_count):
                self.frames[frame_index].values[led_index] = 0
        self.touch()

    def fill_range(
        self, frame_start: int, frame_end: int, led_start: int, led_end: int, value: int
    ) -> None:
        value = clamp_byte(value)
        for frame_index in normalized_range(frame_start, frame_end, len(self.frames)):
            for led_index in normalized_range(led_start, led_end, self.led_count):
                self.frames[frame_index].values[led_index] = value
        self.touch()

    def set_duration(self, index: int, duration_ms: int) -> None:
        index = self.valid_frame_index(index)
        self.frames[index].duration_ms = clamp_duration(duration_ms)
        self.touch()

    def total_duration_ms(self) -> int:
        return sum(frame.duration_ms for frame in self.frames)

    def valid_frame_index(self, index: int) -> int:
        if not self.frames:
            raise IndexError("project has no frames")
        return max(0, min(len(self.frames) - 1, int(index)))

    def to_dict(self) -> dict[str, Any]:
        self.normalize()
        return {
            "version": self.version,
            "ledCount": self.led_count,
            "frames": [
                {"durationMs": frame.duration_ms, "values": list(frame.values)}
                for frame in self.frames
            ],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LightProject":
        led_count = int(data.get("ledCount", DEFAULT_LED_COUNT))
        frames = [
            AnimationFrame(
                int(frame.get("durationMs", DEFAULT_DURATION_MS)),
                list(frame.get("values", [])),
            )
            for frame in data.get("frames", [])
        ]
        project = cls(
            led_count=led_count,
            frames=frames,
            metadata=dict(data.get("metadata", {})),
            version=int(data.get("version", PROJECT_VERSION)),
        )
        project.normalize()
        return project


def normalized_range(start: int, end: int, size: int) -> range:
    if size <= 0:
        return range(0)
    a = max(0, min(size - 1, int(start)))
    b = max(0, min(size - 1, int(end)))
    if a > b:
        a, b = b, a
    return range(a, b + 1)


def iso_now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()
