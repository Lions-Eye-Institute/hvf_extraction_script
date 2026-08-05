"""Optional integration tests for the local, non-versioned HFA sample corpus."""

from hashlib import sha256
import json
import os
from pathlib import Path
import unittest

from pydicom import dcmread

from hvf_extraction_script import ThresholdResult, UnsupportedHFADataError, parse_hfa_dicom


SAMPLE_ROOT = os.environ.get("HFA_SAMPLE_DIR")
THREE_IN_ONE_SAMPLE_ROOT = os.environ.get("HFA_3IN1_SAMPLE_DIR")
EXPECTED_SAMPLES = {
    "formats/hfa-3.dcm": ("24-2C", "SITA-Faster", "Right", "OFF", "ONL", 64),
    "formats/hfa-II-i.dcm": ("24-2", "SITA Standard", "Right", 33, "WNL", 54),
    "laterality/left.dcm": ("24-2C", "SITA-Faster", "Left", "OFF", "ONL", 64),
    "laterality/right.dcm": ("24-2C", "SITA-Faster", "Right", "OFF", "ONL", 64),
    "patterns/10-2.dcm": ("10-2", "SITA Standard", "Right", "OFF", None, 68),
    "patterns/24-2.dcm": ("24-2", "SITA Standard", "Left", "OFF", "ONL", 54),
    "patterns/24-2C.dcm": ("24-2C", "SITA-Faster", "Right", "OFF", "ONL", 64),
    "patterns/30-2.dcm": ("30-2", "SITA Standard", "Right", "OFF", "WNL", 76),
    "strategies/sita-fast.dcm": ("24-2", "SITA Fast", "Left", "OFF", "WNL", 54),
    "strategies/sita-faster.dcm": ("24-2C", "SITA-Faster", "Left", "OFF", "ONL", 64),
    "strategies/sita-standard.dcm": ("24-2", "SITA Standard", "Right", "OFF", "Borderline", 54),
}
EXPECTED_PLOT_DIGESTS = {
    "formats/hfa-3.dcm": {"raw": "81f0276f45dc4ca7c5ed1cb5187dfa82f400c5e47e039be3e34c4a54a013f11d", "tdv": "be6a6fe1fda53a1fa6ff079f65291b9a492978c21f94e35a0c12050b31654707", "tdp": "52f64f510e1cc41e0748a5e527af7e0a3c440bd9be7bfe74c06a248c42adf4c1", "pdv": "5d20e7f1c0fc7b4bc535591ac35c81e084a39410f3d07483d9373aadd06ebd8c", "pdp": "65b86d629b0cf0b1d2db68c020275c489782bcc3eb554db6e2e2519874072a79"},
    "formats/hfa-II-i.dcm": {"raw": "c9d1cf6897ccb8a2fe6b64d9603ed5c764358857b0ca3e60f62ce8768032d6e2", "tdv": "3f6c804d338490f0b2a7e4fa4a6b55a6c8a96ec1a4e48c13fa17648b7b137348", "tdp": "0a91ece079643af616a60dfa9eedd6bac9a746c2dff61e4fc2f942fe09807e77", "pdv": "bd466205371113df6378b8f98620ef9417b95404ff65d3221257c3830e4284ed", "pdp": "b9d2a74818b67f1cd458e7286f8cf5aa12308006e0ebc650f1860502e7eb9da0"},
    "laterality/left.dcm": {"raw": "3efee6a6479c33fd0e42daa22a2df15a6cf94fc064592879bbd6f7edc83b3c75", "tdv": "7e72401fb498290fb5f4ff88b58d8fc9189cbd119fbfaedb9aadd0ec32d43111", "tdp": "0a1ab7f4fbf8a2850859342487a571e419b089d4900d1a6e64a0ad89300619a4", "pdv": "71519b755bf7cfdb4198951a6bd90eaec2ea4c382733be056cbb9ef7ce69502f", "pdp": "15f7eb9322fec1cc48bf8c3142d890df4ef6abd6de661f448c845a6e0cb23a69"},
    "laterality/right.dcm": {"raw": "81f0276f45dc4ca7c5ed1cb5187dfa82f400c5e47e039be3e34c4a54a013f11d", "tdv": "be6a6fe1fda53a1fa6ff079f65291b9a492978c21f94e35a0c12050b31654707", "tdp": "52f64f510e1cc41e0748a5e527af7e0a3c440bd9be7bfe74c06a248c42adf4c1", "pdv": "5d20e7f1c0fc7b4bc535591ac35c81e084a39410f3d07483d9373aadd06ebd8c", "pdp": "65b86d629b0cf0b1d2db68c020275c489782bcc3eb554db6e2e2519874072a79"},
    "patterns/10-2.dcm": {"raw": "15dcc3a09fa1df2075d4615230246648a326c6d4f7b7619b343399edda971ff0", "tdv": "7f0ba458d32b64214209612e90ed3440dfcdb615db6fa5dbd67b6c2808c166f3", "tdp": "91d29a045bd6cf6c07203ea89a24c477fc88ab7df37f8d289b21708e7d954851", "pdv": "e2558e2a7ddc5a4aaa8b21a090c3c60c3881bf00320d2c910d7f49d0f61fc7e7", "pdp": "d33bc53ce1855753b8f4a51ae44815d8cba00514456466b283fa19a0b1917987"},
    "patterns/24-2.dcm": {"raw": "d66946f16bacdc62ed0f7b7a32f3f06c0624a6f19ffb7907a5399cd09bfa2fc5", "tdv": "012dac4e7e3b39fb4c33bf5bc89d75c9ce9086a028c2951db1c8db4dcc0fe5df", "tdp": "d5f0792e4b26f066fb1017c1b596fcf131f3255d22873fd37ead240a49c9d1b1", "pdv": "aa70004c841c803ae58f423b596433f421e34b2436d7c543bfaaeeb556388089", "pdp": "cdea189d175f1e9060bbcb8f3c0bf750e61076966a1daedc92669650026588bb"},
    "patterns/24-2C.dcm": {"raw": "81f0276f45dc4ca7c5ed1cb5187dfa82f400c5e47e039be3e34c4a54a013f11d", "tdv": "be6a6fe1fda53a1fa6ff079f65291b9a492978c21f94e35a0c12050b31654707", "tdp": "52f64f510e1cc41e0748a5e527af7e0a3c440bd9be7bfe74c06a248c42adf4c1", "pdv": "5d20e7f1c0fc7b4bc535591ac35c81e084a39410f3d07483d9373aadd06ebd8c", "pdp": "65b86d629b0cf0b1d2db68c020275c489782bcc3eb554db6e2e2519874072a79"},
    "patterns/30-2.dcm": {"raw": "93455b3feb59c0bfddec272cbdaa3a4953b4fe64af7f2baad45f96de435c266d", "tdv": "2ed7e05500a2d2758462308b44034489a98e9beec210d117eba0f72f0d538c8f", "tdp": "f994eb443c223caf54f0b344773c33ef38684a6ea9ffa3e3ece1f3489d96ab9c", "pdv": "a59c789cf8ae9a9cab3ca988aca05335e012ec9736c10c638c4e1940fc8a2353", "pdp": "98628c047ea220ea829967ef84052a5a4ad332d15e77524dffe7203b33b1e05b"},
    "strategies/sita-fast.dcm": {"raw": "ab12415e419a230cc10657ae6f9359cf0ef8f6673b3a1a9e111b89f9af62b8e0", "tdv": "876312eec0a4080989495928a363db2ff7f46004c0c4bd90cba45dbae1448efe", "tdp": "2b6e283f35f3cc6057395e931304d8442a673347948851461a24036dc107d584", "pdv": "2be57a51465a9aca039122f34ad001b1f670fd5332a78f340919b843e97146f5", "pdp": "3c4eda132582fba41361e69ae9dbe3ca1d0fb8f35c6bf3b25340103a38564238"},
    "strategies/sita-faster.dcm": {"raw": "3efee6a6479c33fd0e42daa22a2df15a6cf94fc064592879bbd6f7edc83b3c75", "tdv": "7e72401fb498290fb5f4ff88b58d8fc9189cbd119fbfaedb9aadd0ec32d43111", "tdp": "0a1ab7f4fbf8a2850859342487a571e419b089d4900d1a6e64a0ad89300619a4", "pdv": "71519b755bf7cfdb4198951a6bd90eaec2ea4c382733be056cbb9ef7ce69502f", "pdp": "15f7eb9322fec1cc48bf8c3142d890df4ef6abd6de661f448c845a6e0cb23a69"},
    "strategies/sita-standard.dcm": {"raw": "7f83bcda95093bc69b5f92b647b65a947864df4859b728f9fdd907d6b9522278", "tdv": "b9365d2c202ee40bcd145ff7a569ee98d00f399582aab8961e2a1824d2352d2f", "tdp": "67c7915ba5c425c74c03b69a0927529525952a8d5a5af5502c4281d0e4f08deb", "pdv": "a7a1932d44cdaaec458a95d1a53d3f8402a8f008b0b678c97dee4641503818ac", "pdp": "e2332a713b57fba0a5d2434fc0120b0f21c02d0f372157106c97b2772e46cc0e"},
}
REJECTED_SAMPLES = {
    "rejects/esterman-binocular.dcm": "Esterman Binocular",
    "rejects/esterman-monocular.dcm": "Esterman Monocular",
}
THRESHOLD_SAMPLES = {
    "rejects/3in1macula.dcm": ("3-in-1 Macula", "Full Threshold", "Left", 16, 4),
}


def _plot_digest(values) -> str:
    """Return a stable digest of every coordinate and value in one plot."""
    entries = [[x, y, value] for (x, y), value in sorted(values.items())]
    encoded = json.dumps(entries, ensure_ascii=True, separators=(",", ":")).encode()
    return sha256(encoded).hexdigest()


@unittest.skipUnless(SAMPLE_ROOT, "Set HFA_SAMPLE_DIR to run the local sample-corpus tests.")
class SampleCorpusTests(unittest.TestCase):
    def test_every_sample_matches_the_supported_contract(self):
        root = Path(SAMPLE_ROOT)
        for relative_path, expected in EXPECTED_SAMPLES.items():
            with self.subTest(sample=relative_path):
                result = parse_hfa_dicom(dcmread(root / relative_path, stop_before_pixels=True))
                pattern, strategy, laterality, fovea, ght, point_count = expected
                self.assertEqual(result.metadata["field_size"], pattern)
                self.assertEqual(result.metadata["strategy"], strategy)
                self.assertEqual(result.metadata["laterality"], laterality)
                self.assertEqual(result.metadata["fovea"], fovea)
                self.assertEqual(result.metadata["ght"], ght)
                self.assertEqual(len(result.raw.values), point_count)
                self.assertEqual(set(result.raw.coordinates), set(result.tdv.coordinates))
                self.assertEqual(set(result.raw.coordinates), set(result.tdp.coordinates))
                self.assertEqual(set(result.raw.coordinates), set(result.pdv.coordinates))
                self.assertEqual(set(result.raw.coordinates), set(result.pdp.coordinates))
                for plot_name, expected_digest in EXPECTED_PLOT_DIGESTS[relative_path].items():
                    with self.subTest(plot=plot_name):
                        self.assertEqual(_plot_digest(getattr(result, plot_name).values), expected_digest)

    def test_known_unsupported_samples_are_explicitly_rejected(self):
        root = Path(SAMPLE_ROOT)
        for relative_path, expected_pattern in REJECTED_SAMPLES.items():
            with self.subTest(sample=relative_path):
                dataset = dcmread(root / relative_path, stop_before_pixels=True)
                with self.assertRaisesRegex(UnsupportedHFADataError, expected_pattern):
                    parse_hfa_dicom(dataset)

    def test_known_full_threshold_macula_samples_are_parsed(self):
        root = Path(SAMPLE_ROOT)
        for relative_path, expected in THRESHOLD_SAMPLES.items():
            with self.subTest(sample=relative_path):
                result = parse_hfa_dicom(dcmread(root / relative_path, stop_before_pixels=True))
                field_size, strategy, laterality, point_count, retest_count = expected
                self.assertIsInstance(result, ThresholdResult)
                self.assertEqual(result.metadata["field_size"], field_size)
                self.assertEqual(result.metadata["strategy"], strategy)
                self.assertEqual(result.metadata["laterality"], laterality)
                self.assertEqual(len(result.points), point_count)
                self.assertEqual(sum(point.retest_sensitivity is not None for point in result.points.values()), retest_count)


@unittest.skipUnless(THREE_IN_ONE_SAMPLE_ROOT, "Set HFA_3IN1_SAMPLE_DIR to run the local 3-in-1 sample-corpus tests.")
class ThreeInOneSampleCorpusTests(unittest.TestCase):
    def test_full_threshold_macula_is_parsed_without_normative_plots(self):
        dataset = dcmread(Path(THREE_IN_ONE_SAMPLE_ROOT) / "3in1/test_types/mtt.dcm", stop_before_pixels=True)

        result = parse_hfa_dicom(dataset)

        self.assertIsInstance(result, ThresholdResult)
        self.assertEqual(result.metadata["field_size"], "3-in-1 Macula")
        self.assertEqual(result.metadata["strategy"], "Full Threshold")
        self.assertEqual(result.metadata["laterality"], "Left")
        self.assertEqual(len(result.points), 16)
        self.assertEqual(sum(point.retest_sensitivity is not None for point in result.points.values()), 4)
        self.assertNotIn("md", result.metadata)
