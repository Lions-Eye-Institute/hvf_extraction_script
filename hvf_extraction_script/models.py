# SPDX-FileCopyrightText: 2026 Lions Eye Institute Limited
# SPDX-License-Identifier: GPL-3.0-only

"""Typed, coordinate-first results for HFA DICOM parsing."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, TypeAlias


Coordinate: TypeAlias = tuple[float, float]
PlotValue: TypeAlias = int | float | None


class UnsupportedHFADataError(ValueError):
    """The DICOM object is outside this fork's supported HFA contract."""


@dataclass(frozen=True)
class HFAPlot:
    """One pointwise HFA measurement, indexed by its source coordinate."""

    values: Mapping[Coordinate, PlotValue]

    @classmethod
    def from_values(cls, values: Mapping[Coordinate, PlotValue]) -> "HFAPlot":
        return cls(MappingProxyType(dict(values)))

    @property
    def coordinates(self) -> tuple[Coordinate, ...]:
        return tuple(self.values)

    def at(self, x: float, y: float) -> PlotValue:
        return self.values[(x, y)]


@dataclass(frozen=True)
class HFAResult:
    """Parsed HFA data with five coordinate-keyed pointwise plots."""

    metadata: Mapping[str, object]
    raw: HFAPlot
    tdv: HFAPlot
    tdp: HFAPlot
    pdv: HFAPlot
    pdp: HFAPlot
