# SPDX-FileCopyrightText: 2026 Lions Eye Institute Limited
# SPDX-License-Identifier: GPL-3.0-only

"""Parser for supported HFA static-perimetry DICOM objects."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
import logging
from typing import Any

from pydicom.dataset import Dataset

from .models import Coordinate, HFAPlot, HFAResult, PlotValue, ThresholdPoint, ThresholdResult, UnsupportedHFADataError


LOGGER = logging.getLogger(__name__)


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
FULL_THRESHOLD_CODE = "111818"
MACULA_PATTERN_CODE = "111804"
AMBIGUOUS_FULL_THRESHOLD_PATTERNS = {
    "111800": "24-2",
    "111801": "10-2",
    "111802": "30-2",
}
GHT_RESULT_CODES = {
    ("DCM", "111849"): "Abnormally High",
    ("DCM", "111848"): "Borderline",
    ("DCM", "111851"): "Borderline / General Reduction",
    ("DCM", "111850"): "General Reduction of Sensitivity",
    ("SRT", "M-00101"): "WNL",
    ("SCT", "125112009"): "WNL",
    ("DCM", "111847"): "ONL",
}
UNSUPPORTED_PATTERN_CODES = {
    "OPVTP117": "Esterman Monocular",
    "OPVTP118": "Esterman Binocular",
}


def parse_hfa_dicom(dataset: Dataset) -> HFAResult | ThresholdResult:
    """Parse a supported OPV static-perimetry DICOM dataset.

    This fork supports 10-2, 24-2, 24-2C and 30-2 tests using SITA Standard,
    SITA Fast or SITA-Faster, plus the unambiguous Full Threshold Macula pattern.
    Pointwise results are keyed by their original DICOM coordinates.
    """

    _require_static_perimetry(dataset)
    protocols = _sequence(dataset, "PerformedProtocolCodeSequence")
    if _has_protocol(protocols, FULL_THRESHOLD_CODE):
        if _has_protocol(protocols, MACULA_PATTERN_CODE):
            return _parse_threshold(dataset, "3-in-1 Macula")
        _reject_ambiguous_full_threshold(dataset, protocols)
    _reject_explicitly_unsupported_patterns(protocols)
    if _has_protocol(protocols, MACULA_PATTERN_CODE):
        raise UnsupportedHFADataError("3-in-1 Macula requires the Full Threshold strategy.")
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


def _parse_threshold(dataset: Dataset, field_size: str) -> ThresholdResult:
    points: dict[Coordinate, ThresholdPoint] = {}
    for point in _sequence(dataset, "VisualFieldTestPointSequence"):
        coordinate = _coordinate(point)
        if coordinate in points:
            raise UnsupportedHFADataError(f"Duplicate visual-field coordinate {coordinate!r}.")
        sensitivity = _number(getattr(point, "SensitivityValue", None), integer=True)
        if sensitivity is None:
            raise UnsupportedHFADataError(f"Point {coordinate!r} has no SensitivityValue.")
        stimulus_result = str(getattr(point, "StimulusResults", ""))
        if stimulus_result not in {"SEEN", "NOT SEEN"}:
            raise UnsupportedHFADataError(f"Point {coordinate!r} has unsupported StimulusResults {stimulus_result!r}.")
        retest_seen = _yes_no(getattr(point, "RetestStimulusSeen", None), "RetestStimulusSeen", coordinate)
        points[coordinate] = ThresholdPoint(
            sensitivity=sensitivity,
            stimulus_result=stimulus_result,
            retest_seen=retest_seen,
            retest_sensitivity=_number(getattr(point, "RetestSensitivityValue", None), integer=True),
        )
    if not points:
        raise UnsupportedHFADataError("VisualFieldTestPointSequence is empty.")
    return ThresholdResult.from_points(_metadata(dataset, field_size, "Full Threshold", include_global_indices=False), points)


def _metadata(dataset: Dataset, field_size: str, strategy: str, *, include_global_indices: bool = True) -> dict[str, object]:
    laterality = {"R": "Right", "L": "Left"}.get(str(getattr(dataset, "Laterality", "")))
    if laterality is None:
        raise UnsupportedHFADataError("Laterality must be R or L.")
    fixation = _first(_sequence(dataset, "FixationSequence"))
    catch_trial = _first(_sequence(dataset, "VisualFieldCatchTrialSequence"))
    results = _first(_sequence(dataset, "ResultsNormalsSequence"))
    eye = _clinical_eye(dataset, laterality)
    metadata = {
        "test_date": _date(getattr(dataset, "StudyDate", None)),
        "laterality": laterality,
        "fixation_losses": _ratio(fixation, "PatientNotProperlyFixatedQuantity", "FixationCheckedQuantity"),
        "false_positive": _reliability(catch_trial, "FalsePositivesEstimate", "FalsePositivesQuantity", "PositiveCatchTrialsQuantity"),
        "false_negative": _reliability(catch_trial, "FalseNegativesEstimate", "FalseNegativesQuantity", "NegativeCatchTrialsQuantity"),
        "field_size": field_size,
        "strategy": strategy,
        "duration_seconds": _number(getattr(dataset, "VisualFieldTestDuration", None), integer=True),
        "fovea": _fovea(dataset),
        "pupil_diameter": _number(getattr(eye, "PupilSize", None)),
        "refraction": _refraction(eye),
    }
    if include_global_indices:
        metadata.update(
            {
                "md": _number(getattr(results, "GlobalDeviationFromNormal", None)),
                "psd": _number(getattr(results, "LocalizedDeviationFromNormal", None)),
                "vfi": _vfi(dataset),
                "ght": _ght(dataset),
            }
        )
    return metadata


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


def _reject_explicitly_unsupported_patterns(protocols: Iterable[Dataset]) -> None:
    for protocol in protocols:
        pattern = UNSUPPORTED_PATTERN_CODES.get(str(getattr(protocol, "CodeValue", "")))
        if pattern is not None:
            raise UnsupportedHFADataError(f"{pattern} tests are explicitly unsupported.")


def _has_protocol(protocols: Iterable[Dataset], code: str) -> bool:
    return any(str(getattr(protocol, "CodeValue", "")) == code for protocol in protocols)


def _reject_ambiguous_full_threshold(dataset: Dataset, protocols: Iterable[Dataset]) -> None:
    for code, pattern in AMBIGUOUS_FULL_THRESHOLD_PATTERNS.items():
        if _has_protocol(protocols, code):
            instance_uid = str(getattr(dataset, "SOPInstanceUID", "")) or "unknown"
            LOGGER.warning(
                "Ambiguous Full Threshold %s OPV measurement (SOP Instance UID %s); contact admin. "
                "The OPV object cannot identify whether it is a 3-in-1 test.",
                pattern,
                instance_uid,
            )
            raise UnsupportedHFADataError(
                f"Ambiguous Full Threshold {pattern} test: the OPV object cannot identify whether it is a 3-in-1 test; contact admin."
            )


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


def _fovea(dataset: Dataset) -> int | str:
    if str(getattr(dataset, "FovealSensitivityMeasured", "")) != "YES":
        return "OFF"
    value = _number(getattr(dataset, "FovealSensitivity", None))
    if value is None:
        raise UnsupportedHFADataError("FovealSensitivity is absent although FovealSensitivityMeasured is YES.")
    return int(value)


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


def _ght(dataset: Dataset) -> str | None:
    for index in _sequence(dataset, "VisualFieldGlobalResultsIndexSequence"):
        observation = _first(_sequence(index, "DataObservationSequence"))
        concept = _first(_sequence(observation, "ConceptNameCodeSequence"))
        name = str(getattr(concept, "CodingSchemeDesignator", "")), str(getattr(concept, "CodeValue", ""))
        if name != ("DCM", "111855"):
            continue
        result = _first(_sequence(observation, "ConceptCodeSequence"))
        code = str(getattr(result, "CodingSchemeDesignator", "")), str(getattr(result, "CodeValue", ""))
        value = GHT_RESULT_CODES.get(code)
        if value is None:
            raise UnsupportedHFADataError(f"Unsupported Glaucoma Hemifield Test result code {code!r}.")
        return value
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


def _yes_no(value: Any, attribute: str, coordinate: Coordinate) -> bool | None:
    if value in (None, ""):
        return None
    text = str(value)
    if text == "YES":
        return True
    if text == "NO":
        return False
    raise UnsupportedHFADataError(f"Point {coordinate!r} has invalid {attribute} value {text!r}.")
