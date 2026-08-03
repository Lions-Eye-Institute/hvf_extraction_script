# SPDX-FileCopyrightText: 2026 Lions Eye Institute Limited
# SPDX-License-Identifier: GPL-3.0-only

"""Parser for supported HFA static-perimetry DICOM objects."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Any

from pydicom.dataset import Dataset

from .models import Coordinate, HFAPlot, HFAResult, PlotValue, UnsupportedHFADataError


PATTERN_CODES = {
    "111800": "24-2",
    "111801": "10-2",
    "111802": "30-2",
    "OPVTP128": "24-2C",
}
STRATEGY_CODES = {
    "111815": "SITA Standard",
    "111817": "SITA Fast",
    "OPVTS101": "SITA-Faster",
}


def parse_hfa_dicom(dataset: Dataset) -> HFAResult:
    """Parse a supported OPV static-perimetry DICOM dataset.

    This fork supports 10-2, 24-2, 24-2C and 30-2 tests using SITA Standard,
    SITA Fast or SITA-Faster. Every returned plot is keyed by the original DICOM
    ``(VisualFieldTestPointXCoordinate, VisualFieldTestPointYCoordinate)``.
    """

    _require_static_perimetry(dataset)
    protocols = _sequence(dataset, "PerformedProtocolCodeSequence")
    field_size = _require_protocol(protocols, PATTERN_CODES, "test pattern")
    strategy = _require_protocol(protocols, STRATEGY_CODES, "test strategy")
    _require_pattern_deviation(dataset)

    plots: dict[str, dict[Coordinate, PlotValue]] = {name: {} for name in ("raw", "tdv", "tdp", "pdv", "pdp")}
    for point in _sequence(dataset, "VisualFieldTestPointSequence"):
        coordinate = _coordinate(point)
        if coordinate in plots["raw"]:
            raise UnsupportedHFADataError(f"Duplicate visual-field coordinate {coordinate!r}.")
        normals = _first(_sequence(point, "VisualFieldTestPointNormalsSequence"))
        if not normals:
            raise UnsupportedHFADataError(f"Point {coordinate!r} has no VisualFieldTestPointNormalsSequence.")
        plots["raw"][coordinate] = _number(getattr(point, "SensitivityValue", None), integer=True)
        plots["tdv"][coordinate] = _number(getattr(normals, "AgeCorrectedSensitivityDeviationValue", None), integer=True)
        plots["tdp"][coordinate] = _number(getattr(normals, "AgeCorrectedSensitivityDeviationProbabilityValue", None))
        plots["pdv"][coordinate] = _number(getattr(normals, "GeneralizedDefectCorrectedSensitivityDeviationValue", None), integer=True)
        plots["pdp"][coordinate] = _number(getattr(normals, "GeneralizedDefectCorrectedSensitivityDeviationProbabilityValue", None))

    if not plots["raw"]:
        raise UnsupportedHFADataError("VisualFieldTestPointSequence is empty.")

    return HFAResult(
        metadata=_metadata(dataset, field_size, strategy),
        raw=HFAPlot.from_values(plots["raw"]),
        tdv=HFAPlot.from_values(plots["tdv"]),
        tdp=HFAPlot.from_values(plots["tdp"]),
        pdv=HFAPlot.from_values(plots["pdv"]),
        pdp=HFAPlot.from_values(plots["pdp"]),
    )


def _metadata(dataset: Dataset, field_size: str, strategy: str) -> dict[str, object]:
    laterality = {"R": "Right", "L": "Left"}.get(str(getattr(dataset, "Laterality", "")))
    if laterality is None:
        raise UnsupportedHFADataError("Laterality must be R or L.")
    fixation = _first(_sequence(dataset, "FixationSequence"))
    catch_trial = _first(_sequence(dataset, "VisualFieldCatchTrialSequence"))
    results = _first(_sequence(dataset, "ResultsNormalsSequence"))
    eye = _clinical_eye(dataset, laterality)
    return {
        "test_date": _date(getattr(dataset, "StudyDate", None)),
        "laterality": laterality,
        "fixation_losses": _ratio(fixation, "PatientNotProperlyFixatedQuantity", "FixationCheckedQuantity"),
        "false_positive": _reliability(catch_trial, "FalsePositivesEstimate", "FalsePositivesQuantity", "PositiveCatchTrialsQuantity"),
        "false_negative": _reliability(catch_trial, "FalseNegativesEstimate", "FalseNegativesQuantity", "NegativeCatchTrialsQuantity"),
        "field_size": field_size,
        "strategy": strategy,
        "duration_seconds": _number(getattr(dataset, "VisualFieldTestDuration", None), integer=True),
        "pupil_diameter": _number(getattr(eye, "PupilSize", None)),
        "refraction": _refraction(eye),
        "md": _number(getattr(results, "GlobalDeviationFromNormal", None)),
        "psd": _number(getattr(results, "LocalizedDeviationFromNormal", None)),
        "vfi": _vfi(dataset),
    }


def _require_static_perimetry(dataset: Dataset) -> None:
    expected = "1.2.840.10008.5.1.4.1.1.80.1"
    if str(getattr(dataset, "SOPClassUID", "")) != expected:
        raise UnsupportedHFADataError("Dataset is not Ophthalmic Visual Field Static Perimetry Measurements Storage.")


def _require_protocol(protocols: Iterable[Dataset], supported: dict[str, str], label: str) -> str:
    for protocol in protocols:
        value = supported.get(str(getattr(protocol, "CodeValue", "")))
        if value is not None:
            return value
    codes = ", ".join(str(getattr(protocol, "CodeValue", "")) for protocol in protocols)
    raise UnsupportedHFADataError(f"Unsupported {label} protocol code(s): {codes or 'none'}.")


def _require_pattern_deviation(dataset: Dataset) -> None:
    point = _first(_sequence(dataset, "VisualFieldTestPointSequence"))
    normals = _first(_sequence(point, "VisualFieldTestPointNormalsSequence"))
    if str(getattr(normals, "GeneralizedDefectCorrectedSensitivityDeviationFlag", "")) != "YES":
        raise UnsupportedHFADataError("Pattern deviation is not available in this OPV object.")


def _coordinate(point: Dataset) -> Coordinate:
    try:
        return float(point.VisualFieldTestPointXCoordinate), float(point.VisualFieldTestPointYCoordinate)
    except AttributeError as error:
        raise UnsupportedHFADataError("A visual-field test point has no coordinate.") from error


def _clinical_eye(dataset: Dataset, laterality: str) -> Dataset:
    attribute = "OphthalmicPatientClinicalInformationRightEyeSequence" if laterality == "Right" else "OphthalmicPatientClinicalInformationLeftEyeSequence"
    return _first(_sequence(dataset, attribute))


def _refraction(eye: Dataset) -> dict[str, int | float | None]:
    refraction = _first(_sequence(eye, "RefractiveParametersUsedOnPatientSequence"))
    return {
        "sphere": _number(getattr(refraction, "SphericalLensPower", None)),
        "cylinder": _number(getattr(refraction, "CylinderLensPower", None)),
        "axis": _number(getattr(refraction, "CylinderAxis", None), integer=True),
    }


def _vfi(dataset: Dataset) -> int | None:
    for index in _sequence(dataset, "VisualFieldGlobalResultsIndexSequence"):
        observation = _first(_sequence(index, "DataObservationSequence"))
        concept = _first(_sequence(observation, "ConceptNameCodeSequence"))
        if str(getattr(concept, "CodeMeaning", "")) == "Visual Field Index":
            return _number(getattr(observation, "NumericValue", None), integer=True)
    return None


def _reliability(dataset: Dataset, estimate: str, numerator: str, denominator: str) -> int | str | None:
    value = _number(getattr(dataset, estimate, None), integer=True)
    return value if value is not None else _ratio(dataset, numerator, denominator)


def _ratio(dataset: Dataset, numerator: str, denominator: str) -> str | None:
    top = _number(getattr(dataset, numerator, None), integer=True)
    bottom = _number(getattr(dataset, denominator, None), integer=True)
    return f"{top}/{bottom}" if top is not None and bottom is not None else None


def _date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    text = str(value)
    try:
        return date(int(text[0:4]), int(text[4:6]), int(text[6:8]))
    except (TypeError, ValueError) as error:
        raise UnsupportedHFADataError(f"StudyDate {text!r} is not a valid YYYYMMDD date.") from error


def _sequence(dataset: Dataset, attribute: str) -> list[Dataset]:
    return list(getattr(dataset, attribute, []) or [])


def _first(items: Iterable[Dataset]) -> Dataset:
    return next(iter(items), Dataset())


def _number(value: Any, integer: bool = False) -> int | float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise UnsupportedHFADataError(f"Expected a numeric DICOM value, got {value!r}.") from error
    return int(number) if integer else number
