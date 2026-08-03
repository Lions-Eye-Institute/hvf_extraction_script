"""Optional integration tests for the local, non-versioned HFA sample corpus."""

import os
from pathlib import Path
import unittest

from pydicom import dcmread

from hvf_extraction_script import UnsupportedHFADataError, parse_hfa_dicom


SAMPLE_ROOT = os.environ.get("HFA_SAMPLE_DIR")
EXPECTED_SAMPLES = {
    "formats/hfa-3.dcm": ("24-2C", "SITA-Faster", "Right", 64),
    "formats/hfa-II-i.dcm": ("24-2", "SITA Standard", "Right", 54),
    "laterality/left.dcm": ("24-2C", "SITA-Faster", "Left", 64),
    "laterality/right.dcm": ("24-2C", "SITA-Faster", "Right", 64),
    "patterns/10-2.dcm": ("10-2", "SITA Standard", "Right", 68),
    "patterns/24-2.dcm": ("24-2", "SITA Standard", "Left", 54),
    "patterns/24-2C.dcm": ("24-2C", "SITA-Faster", "Right", 64),
    "patterns/30-2.dcm": ("30-2", "SITA Standard", "Right", 76),
    "strategies/sita-fast.dcm": ("24-2", "SITA Fast", "Left", 54),
    "strategies/sita-faster.dcm": ("24-2C", "SITA-Faster", "Left", 64),
    "strategies/sita-standard.dcm": ("24-2", "SITA Standard", "Right", 54),
}
REJECTED_SAMPLES = {
    "rejects/3in1macula.dcm": "3-in-1 Macula",
    "rejects/esterman-binocular.dcm": "Esterman Binocular",
    "rejects/esterman-monocular.dcm": "Esterman Monocular",
}


@unittest.skipUnless(SAMPLE_ROOT, "Set HFA_SAMPLE_DIR to run the local sample-corpus tests.")
class SampleCorpusTests(unittest.TestCase):
    def test_every_sample_matches_the_supported_contract(self):
        root = Path(SAMPLE_ROOT)
        for relative_path, expected in EXPECTED_SAMPLES.items():
            with self.subTest(sample=relative_path):
                result = parse_hfa_dicom(dcmread(root / relative_path, stop_before_pixels=True))
                pattern, strategy, laterality, point_count = expected
                self.assertEqual(result.metadata["field_size"], pattern)
                self.assertEqual(result.metadata["strategy"], strategy)
                self.assertEqual(result.metadata["laterality"], laterality)
                self.assertEqual(len(result.raw.values), point_count)
                self.assertEqual(set(result.raw.coordinates), set(result.tdv.coordinates))
                self.assertEqual(set(result.raw.coordinates), set(result.tdp.coordinates))
                self.assertEqual(set(result.raw.coordinates), set(result.pdv.coordinates))
                self.assertEqual(set(result.raw.coordinates), set(result.pdp.coordinates))

    def test_known_unsupported_samples_are_explicitly_rejected(self):
        root = Path(SAMPLE_ROOT)
        for relative_path, expected_pattern in REJECTED_SAMPLES.items():
            with self.subTest(sample=relative_path):
                dataset = dcmread(root / relative_path, stop_before_pixels=True)
                with self.assertRaisesRegex(UnsupportedHFADataError, expected_pattern):
                    parse_hfa_dicom(dataset)
