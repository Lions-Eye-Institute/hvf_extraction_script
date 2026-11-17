from datetime import date
import unittest

from pydicom.dataset import Dataset
from pydicom.sequence import Sequence

from hvf_extraction_script import InvalidHFADataError, ThresholdResult, UnsupportedHFADataError, parse_hfa_dicom


def make_point(x, y, raw, pattern=True):
    normals = Dataset()
    normals.AgeCorrectedSensitivityDeviationValue = -2
    normals.AgeCorrectedSensitivityDeviationProbabilityValue = 5.0
    normals.GeneralizedDefectCorrectedSensitivityDeviationFlag = "YES" if pattern else "NO"
    if pattern:
        normals.GeneralizedDefectCorrectedSensitivityDeviationValue = -3
        normals.GeneralizedDefectCorrectedSensitivityDeviationProbabilityValue = 2.0

    point = Dataset()
    point.VisualFieldTestPointXCoordinate = x
    point.VisualFieldTestPointYCoordinate = y
    point.StimulusResults = "SEEN"
    point.SensitivityValue = raw
    point.VisualFieldTestPointNormalsSequence = Sequence([normals])
    return point


def make_dataset(pattern=True):
    dataset = Dataset()
    dataset.SOPClassUID = "1.2.840.10008.5.1.4.1.1.80.1"
    dataset.StudyDate = "20260731"
    dataset.Laterality = "R"
    dataset.VisualFieldTestDuration = 167
    dataset.FovealSensitivityMeasured = "NO"

    fixation = Dataset()
    fixation.PatientNotProperlyFixatedQuantity = 1
    fixation.FixationCheckedQuantity = 10
    dataset.FixationSequence = Sequence([fixation])

    catch = Dataset()
    catch.FalsePositivesEstimate = 4
    catch.FalseNegativesEstimate = 1
    dataset.VisualFieldCatchTrialSequence = Sequence([catch])

    results = Dataset()
    results.GlobalDeviationFromNormal = -0.3
    results.LocalizedDeviationFromNormal = 1.58
    dataset.ResultsNormalsSequence = Sequence([results])

    eye = Dataset()
    eye.PupilSize = None
    refraction = Dataset()
    refraction.SphericalLensPower = 3.25
    refraction.CylinderLensPower = 0
    refraction.CylinderAxis = 0
    eye.RefractiveParametersUsedOnPatientSequence = Sequence([refraction])
    dataset.OphthalmicPatientClinicalInformationRightEyeSequence = Sequence([eye])

    pattern_protocol = Dataset()
    pattern_protocol.CodeValue = "OPVTP128"
    strategy_protocol = Dataset()
    strategy_protocol.CodeValue = "OPVTS101"
    dataset.PerformedProtocolCodeSequence = Sequence([pattern_protocol, strategy_protocol])
    dataset.VisualFieldTestPointSequence = Sequence([make_point(3, 3, 28, pattern), make_point(5, 7, 31, pattern)])
    return dataset


def make_full_threshold_macula_dataset():
    dataset = make_dataset()
    dataset.PerformedProtocolCodeSequence[0].CodeValue = "111804"
    dataset.PerformedProtocolCodeSequence[1].CodeValue = "111818"
    dataset.VisualFieldTestPointSequence[0].RetestStimulusSeen = "YES"
    dataset.VisualFieldTestPointSequence[0].RetestSensitivityValue = 29
    return dataset


def set_ght(dataset, scheme, code):
    name = Dataset()
    name.CodingSchemeDesignator = "DCM"
    name.CodeValue = "111855"
    result = Dataset()
    result.CodingSchemeDesignator = scheme
    result.CodeValue = code
    observation = Dataset()
    observation.ConceptNameCodeSequence = Sequence([name])
    observation.ConceptCodeSequence = Sequence([result])
    index = Dataset()
    index.DataObservationSequence = Sequence([observation])
    dataset.VisualFieldGlobalResultsIndexSequence = Sequence([index])


def add_vfi(dataset, value, code="111852", meaning="Visual Field Index"):
    name = Dataset()
    name.CodingSchemeDesignator = "DCM"
    name.CodeValue = code
    name.CodeMeaning = meaning
    observation = Dataset()
    observation.ConceptNameCodeSequence = Sequence([name])
    observation.NumericValue = value
    index = Dataset()
    index.DataObservationSequence = Sequence([observation])
    existing = list(getattr(dataset, "VisualFieldGlobalResultsIndexSequence", None) or [])
    dataset.VisualFieldGlobalResultsIndexSequence = Sequence([*existing, index])


class ParseHFADicomTests(unittest.TestCase):
    def test_vfi_is_matched_by_concept_code(self):
        cases = [
            ("standard meaning", "111852", "Visual Field Index", 92),
            ("different meaning", "111852", "VFI", 92),
            ("meaning without the code", "999999", "Visual Field Index", None),
        ]
        for name, code, meaning, expected in cases:
            with self.subTest(name):
                dataset = make_dataset()
                set_ght(dataset, "DCM", "111847")
                add_vfi(dataset, 92, code=code, meaning=meaning)

                result = parse_hfa_dicom(dataset)

                self.assertEqual(result.metadata["vfi"], expected)
                self.assertEqual(result.metadata["ght"], "ONL")

    def test_missing_vfi_is_none(self):
        self.assertIsNone(parse_hfa_dicom(make_dataset()).metadata["vfi"])

    def test_returns_five_coordinate_keyed_plots(self):
        result = parse_hfa_dicom(make_dataset())

        self.assertEqual(result.metadata["test_date"], date(2026, 7, 31))
        self.assertEqual(result.metadata["field_size"], "24-2C")
        self.assertEqual(result.metadata["strategy"], "SITA-Faster")
        self.assertEqual(result.metadata["fovea"], "OFF")
        self.assertIsNone(result.metadata["ght"])
        self.assertIsNone(result.metadata["pupil_diameter"])
        self.assertEqual(set(result.raw.coordinates), {(3.0, 3.0), (5.0, 7.0)})
        self.assertEqual(result.raw.at(3.0, 3.0), 28)
        self.assertEqual(result.tdv.at(5.0, 7.0), -2)
        self.assertEqual(result.tdp.at(5.0, 7.0), 5.0)
        self.assertEqual(result.pdv.at(5.0, 7.0), -3)
        self.assertEqual(result.pdp.at(5.0, 7.0), 2.0)

    def test_measured_fovea_is_returned_as_an_integer(self):
        dataset = make_dataset()
        dataset.FovealSensitivityMeasured = "YES"
        dataset.FovealSensitivity = 33.9

        result = parse_hfa_dicom(dataset)

        self.assertEqual(result.metadata["fovea"], 33)

    def test_ght_codes_are_mapped_to_application_values(self):
        cases = [
            ("DCM", "111849", "Abnormally High"),
            ("DCM", "111848", "Borderline"),
            ("DCM", "111851", "Borderline / General Reduction"),
            ("DCM", "111850", "General Reduction of Sensitivity"),
            ("SRT", "M-00101", "WNL"),
            ("SCT", "125112009", "WNL"),
            ("DCM", "111847", "ONL"),
        ]
        for scheme, code, expected in cases:
            with self.subTest(scheme=scheme, code=code):
                dataset = make_dataset()
                set_ght(dataset, scheme, code)

                self.assertEqual(parse_hfa_dicom(dataset).metadata["ght"], expected)

    def test_unknown_ght_code_leaves_ght_blank_with_a_warning(self):
        dataset = make_dataset()
        set_ght(dataset, "DCM", "111999")
        dataset.VisualFieldGlobalResultsIndexSequence[0].DataObservationSequence[0].ConceptCodeSequence[0].CodeMeaning = "Something New"

        result = parse_hfa_dicom(dataset)

        self.assertIsNone(result.metadata["ght"])
        self.assertEqual(
            result.warnings,
            ("Unrecognised Glaucoma Hemifield Test result code DCM:111999 ('Something New'); GHT left blank.",),
        )
        self.assertEqual(result.raw.at(3.0, 3.0), 28)

    def test_unknown_ght_code_without_meaning_names_only_the_code(self):
        dataset = make_dataset()
        set_ght(dataset, "DCM", "111999")

        result = parse_hfa_dicom(dataset)

        self.assertEqual(
            result.warnings,
            ("Unrecognised Glaucoma Hemifield Test result code DCM:111999; GHT left blank.",),
        )

    def test_results_have_no_warnings_by_default(self):
        dataset = make_dataset()
        set_ght(dataset, "DCM", "111847")

        self.assertEqual(parse_hfa_dicom(dataset).warnings, ())
        self.assertEqual(parse_hfa_dicom(make_full_threshold_macula_dataset()).warnings, ())

    def test_missing_pattern_deviation_is_out_of_scope(self):
        with self.assertRaisesRegex(UnsupportedHFADataError, "Pattern deviation"):
            parse_hfa_dicom(make_dataset(pattern=False))

    def test_unknown_protocol_is_out_of_scope(self):
        dataset = make_dataset()
        dataset.PerformedProtocolCodeSequence[0].CodeValue = "UNKNOWN"

        with self.assertRaisesRegex(UnsupportedHFADataError, "test pattern"):
            parse_hfa_dicom(dataset)

    def test_esterman_patterns_are_explicitly_rejected(self):
        for code, pattern in (
            ("OPVTP117", "Esterman Monocular"),
            ("OPVTP118", "Esterman Binocular"),
        ):
            with self.subTest(pattern=pattern):
                dataset = make_dataset()
                dataset.PerformedProtocolCodeSequence[0].CodeValue = code

                with self.assertRaisesRegex(UnsupportedHFADataError, pattern):
                    parse_hfa_dicom(dataset)

    def test_full_threshold_macula_returns_non_normative_threshold_points(self):
        result = parse_hfa_dicom(make_full_threshold_macula_dataset())

        self.assertIsInstance(result, ThresholdResult)
        self.assertEqual(result.metadata["field_size"], "3-in-1 Macula")
        self.assertEqual(result.metadata["strategy"], "Full Threshold")
        self.assertNotIn("md", result.metadata)
        self.assertEqual(set(result.coordinates), {(3.0, 3.0), (5.0, 7.0)})
        point = result.at(3.0, 3.0)
        self.assertEqual(point.sensitivity, 28)
        self.assertEqual(point.stimulus_result, "SEEN")
        self.assertTrue(point.retest_seen)
        self.assertEqual(point.retest_sensitivity, 29)

    def test_macula_requires_full_threshold(self):
        dataset = make_dataset()
        dataset.PerformedProtocolCodeSequence[0].CodeValue = "111804"

        with self.assertRaisesRegex(UnsupportedHFADataError, "requires the Full Threshold"):
            parse_hfa_dicom(dataset)

    def test_macula_point_without_sensitivity_is_returned_as_none(self):
        dataset = make_full_threshold_macula_dataset()
        del dataset.VisualFieldTestPointSequence[1].SensitivityValue

        result = parse_hfa_dicom(dataset)

        self.assertIsInstance(result, ThresholdResult)
        self.assertIsNone(result.at(5.0, 7.0).sensitivity)
        self.assertEqual(result.at(5.0, 7.0).stimulus_result, "SEEN")
        self.assertEqual(result.at(3.0, 3.0).sensitivity, 28)

    def test_data_problems_raise_invalid_data_error(self):
        def duplicate_coordinate(dataset):
            dataset.VisualFieldTestPointSequence[1].VisualFieldTestPointXCoordinate = 3
            dataset.VisualFieldTestPointSequence[1].VisualFieldTestPointYCoordinate = 3

        def non_numeric_sensitivity(dataset):
            dataset.VisualFieldTestPointSequence[0].SensitivityValue = "abc"

        def invalid_study_date(dataset):
            dataset.StudyDate = "2026-07"

        def invalid_laterality(dataset):
            dataset.Laterality = "B"

        def invalid_stimulus_result(dataset):
            dataset.VisualFieldTestPointSequence[0].StimulusResults = "MAYBE"

        cases = [
            ("standard duplicate coordinate", make_dataset, duplicate_coordinate, "Duplicate"),
            ("standard non-numeric sensitivity", make_dataset, non_numeric_sensitivity, "numeric"),
            ("standard invalid study date", make_dataset, invalid_study_date, "StudyDate"),
            ("standard invalid laterality", make_dataset, invalid_laterality, "Laterality"),
            ("macula duplicate coordinate", make_full_threshold_macula_dataset, duplicate_coordinate, "Duplicate"),
            ("macula invalid stimulus result", make_full_threshold_macula_dataset, invalid_stimulus_result, "StimulusResults"),
        ]
        for name, factory, corrupt, pattern in cases:
            with self.subTest(name):
                dataset = factory()
                corrupt(dataset)

                with self.assertRaisesRegex(InvalidHFADataError, pattern):
                    parse_hfa_dicom(dataset)

    def test_unsupported_test_types_are_not_invalid_data(self):
        def unknown_pattern(dataset):
            dataset.PerformedProtocolCodeSequence[0].CodeValue = "UNKNOWN"

        def esterman(dataset):
            dataset.PerformedProtocolCodeSequence[0].CodeValue = "OPVTP117"

        def macula_without_full_threshold(dataset):
            dataset.PerformedProtocolCodeSequence[0].CodeValue = "111804"

        def wrong_sop_class(dataset):
            dataset.SOPClassUID = "1.2.3"

        for corrupt in (unknown_pattern, esterman, macula_without_full_threshold, wrong_sop_class):
            with self.subTest(corrupt.__name__):
                dataset = make_dataset()
                corrupt(dataset)

                with self.assertRaises(UnsupportedHFADataError) as context:
                    parse_hfa_dicom(dataset)
                self.assertNotIsInstance(context.exception, InvalidHFADataError)

    def test_ambiguous_full_threshold_patterns_warn_and_remain_rejected(self):
        for code, pattern in (("111801", "10-2"), ("111800", "24-2"), ("111802", "30-2")):
            with self.subTest(pattern=pattern):
                dataset = make_dataset()
                dataset.PerformedProtocolCodeSequence[0].CodeValue = code
                dataset.PerformedProtocolCodeSequence[1].CodeValue = "111818"

                with self.assertLogs("hvf_extraction_script.dicom", "WARNING") as logs:
                    with self.assertRaisesRegex(UnsupportedHFADataError, "contact admin"):
                        parse_hfa_dicom(dataset)
                self.assertIn(f"Full Threshold {pattern}", logs.output[0])
                self.assertIn("contact admin", logs.output[0])

    def test_zeiss_protocol_codes_for_supported_patterns_and_strategies(self):
        cases = [
            ("111801", "111815", "10-2", "SITA Standard"),
            ("111800", "111817", "24-2", "SITA Fast"),
            ("111802", "111815", "30-2", "SITA Standard"),
        ]

        for pattern_code, strategy_code, expected_pattern, expected_strategy in cases:
            with self.subTest(pattern=expected_pattern, strategy=expected_strategy):
                dataset = make_dataset()
                dataset.PerformedProtocolCodeSequence[0].CodeValue = pattern_code
                dataset.PerformedProtocolCodeSequence[1].CodeValue = strategy_code

                result = parse_hfa_dicom(dataset)

                self.assertEqual(result.metadata["field_size"], expected_pattern)
                self.assertEqual(result.metadata["strategy"], expected_strategy)

    def test_recognized_pattern_and_strategy_codes_are_independent(self):
        dataset = make_dataset()
        dataset.PerformedProtocolCodeSequence[0].CodeValue = "111801"
        dataset.PerformedProtocolCodeSequence[1].CodeValue = "111817"

        result = parse_hfa_dicom(dataset)

        self.assertEqual(result.metadata["field_size"], "10-2")
        self.assertEqual(result.metadata["strategy"], "SITA Fast")


if __name__ == "__main__":
    unittest.main()
