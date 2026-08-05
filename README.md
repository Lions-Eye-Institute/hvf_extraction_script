# HFA DICOM Parser

A small, coordinate-first parser for Humphrey Field Analyzer (HFA) DICOM static-perimetry data.

This fork parses DICOM **Ophthalmic Visual Field Static Perimetry Measurements Storage** objects. It does not provide image/PDF OCR, spreadsheet serialisation, bulk-processing commands, or DICOM network retrieval.

## Install

This project uses [uv](https://docs.astral.sh/uv/):

```shell
uv sync
```

The only runtime dependency is `pydicom`.

## Usage

```python
from pydicom import dcmread
from hvf_extraction_script import parse_hfa_dicom

dataset = dcmread("visual-field.dcm", stop_before_pixels=True)
result = parse_hfa_dicom(dataset)

# For standard SITA results:
coordinate = (-3.0, 21.0)
raw_sensitivity = result.raw.at(*coordinate)
total_deviation = result.tdv.values[coordinate]
pattern_deviation_probability = result.pdp.values[coordinate]
```

Standard SITA results provide five plots keyed by their original DICOM `(x, y)` test-point coordinate:

- `result.raw` — raw sensitivity
- `result.tdv` — total deviation value
- `result.tdp` — total deviation probability
- `result.pdv` — pattern deviation value
- `result.pdp` — pattern deviation probability

See [the DICOM API reference](docs/dicom-api.md) for metadata, return types, supported protocol codes, and errors.

## Supported inputs

The parser recognises these validated Zeiss SITA protocol codes independently. This is not a pattern/strategy combination whitelist: any recognised SITA pattern code may be paired with any recognised SITA strategy code.

| Test pattern | Code value |
| --- | --- |
| 10-2 | `111801` |
| 24-2 | `111800` |
| 24-2C | `OPVTP128` |
| 30-2 | `111802` |

| Strategy | Code value |
| --- | --- |
| SITA Standard | `111815` |
| SITA Fast | `111817` |
| SITA-Faster | `OPVTS101` |

| Test pattern | Code value |
| --- | --- |
| 3-in-1 Macula | `111804` |

| Strategy | Code value |
| --- | --- |
| Full Threshold | `111818` |

Full Threshold 3-in-1 Macula tests are returned as `ThresholdResult`, with coordinate-keyed point measurements rather than normative/deviation plots. The OPV measurement object does not contain the rendered report or normative analysis. Full Threshold 10-2, 24-2, and 30-2 objects are ambiguous: the OPV object cannot identify whether they are 3-in-1 tests, so the parser logs a warning containing “contact admin” and raises `UnsupportedHFADataError`.

## Testing

Run unit tests:

```shell
uv run python -m unittest discover -s tests -v
```

The anonymised HFA sample corpus remains outside the repository. To run its integration test:

```shell
HFA_SAMPLE_DIR=/path/to/all_hvf_samples \
  uv run python -m unittest discover -s tests -v
```

To include the local 3-in-1 Macula corpus:

```shell
HFA_3IN1_SAMPLE_DIR=/path/to/all_3in1_samples \
  uv run python -m unittest discover -s tests -v
```

Build source and wheel distributions:

```shell
uv build
```

## Legacy image/OCR restoration

The upstream image/OCR implementation is intentionally excluded from the active package. It is recoverable from the local `legacy-image-ocr-baseline` Git tag; see [legacy restoration](docs/legacy-restoration.md).

## Licence

This project is licensed under the GNU General Public License v3.0 only. See [LICENSE.txt](LICENSE.txt) and [NOTICE](NOTICE).
