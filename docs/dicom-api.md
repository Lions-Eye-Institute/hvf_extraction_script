# DICOM parser API

The public API for this fork is:

```python
from pydicom import dcmread
from hvf_extraction_script import parse_hfa_dicom

dataset = dcmread("visual-field.dcm", stop_before_pixels=True)
result = parse_hfa_dicom(dataset)
```

`parse_hfa_dicom()` accepts a pydicom `Dataset` and returns an `HFAResult`. File I/O deliberately remains outside the package API so callers can obtain datasets from a file, DICOMweb, C-MOVE receiver, or another authorised source.

## Result model

`HFAResult` contains metadata and five coordinate-keyed `HFAPlot` values:

```python
result.metadata
result.raw
result.tdv
result.tdp
result.pdv
result.pdp
```

Each plot is indexed by its original DICOM coordinate, without a derived 10x10 grid:

```python
coordinate = (-3.0, 21.0)

raw_sensitivity = result.raw.values[coordinate]
total_deviation = result.tdv.values[coordinate]
total_deviation_probability = result.tdp.values[coordinate]
pattern_deviation = result.pdv.values[coordinate]
pattern_deviation_probability = result.pdp.values[coordinate]

# Equivalent convenience form:
raw_sensitivity = result.raw.at(-3.0, 21.0)
```

`HFAPlot.values` is immutable. `HFAPlot.coordinates` returns the coordinates contained in the plot.

The current parser preserves DICOM numeric values directly:

- `raw`, `tdv`, and `pdv` are integer values or `None` when a value is absent.
- `tdp` and `pdp` are probability values as supplied by DICOM, such as `0.0`, `5.0`, `2.0`, `1.0`, or `0.5`.

## Metadata

`result.metadata` contains only the exported clinical/test fields:

| Key | Value |
| --- | --- |
| `test_date` | `datetime.date` or `None` |
| `laterality` | `Right` or `Left` |
| `fixation_losses` | fraction string, for example `"1/10"` |
| `false_positive`, `false_negative` | estimated percentage as an integer, or a fraction string |
| `field_size` | `10-2`, `24-2`, `24-2C`, or `30-2` |
| `strategy` | `SITA Standard`, `SITA Fast`, or `SITA-Faster` |
| `duration_seconds` | integer or `None` |
| `pupil_diameter` | float or `None` |
| `refraction` | mapping with `sphere`, `cylinder`, and `axis` |
| `md`, `psd` | float or `None` |
| `vfi` | integer percentage value or `None` |

Patient name, identifier, and date of birth are intentionally not part of this API.

## Supported DICOM contract

The parser accepts only DICOM **Ophthalmic Visual Field Static Perimetry Measurements Storage** objects with these validated Zeiss protocol codes:

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

Pattern-deviation values must be present. An unsupported SOP class, protocol code, duplicate coordinate, malformed numeric value, or absent pattern-deviation data raises `UnsupportedHFADataError`.

## Non-goals

This package does not provide spreadsheet serialisation, delimited export, bulk-processing commands, image/PDF OCR, or DICOM retrieval. The application owns presentation and export formatting, and DICOM retrieval remains the responsibility of the configured DICOM client/receiver.
