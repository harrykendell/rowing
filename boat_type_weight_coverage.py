#!/usr/bin/env python3
"""Render club boat weight coverage by boat type as a standalone SVG."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from html import escape
from pathlib import Path


BOAT_TYPES = ["1x", "2x", "2x/-", "2-", "4x", "4x/-", "4-", "4+", "4x+", "8+"]
BOAT_TYPE_GROUPS = {
    "1x": "Singles",
    "2x": "Doubles",
    "2x/-": "Doubles",
    "2-": "Doubles",
    "4x": "Fours",
    "4x/-": "Fours",
    "4-": "Fours",
    "4+": "Coxed Fours",
    "4x+": "Coxed Fours",
    "8+": "Eights",
}
DISPLAY_BOAT_TYPES = [
    "Singles",
    "Doubles",
    "Fours",
    "Coxed Fours",
    "Eights",
]
RIGGING_TYPE = {
    "1x": "scull",
    "2x": "scull",
    "2x/-": "both",
    "2-": "sweep",
    "4x": "scull",
    "4x/-": "both",
    "4-": "sweep",
    "4+": "sweep",
    "4x+": "both",
    "8+": "sweep",
}
SCULL_COLOR = "#0b5d46"
SWEEP_COLOR = "#1e40af"
WEIGHT_TOLERANCE_KG = 5
BAR_STROKE_WIDTH = 15
FONT_STACK = "'IBM Plex Sans', 'Helvetica Neue', Arial, sans-serif"
CLUB_BOAT_COLOR = "#0b5d46"
APPROVAL_COLOR = "#dc2626"
GRID_COLOR = "#d7dfda"
TEXT_COLOR = "#14352b"
SUBTLE_TEXT = "#5b6f66"
BACKGROUND = "#ffffff"
PANEL_BACKGROUND = "#fcfbf6"
PANEL_BORDER = "#8ea79d"
HEADER_FILL = "#00543c"
HEADER_TEXT = "#f7f5ef"
ACCENT_GOLD = "#c5a24a"
RIGGING_TYPE_OVERRIDES = {
    47: "2x",  # Angus
    134: "2x/-",  # de la Mare
    48: "2-",  # Doug Melvin
    49: "2-",  # Ed Pair-cy
    50: "2x",  # Inch by Inch
    51: "2x/-",  # JK's
    55: "2x",  # Paulaurarmoff
    57: "2x/-",  # Snowy
    58: "2x/-",  # The Wibergs
    59: "2x",  # Tracey Ann
    60: "2x",  # Undine
    63: "2x",  # Yansec
    135: "4-",  # Fortitude
    67: "4-",  # SITA
    65: "4-",  # Hagaros
    74: "4+",  # High
    80: "4+",  # The Royal and Ancient
    72: "4+",  # City of Bristol
    78: "4+",  # Out of Nowhere
    64: "4x",  # Farn
    71: "4x",  # Water beetle
    70: "4x/-",  # Vixen
    66: "4x/-",  # Shaker Baker
    68: "4x/-",  # Dalesman
    69: "4x/-",  # Tricky
    81: "4x+",  # Water Witch
    76: "4x+",  # Kath & Rog
    77: "4x+",  # Neptune
    73: "4x+",  # Davina Lund
    75: "4x+",  # Inspired by Murphy
    79: "4x+",  # Paula
}
DROP_REASON_PRIORITY = [
    "private boat",
    "deleted",
    "wrong equipment type",
    "missing stated weight",
]
DROP_REASON_ORDER = {reason: index for index, reason in enumerate(DROP_REASON_PRIORITY)}


@dataclass(frozen=True)
class Boat:
    name: str
    boat_type: str
    display_type: str
    rigging: str
    weight: int
    approval_required: bool
    lower: int
    upper: int


@dataclass(frozen=True)
class DroppedBoat:
    name: str
    boat_type: str
    weight: int | None
    owner_id: int | None
    reason: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create a faceted SVG showing club boat weight coverage by boat type."
        )
    )
    parser.add_argument(
        "--boats",
        default="bristolrowing_boats.json",
        help="Path to the boats JSON export.",
    )
    parser.add_argument(
        "--svg-out",
        default="boat_type_weight_coverage.svg",
        help="Path to the SVG file to create.",
    )
    return parser.parse_args()


def load_boats(path: Path) -> tuple[list[Boat], list[DroppedBoat]]:
    with path.open() as handle:
        raw_boats = json.load(handle)["data"]

    boats: list[Boat] = []
    dropped_boats: list[DroppedBoat] = []
    for item in raw_boats:
        boat_type = resolve_boat_type(item)
        drop_reason = get_drop_reason(item)
        if drop_reason is not None:
            dropped_boats.append(
                DroppedBoat(
                    name=item["name"],
                    boat_type=boat_type,
                    weight=int(item["weight"])
                    if item.get("weight") is not None
                    else None,
                    owner_id=item.get("owner"),
                    reason=drop_reason,
                )
            )
            continue

        weight = int(item["weight"])
        boats.append(
            Boat(
                name=item["name"],
                boat_type=boat_type,
                display_type=BOAT_TYPE_GROUPS[boat_type],
                rigging=RIGGING_TYPE[boat_type],
                weight=weight,
                approval_required=bool(item.get("approval", False)),
                lower=weight - WEIGHT_TOLERANCE_KG,
                upper=weight + WEIGHT_TOLERANCE_KG,
            )
        )

    boats.sort(
        key=lambda boat: (
            DISPLAY_BOAT_TYPES.index(boat.display_type),
            boat.weight,
            boat.name,
        )
    )
    dropped_boats.sort(
        key=lambda boat: (DROP_REASON_ORDER[boat.reason], boat.boat_type, boat.name)
    )
    return boats, dropped_boats


def resolve_boat_type(item: dict[str, object]) -> str:
    return RIGGING_TYPE_OVERRIDES.get(int(item["id"]), str(item["type"]))


def get_drop_reason(item: dict[str, object]) -> str | None:
    boat_type = resolve_boat_type(item)
    if item.get("owner") is not None:
        return "private boat"
    if item.get("deleted"):
        return "deleted"
    if boat_type not in BOAT_TYPES:
        return "wrong equipment type"
    if item.get("weight") is None:
        return "missing stated weight"
    return None


def merge_intervals(intervals: list[tuple[int, int]]) -> list[list[int]]:
    merged: list[list[int]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return merged


def coverage_count(boats: list[Boat], kg: int) -> int:
    return sum(1 for boat in boats if boat.lower <= kg <= boat.upper)


def make_summary(grouped_boats: dict[str, list[Boat]]) -> list[dict[str, object]]:
    summary: list[dict[str, object]] = []
    for display_type in DISPLAY_BOAT_TYPES:
        boats = grouped_boats[display_type]
        intervals = [(boat.lower, boat.upper) for boat in boats]
        merged = merge_intervals(intervals)
        gaps = []
        for left, right in zip(merged, merged[1:]):
            gaps.append({"from_kg": left[1], "to_kg": right[0]})

        peak_density = 0
        peak_weights: list[int] = []
        if boats:
            for kg in range(
                min(boat.lower for boat in boats), max(boat.upper for boat in boats) + 1
            ):
                density = coverage_count(boats, kg)
                if density > peak_density:
                    peak_density = density
                    peak_weights = [kg]
                elif density == peak_density:
                    peak_weights.append(kg)

        summary.append(
            {
                "boat_type": display_type,
                "boat_count": len(boats),
                "coverage_min_kg": min(boat.lower for boat in boats) if boats else None,
                "coverage_max_kg": max(boat.upper for boat in boats) if boats else None,
                "peak_density": peak_density,
                "peak_weights_kg": peak_weights,
                "approval_required_boats": [
                    boat.name for boat in boats if boat.approval_required
                ],
                "boats": [asdict(boat) for boat in boats],
                "merged_coverage_ranges_kg": merged,
                "gaps_kg": gaps,
            }
        )
    return summary


def svg_text(
    x: float,
    y: float,
    text: str,
    css_class: str,
    anchor: str = "start",
    fill: str | None = None,
    bold: bool = False,
) -> str:
    fill_attr = f' fill="{fill}"' if fill else ""
    font_weight = ' font-weight="bold"' if bold else ""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" class="{css_class}" '
        f'text-anchor="{anchor}"{fill_attr}{font_weight}>{escape(text)}</text>'
    )


def render_svg(
    grouped_boats: dict[str, list[Boat]], summary: list[dict[str, object]]
) -> str:
    non_empty_boats = [boat for boats in grouped_boats.values() for boat in boats]
    axis_min = 5 * math.floor(min(boat.lower for boat in non_empty_boats) / 5)
    axis_max = 5 * math.ceil(max(boat.upper for boat in non_empty_boats) / 5)

    width = 1800
    left_margin = 120
    right_margin = 120
    plot_width = width - left_margin - right_margin
    title_block = 170
    panel_gap = 32
    axis_band = 22
    panel_header = 58
    row_height = 24
    panel_padding_bottom = 24
    footer_height = 42

    panel_heights = []
    for display_type in DISPLAY_BOAT_TYPES:
        boat_count = len(grouped_boats[display_type])
        panel_heights.append(
            panel_header + axis_band + (boat_count * row_height) + panel_padding_bottom
        )

    height = (
        title_block
        + footer_height
        + sum(panel_heights)
        + panel_gap * (len(DISPLAY_BOAT_TYPES) - 1)
    )

    def x_for_weight(weight: float) -> float:
        return left_margin + ((weight - axis_min) / (axis_max - axis_min)) * plot_width

    svg: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title subtitle">',
        "<style>",
        f"""
        .bg {{ fill: {BACKGROUND}; }}
        .panel {{ fill: {PANEL_BACKGROUND}; stroke: {PANEL_BORDER}; stroke-width: 2; }}
        .kicker {{ font: 700 18px {FONT_STACK}; fill: {SUBTLE_TEXT}; letter-spacing: 1.8px; text-transform: uppercase; }}
        .title {{ font: 800 40px {FONT_STACK}; fill: {HEADER_FILL}; letter-spacing: 0.4px; }}
        .subtitle {{ font: 400 17px {FONT_STACK}; fill: {SUBTLE_TEXT}; }}
        .legend {{ font: 600 14px {FONT_STACK}; fill: {TEXT_COLOR}; }}
        .panel-title {{ font: 800 22px {FONT_STACK}; fill: {HEADER_TEXT}; letter-spacing: 0.6px; }}
        .tick {{ font: 500 12px {FONT_STACK}; fill: {SUBTLE_TEXT}; }}
        .boat-label {{ font: 500 13px {FONT_STACK}; fill: white; }}
        .footer {{ font: 400 14px {FONT_STACK}; fill: {SUBTLE_TEXT}; }}
        .grid {{ stroke: {GRID_COLOR}; stroke-width: 1; }}
        .baseline {{ stroke: {PANEL_BORDER}; stroke-width: 1.25; }}
        .interval {{ stroke-width: {BAR_STROKE_WIDTH}; stroke-linecap: round; fill: none; }}
        .marker {{ stroke: white; stroke-width: 2; }}
        """,
        "</style>",
        f'<rect class="bg" width="{width}" height="{height}" />',
        '<title id="title">Club boat weight coverage by boat type</title>',
        '<desc id="subtitle"></desc>',
        svg_text(72, 40, "City of Bristol Rowing Club", "kicker"),
        svg_text(72, 82, "Boat Weight Coverage", "title"),
        svg_text(
            72,
            114,
            "Coverage uses stated weight ± 5 kg.",
            "subtitle",
        ),
        svg_text(
            72,
            135,
            "Deleted boats, and private boats are excluded.",
            "subtitle",
        ),
    ]

    legend_y = 70
    legend_x = 1260
    legend_both_y = legend_y + 52
    legend_both_top = legend_both_y - (BAR_STROKE_WIDTH / 2)
    legend_both_left = legend_x - (BAR_STROKE_WIDTH / 2)
    legend_both_width = 34 + BAR_STROKE_WIDTH
    svg.extend(
        [
            f'<line x1="{legend_x}" x2="{legend_x + 34}" y1="{legend_y}" y2="{legend_y}" '
            f'class="interval" stroke="{SCULL_COLOR}" />',
            svg_text(legend_x + 48, legend_y + 5, "scull", "legend"),
            f'<line x1="{legend_x}" x2="{legend_x + 34}" y1="{legend_y + 26}" y2="{legend_y + 26}" '
            f'class="interval" stroke="{SWEEP_COLOR}" />',
            svg_text(legend_x + 48, legend_y + 31, "sweep", "legend"),
            "<defs>",
            (
                f'<clipPath id="legend-both-clip">'
                f'<rect x="{legend_both_left:.1f}" y="{legend_both_top:.1f}" width="{legend_both_width:.1f}" height="{BAR_STROKE_WIDTH}" '
                f'rx="{BAR_STROKE_WIDTH / 2}" ry="{BAR_STROKE_WIDTH / 2}" />'
                "</clipPath>"
            ),
            "</defs>",
            (
                f'<rect x="{legend_both_left:.1f}" y="{legend_both_top:.1f}" width="{legend_both_width:.1f}" height="{BAR_STROKE_WIDTH}" '
                f'rx="{BAR_STROKE_WIDTH / 2}" ry="{BAR_STROKE_WIDTH / 2}" fill="{SCULL_COLOR}" />'
            ),
            (
                f'<rect x="{legend_both_left:.1f}" y="{legend_both_y:.1f}" width="{legend_both_width:.1f}" height="{BAR_STROKE_WIDTH / 2}" '
                f'fill="{SWEEP_COLOR}" clip-path="url(#legend-both-clip)" />'
            ),
            svg_text(legend_x + 48, legend_y + 57, "both", "legend"),
        ]
    )

    current_y = title_block
    for display_type in DISPLAY_BOAT_TYPES:
        safe_display_type = "".join(
            char if char.isalnum() else "-" for char in display_type.lower()
        ).strip("-")
        boats = grouped_boats[display_type]
        panel_height = (
            panel_header + axis_band + (len(boats) * row_height) + panel_padding_bottom
        )
        panel_x = 48
        panel_y = current_y
        panel_width = width - 96
        svg.append(
            f'<rect x="{panel_x}" y="{panel_y}" width="{panel_width}" height="{panel_height}" '
            f'rx="6" ry="6" class="panel" />'
        )
        svg.append(
            f'<rect x="{panel_x + 16}" y="{panel_y + 14}" width="{panel_width - 32}" height="30" '
            f'rx="4" ry="4" fill="{HEADER_FILL}" />'
        )

        svg.append(svg_text(72, panel_y + 36, display_type, "panel-title"))

        axis_top = panel_y + panel_header
        rows_top = axis_top + axis_band + row_height

        for weight in range(axis_min, axis_max + 1, 5):
            x = x_for_weight(weight)
            svg.append(
                f'<line x1="{x:.1f}" y1="{axis_top + 4:.1f}" x2="{x:.1f}" y2="{panel_y + panel_height - 18:.1f}" class="grid" />'
            )
            svg.append(svg_text(x, axis_top, f"{weight} kg", "tick", anchor="middle"))

        svg.append(
            f'<line x1="{left_margin:.1f}" y1="{axis_top + axis_band:.1f}" '
            f'x2="{left_margin + plot_width:.1f}" y2="{axis_top + axis_band:.1f}" class="baseline" />'
        )

        for index, boat in enumerate(boats):
            y = rows_top + index * row_height
            label = boat.name
            if boat.rigging == "scull":
                color = SCULL_COLOR
            elif boat.rigging == "sweep":
                color = SWEEP_COLOR
            else:  # both
                color = None

            if boat.rigging == "both":
                lower_x = x_for_weight(boat.lower)
                upper_x = x_for_weight(boat.upper)
                bar_left = lower_x - (BAR_STROKE_WIDTH / 2)
                bar_width = (upper_x - lower_x) + BAR_STROKE_WIDTH
                bar_top = y - (BAR_STROKE_WIDTH / 2)
                clip_id = f"both-clip-{safe_display_type}-{index}"
                svg.append(
                    "<defs>"
                    f'<clipPath id="{clip_id}">'
                    f'<rect x="{bar_left:.1f}" y="{bar_top:.1f}" width="{bar_width:.1f}" height="{BAR_STROKE_WIDTH}" '
                    f'rx="{BAR_STROKE_WIDTH / 2}" ry="{BAR_STROKE_WIDTH / 2}" />'
                    "</clipPath>"
                    "</defs>"
                )
                svg.append(
                    f'<rect x="{bar_left:.1f}" y="{bar_top:.1f}" width="{bar_width:.1f}" height="{BAR_STROKE_WIDTH}" '
                    f'rx="{BAR_STROKE_WIDTH / 2}" ry="{BAR_STROKE_WIDTH / 2}" fill="{SCULL_COLOR}" />'
                )
                svg.append(
                    f'<rect x="{bar_left:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{BAR_STROKE_WIDTH / 2}" '
                    f'fill="{SWEEP_COLOR}" clip-path="url(#{clip_id})" />'
                )
            else:
                svg.append(
                    f'<line x1="{x_for_weight(boat.lower):.1f}" y1="{y:.1f}" x2="{x_for_weight(boat.upper):.1f}" '
                    f'y2="{y:.1f}" class="interval" stroke="{color}" />'
                )
            if boat.approval_required:
                svg.append(
                    f'<circle cx="{x_for_weight(boat.lower):.1f}" cy="{y:.1f}" r="5" class="marker" fill="{APPROVAL_COLOR}" />'
                )
            # Place boat name at stated weight, replacing the marker dot.
            svg.append(
                svg_text(
                    x_for_weight(boat.weight),
                    y + 4,
                    label,
                    "boat-label",
                    anchor="middle",
                    fill="white",
                )
            )

        current_y += panel_height + panel_gap

    svg.append("</svg>")
    return "\n".join(svg)


def print_dropped_boat_log(dropped_boats: list[DroppedBoat]) -> None:
    print(f"Dropped {len(dropped_boats)} boats from coverage:")
    grouped_boats: dict[str, list[DroppedBoat]] = defaultdict(list)
    for boat in dropped_boats:
        grouped_boats[boat.reason].append(boat)

    for reason in DROP_REASON_PRIORITY:
        boats_for_reason = grouped_boats.get(reason, [])
        if not boats_for_reason:
            continue

        print(f" {reason} ({len(boats_for_reason)}):")
        for boat in boats_for_reason:
            details = []
            if boat.weight is not None:
                details.append(f"{boat.weight} kg")
            if boat.owner_id is not None:
                details.append(f"owner {boat.owner_id}")
            detail_text = f" ({', '.join(details)})" if details else ""
            print(f"  - {boat.name} [{boat.boat_type}]{detail_text}")


def main() -> None:
    args = parse_args()
    boats_path = Path(args.boats)
    svg_path = Path(args.svg_out)

    boats, dropped_boats = load_boats(boats_path)
    grouped_boats: dict[str, list[Boat]] = defaultdict(list)
    for boat in boats:
        grouped_boats[boat.display_type].append(boat)
    for display_type in DISPLAY_BOAT_TYPES:
        grouped_boats.setdefault(display_type, [])

    summary = make_summary(grouped_boats)
    svg_path.write_text(render_svg(grouped_boats, summary))

    print(f"Wrote {svg_path}")
    print_dropped_boat_log(dropped_boats)


if __name__ == "__main__":
    main()
