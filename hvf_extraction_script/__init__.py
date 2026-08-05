# SPDX-FileCopyrightText: 2026 Lions Eye Institute Limited
# SPDX-License-Identifier: GPL-3.0-only

"""DICOM-only HFA parsing package."""

from .dicom import parse_hfa_dicom
from .models import HFAPlot, HFAResult, ThresholdPoint, ThresholdResult, UnsupportedHFADataError

__all__ = ["HFAPlot", "HFAResult", "ThresholdPoint", "ThresholdResult", "UnsupportedHFADataError", "parse_hfa_dicom"]
