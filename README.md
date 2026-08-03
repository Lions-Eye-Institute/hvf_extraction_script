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

coordinate = (-3.0, 21.0)
raw_sensitivity = result.raw.at(*coordinate)
total_deviation = result.tdv.values[coordinate]
pattern_deviation_probability = result.pdp.values[coordinate]
```

Each of the five plots is keyed by its original DICOM `(x, y)` test-point coordinate:

- `result.raw` — raw sensitivity
- `result.tdv` — total deviation value
- `result.tdp` — total deviation probability
- `result.pdv` — pattern deviation value
- `result.pdp` — pattern deviation probability

See [the DICOM API reference](docs/dicom-api.md) for metadata, return types, supported protocol codes, and errors.

## Supported inputs

The parser supports these validated Zeiss test patterns and strategies:

| Test pattern | Strategy |
| --- | --- |
| 10-2 | SITA Standard |
| 24-2 | SITA Standard, SITA Fast |
| 24-2C | SITA-Faster |
| 30-2 | SITA Standard |

Esterman (monocular and binocular) and 3-in-1 macula tests are explicitly unsupported. Other unsupported protocol codes or absent pattern-deviation data raise `UnsupportedHFADataError`.

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

Build source and wheel distributions:

```shell
uv build
```

## Legacy image/OCR restoration

The upstream image/OCR implementation is intentionally excluded from the active package. It is recoverable from the local `legacy-image-ocr-baseline` Git tag; see [legacy restoration](docs/legacy-restoration.md).

## Licence

This project is licensed under the GNU General Public License v3.0 only. See [LICENSE.txt](LICENSE.txt) and [NOTICE](NOTICE).
