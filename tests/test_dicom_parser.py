from datetime import date
import unittest

from pydicom.dataset import Dataset
from pydicom.sequence import Sequence

from hvf_extraction_script import UnsupportedHFADataError, parse_hfa_dicom


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


class ParseHFADicomTests(unittest.TestCase):
    def test_returns_five_coordinate_keyed_plots(self):
        result = parse_hfa_dicom(make_dataset())

        self.assertEqual(result.metadata["test_date"], date(2026, 7, 31))
        self.assertEqual(result.metadata["field_size"], "24-2C")
        self.assertEqual(result.metadata["strategy"], "SITA-Faster")
        self.assertEqual(result.metadata["fovea"], "OFF")
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

    def test_3_in_1_macula_pattern_is_explicitly_rejected(self):
        dataset = make_dataset()
        dataset.PerformedProtocolCodeSequence[0].CodeValue = "111804"

        with self.assertRaisesRegex(UnsupportedHFADataError, "3-in-1 Macula"):
            parse_hfa_dicom(dataset)

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
