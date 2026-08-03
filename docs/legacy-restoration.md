# Restoring legacy image/OCR extraction

This fork intentionally focuses on coordinate-first parsing of DICOM **Ophthalmic Visual Field Static Perimetry Measurements Storage** objects. The image/OCR implementation is not retained in the active DICOM-only surface, but it is recoverable from the local Git baseline tag:

```text
legacy-image-ocr-baseline
```

That tag points to commit `9ad0a96` (`fix: remove unneccessary scripting`), the final committed state that contains the upstream image/OCR implementation, packaged image templates, and the UV configuration required by those modules.

The tag currently exists locally. Publish it with the following command when this repository is ready to share the restoration reference:

```bash
git push origin legacy-image-ocr-baseline
```

## What the baseline contains

| Capability | Files and resources |
| --- | --- |
| Image-based extraction | `hvf_extraction_script/hvf_data/hvf_object.py` and `hvf_plot_array.py` |
| Value/percentile template recognition | `hvf_value.py`, `hvf_perc_icon.py`, and `hvf_data/{other_icons,perc_icons,value_icons}/` |
| Image, OCR, and matching helpers | `hvf_extraction_script/utilities/` |
| AWS Rekognition path | `utilities/ocr_utils.py` plus `boto3` |
| Optional local Tesseract path | `tesserocr` extra and system Tesseract libraries |
| Legacy object and display/export compatibility | `hvf_data/` and `hvf_manager/hvf_export.py` |

The upstream project does **not** provide a complete standalone PDF parser. Its image path accepts an OpenCV/NumPy image. A future PDF feature should rasterize a PDF page first, then use the restored image extraction logic or a new purpose-built parser.

## Inspecting the baseline

```bash
git show legacy-image-ocr-baseline:hvf_extraction_script/hvf_data/hvf_object.py
git show legacy-image-ocr-baseline:pyproject.toml
git ls-tree -r --name-only legacy-image-ocr-baseline -- hvf_extraction_script/
```

## Restoring on a feature branch

Do not restore the legacy files directly on the DICOM-only branch. Create a feature branch first:

```bash
git switch -c feature/image-ocr-restoration
git restore --source=legacy-image-ocr-baseline -- \
  hvf_extraction_script/hvf_data \
  hvf_extraction_script/utilities \
  hvf_extraction_script/hvf_manager/hvf_export.py
```

Restore image-template assets together with the classes that consume them. Then compare the baseline packaging metadata before adding only the dependencies required by the selected restored feature:

```bash
git diff legacy-image-ocr-baseline -- pyproject.toml
git show legacy-image-ocr-baseline:pyproject.toml
```

Typical image/OCR restoration requires `numpy`, `opencv-python`, `pillow`, `regex`, `fuzzysearch`, `fuzzywuzzy`, and `python-levenshtein`. AWS Rekognition additionally requires `boto3`; local Tesseract additionally requires the `tesserocr` Python package and host Tesseract development/runtime libraries.

## Integration boundary

Keep `parse_hfa_dicom()` and the coordinate-first result model independent of any restored OCR code. A restored image/PDF feature should convert its output at a deliberately defined boundary rather than reintroducing the former `Hvf_Object` API as the public DICOM interface.
