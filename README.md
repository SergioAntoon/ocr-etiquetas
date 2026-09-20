# OCR-etiquetas

Automatic extraction of numeric codes (18 digits, SSCC/GS1 type) from logistics label photographs using OCR with neural networks ([EasyOCR](https://github.com/JaidedAI/EasyOCR)).

Designed for large batches of mobile phone photos: poor lighting, rotated labels, HEIC format, and hundreds or thousands of files that need to be processed without losing progress if the process is interrupted.

## Features

* **OCR error tolerance.** Flexible regular expression that accepts characters commonly confused with digits (`O/0`, `I/1`, `S/5`, `B/8`…) and then normalizes them into digits.
* **GS1 check digit validation.** The `--validate-sscc` option discards incorrect readings using the SSCC modulo 10 algorithm: a single incorrectly read digit is enough for the code to be rejected.
* **Multi-angle search.** Tests rotations of 0°, 90°, 180°, and 270°, with configurable image scaling and contrast enhancement.
* **Rescue mode.** A second aggressive pass (grayscale conversion and forced EasyOCR internal parameters) for images that the standard pass cannot resolve, while also recording the raw OCR text for manual review.
* **Safe resume.** Results are written incrementally to CSV; when restarting the process, already processed files are skipped and duplicates are not generated.
* **HEIC/HEIF support** in addition to common image formats.

## Installation

Requires Python 3.10 or higher.

```bash
git clone https://github.com/SergioAntoon/ocr-etiquetas
cd ocr-etiquetas

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
pip install -e .                 # installs the `ocr-etiquetas` command
```

> **GPU:** EasyOCR relies on PyTorch. To enable CUDA acceleration, install the `torch` build matching your CUDA version before installing the dependencies. Without a GPU, use the `--cpu` option.

## Usage

Process an entire folder:

```bash
ocr-etiquetas extract ./photos --output results/codes.csv
```

With check digit validation and without GPU:

```bash
ocr-etiquetas extract ./photos -s results/codes.csv --validate-sscc --cpu
```

Resume an interrupted batch and retry only failed items:

```bash
ocr-etiquetas extract ./photos -s results/codes.csv --retry-failed
```

Rescue pass on specific images:

```bash
ocr-etiquetas rescue ./photos -s results/rescue.csv -i IMG_0042.heic IMG_0117.jpg
```

It also works without installing the package:

```bash
python -m ocr_etiquetas extract ./photos -s results/codes.csv
```

### Main options

| Option            | Description                  | Default        |
| ----------------- | ---------------------------- | -------------- |
| `--prefix`        | Known code prefix            | `4260`         |
| `--length`        | Total code length            | `18`           |
| `--validate-sscc` | Filters by GS1 check digit   | disabled       |
| `--angles`        | Rotations to test (degrees)  | `0 90 180 270` |
| `--scale`         | Image enlargement factor     | `2`            |
| `--contrast`      | Contrast enhancement         | `1.5`          |
| `--cpu`           | Forces execution without GPU | disabled       |
| `-v, --verbose`   | Detailed trace output        | disabled       |

### Output format

CSV file with one row per detected code:

```csv
file,code,method,ocr_text
IMG_0042.heic,426000123456789012,standard,
IMG_0117.jpg,,no_result,
```

The `method` column distinguishes standard readings from rescue readings and marks files without results, which are candidates for manual review.

## Project structure

```text
src/ocr_etiquetas/
├── __init__.py      Public package API
├── __main__.py      `python -m ocr_etiquetas` entry point
├── almacen.py       CSV persistence and resume logic
├── cli.py           Command-line interface
├── limpieza.py      Character normalization and GS1 validation
└── ocr.py           Image preprocessing and extraction with EasyOCR
```

## Results

The model has been evaluated on a dataset of **526 real-world images** collected from a logistics environment.

### Detection Statistics

| Result | Count | Percentage |
|---|---:|---:|
| Correctly identified in the first run | 485 | 92.2% |
| Recovered using rescue mode | 10 | 1.9% |
| Correctly rejected (no code present or unreadable code) | 13 | 2.5% |
| Readable codes not identified by the system | 18 | 3.4% |
| Total images evaluated | 526 | 100% |

### Summary

- **495/526 images** were correctly identified after combining the main OCR pipeline and the rescue mode.
- **13/526 images** were correctly classified as cases where no valid SSCC could be extracted.
- **18 images** contained apparently readable SSCC codes but were not successfully detected by the system.

### Overall performance

Considering both the main pipeline and the rescue process, the system achieved:

**94.1% successful SSCC recovery rate**

### Error Analysis

The remaining failures were mainly related to:

- poor image quality,
- extreme perspective distortion,
- reflections or uneven lighting,
- variations in label printing quality,
- limitations of the OCR engine under difficult conditions.

These results were obtained using real production-like images. Due to the sensitive nature of the logistics information contained in the dataset, the evaluation images are not publicly available.

> An image is considered correctly identified when the extracted SSCC matches the expected value and passes the corresponding format validation checks.

## Technical notes

The SSCC check digit is calculated using the GS1 modulo 10 algorithm: the first 17 digits are weighted using alternating multipliers of 3 and 1, and the check digit is the complement to the next multiple of ten. It is a highly effective quality filter against typical OCR mistakes, although it is only applicable if the codes are actually SSCC codes; therefore, validation is optional.

## Tests

```bash
pip install pytest
PYTHONPATH=src pytest -q
```

## Roadmap

* [x] Unit tests for code cleaning and validation.
* [ ] Parallel batch processing (multiprocessing) for very large folders.
* [ ] Preliminary label region detection to reduce background noise.
* [ ] Summary report (accuracy rate by method).

## License

All Rights Reserved -See LICENSE

## Author

**Sergio Antón** — Computer Engineering Student, University of Zaragoza (Spain), 2026.
