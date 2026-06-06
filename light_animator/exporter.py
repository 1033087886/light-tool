from __future__ import annotations

import json
from pathlib import Path

from .model import LightProject


def save_project(project: LightProject, path: str | Path) -> None:
    target = Path(path)
    target.write_text(
        json.dumps(project.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_project(path: str | Path) -> LightProject:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return LightProject.from_dict(data)


def export_c_header(project: LightProject, symbol_prefix: str = "light") -> str:
    project.normalize()
    prefix = _sanitize_symbol(symbol_prefix)
    upper = prefix.upper()
    duration_values = ", ".join(str(frame.duration_ms) for frame in project.frames)
    frame_rows = []
    for frame in project.frames:
        row = ", ".join(f"{value:3d}" for value in frame.values)
        frame_rows.append(f"    {{{row}}}")
    rows = ",\n".join(frame_rows)

    return f"""#pragma once

#include <stdint.h>

#define {upper}_LED_COUNT {project.led_count}
#define {upper}_FRAME_COUNT {len(project.frames)}

const uint16_t {prefix}_frame_duration_ms[{upper}_FRAME_COUNT] = {{
    {duration_values}
}};

const uint8_t {prefix}_frames[{upper}_FRAME_COUNT][{upper}_LED_COUNT] = {{
{rows}
}};
"""


def _sanitize_symbol(value: str) -> str:
    cleaned = []
    for char in value.strip():
        if char.isalnum() or char == "_":
            cleaned.append(char.lower())
        elif char in (" ", "-", "."):
            cleaned.append("_")
    symbol = "".join(cleaned).strip("_")
    if not symbol:
        symbol = "light"
    if symbol[0].isdigit():
        symbol = f"light_{symbol}"
    return symbol
