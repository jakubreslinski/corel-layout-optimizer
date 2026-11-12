"""A small, deterministic Skyline packer for fast fitness evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Hashable


@dataclass(frozen=True)
class SkylineRectangle:
    """A rectangle placed by the Skyline packer."""

    x: float
    y: float
    width: float
    height: float
    rid: Hashable


class SkylinePacker:
    """Pack rectangles from left to right at the lowest available skyline."""

    def __init__(self, width: float) -> None:
        if width <= 0:
            raise ValueError("width must be positive.")
        self.width = width
        self._skyline: list[list[float]] = [[0.0, width, 0.0]]
        self._rectangles: list[SkylineRectangle] = []

    def add_rect(self, width: float, height: float, rid: Hashable = None) -> None:
        if width <= 0 or height <= 0:
            raise ValueError("Rectangle dimensions must be positive.")
        if width > self.width:
            return

        best: tuple[float, float, int] | None = None
        for index, (start, segment_width, _) in enumerate(self._skyline):
            if width > self._available_width(index, width):
                continue
            y = self._height_at(index, width)
            candidate = (y, start, index)
            if best is None or candidate < best:
                best = candidate

        if best is None:
            return

        y, x, index = best
        self._raise_skyline(x, width, y + height)
        self._rectangles.append(SkylineRectangle(x, y, width, height, rid))

    def rect_list(self) -> list[tuple[int, float, float, float, float, Hashable]]:
        return [
            (0, rectangle.x, rectangle.y, rectangle.width, rectangle.height, rectangle.rid)
            for rectangle in self._rectangles
        ]

    def _available_width(self, index: int, width: float) -> float:
        available = 0.0
        for _, segment_width, _ in self._skyline[index:]:
            available += segment_width
            if available >= width:
                return available
        return available

    def _height_at(self, index: int, width: float) -> float:
        remaining = width
        height = 0.0
        for _, segment_width, segment_height in self._skyline[index:]:
            height = max(height, segment_height)
            remaining -= segment_width
            if remaining <= 0:
                break
        return height

    def _raise_skyline(self, x: float, width: float, height: float) -> None:
        end = x + width
        updated: list[list[float]] = []
        for start, segment_width, segment_height in self._skyline:
            segment_end = start + segment_width
            if segment_end <= x or start >= end:
                updated.append([start, segment_width, segment_height])
                continue
            if start < x:
                updated.append([start, x - start, segment_height])
            if start < end and segment_end > x:
                overlap_start = max(start, x)
                overlap_end = min(segment_end, end)
                updated.append([overlap_start, overlap_end - overlap_start, height])
            if segment_end > end:
                updated.append([end, segment_end - end, segment_height])

        merged: list[list[float]] = []
        for segment in updated:
            if merged and merged[-1][2] == segment[2]:
                merged[-1][1] += segment[1]
            else:
                merged.append(segment)
        self._skyline = merged


def pack_rectangles(
    rectangles: list[tuple[float, float, Hashable]],
    max_width: float,
) -> SkylinePacker:
    """Pack ``(width, height, id)`` tuples and return the packer."""
    packer = SkylinePacker(max_width)
    for width, height, rid in rectangles:
        packer.add_rect(width, height, rid)
    return packer
