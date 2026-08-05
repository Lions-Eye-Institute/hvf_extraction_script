# DICOM parser API

The public API for this fork is:

```python
from pydicom import dcmread
from hvf_extraction_script import parse_hfa_dicom

dataset = dcmread("visual-field.dcm", stop_before_pixels=True)
result = parse_hfa_dicom(dataset)
```

`parse_hfa_dicom()` accepts a pydicom `Dataset` and returns an `HFAResult` or `ThresholdResult`. File I/O deliberately remains outside the package API so callers can obtain datasets from a file, DICOMweb, C-MOVE receiver, or another authorised source.

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

`ThresholdResult` represents Full Threshold 3-in-1 Macula measurements, which do not include normative/deviation analyses. Its `points` mapping is keyed by source coordinate and contains immutable `ThresholdPoint` values with `sensitivity`, `stimulus_result`, `retest_seen`, and `retest_sensitivity` fields. `ThresholdResult.coordinates` and `ThresholdResult.at(x, y)` provide the equivalent coordinate accessors.

The current parser preserves DICOM numeric values directly:

- `raw`, `tdv`, and `pdv` are integer values or `None` when a value is absent.
- `tdp` and `pdp` are probability values as supplied by DICOM, such as `0.0`, `5.0`, `2.0`, `1.0`, or `0.5`.

## Metadata

`HFAResult.metadata` contains these clinical/test fields:

| Key | Value |
| --- | --- |
| `test_date` | `datetime.date` or `None` |
| `laterality` | `Right` or `Left` |
| `fixation_losses` | fraction string, for example `"1/10"` |
| `false_positive`, `false_negative` | estimated percentage as an integer, or a fraction string |
| `field_size` | `10-2`, `24-2`, `24-2C`, or `30-2` |
| `strategy` | `SITA Standard`, `SITA Fast`, or `SITA-Faster` |
| `duration_seconds` | integer or `None` |
| `fovea` | integer sensitivity when measured; otherwise `"OFF"` |
| `pupil_diameter` | float or `None` |
| `refraction` | mapping with `sphere`, `cylinder`, and `axis` |
| `md`, `psd` | float or `None` |
| `vfi` | integer percentage value or `None` |
| `ght` | `Abnormally High`, `Borderline`, `Borderline / General Reduction`, `General Reduction of Sensitivity`, `WNL`, `ONL`, or `None` when no GHT result is present |

Patient name, identifier, and date of birth are intentionally not part of this API.

`ThresholdResult.metadata` contains the shared fields through `refraction`, but deliberately excludes `md`, `psd`, `vfi`, and `ght`: those analyses are absent from Full Threshold Macula OPV objects.

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

SITA pattern and strategy code recognition is independent: the parser accepts any recognised SITA pattern code with any recognised SITA strategy code. It does not restrict SITA inputs to a pattern/strategy combination whitelist.

| Full Threshold test pattern | Code value |
| --- | --- |
| 3-in-1 Macula | `111804` |

| Full Threshold strategy | Code value |
| --- | --- |
| Full Threshold | `111818` |

Pattern-deviation values must be present for `HFAResult`. Full Threshold 3-in-1 Macula is recognised only as the combination of the Macula pattern code (`111804`) and Full Threshold strategy code (`111818`), and returns a `ThresholdResult`. Macula paired with another strategy is rejected.

Full Threshold 10-2, 24-2, and 30-2 objects are ambiguous: OPV measurement storage has no indicator of whether they are 3-in-1 tests. The parser logs a warning containing “contact admin” and raises `UnsupportedHFADataError` rather than silently classify them. Esterman remains explicitly rejected. An unsupported SOP class, protocol code, duplicate coordinate, malformed numeric value, or absent pattern-deviation data raises `UnsupportedHFADataError`.

## Non-goals

This package does not provide spreadsheet serialisation, delimited export, bulk-processing commands, image/PDF OCR, or DICOM retrieval. The application owns presentation and export formatting, and DICOM retrieval remains the responsibility of the configured DICOM client/receiver.
