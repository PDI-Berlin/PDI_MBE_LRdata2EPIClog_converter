# PDI_MBE_LRdata2EPIClog_converter

## Overview

`PDI_MBE_LRdata2EPIClog_converter` is a Python-based automation utility for converting PDI reflectance monitor `.dat` files into EPIC-compatible log files.

The tool can operate in:

- **Watchdog mode** — continuously monitors a directory for incoming `.dat` files
- **Manual conversion mode** — converts a specific `.dat` file on demand

The converter automatically:

- transforms relative time offsets into absolute timestamps
- splits measurements across multiple daily log files when experiments span midnight
- records instrument metadata
- stores XML configuration snapshots for traceability

---

# Features

## Data Conversion

- Converts tab-separated `.dat` measurement files into EPIC log format
- Converts relative time offsets into absolute timestamps
- Automatically splits measurements into multiple daily folders if an experiment crosses midnight
- Appends data into daily `LR.txt` files

---

## Timing Modes

Two timing calculation methods are supported:

| Mode | Description |
|---|---|
| `-tc` | Uses OS file creation time as experiment start time (default) |
| `-tm` | Uses file modification time minus the last relative timestamp offset |

The `-tm` method is useful when `.dat` files are copied between systems and creation time no longer reflects the original experiment start time.

---

## Watchdog Monitoring

- Watches a target directory continuously for new or modified `.dat` files
- Waits for a configurable inactivity period before processing
- Prevents duplicate processing of already converted files
- Gracefully shuts down on manual interruption (`Ctrl+C`)

---

## Metadata Handling

- Reads instrument settings from `settings.xml`
- Writes instrument settings into:
  - `LR.txt` header (on first creation)
  - `LR_meta.txt` metadata log
- Creates a timestamped XML snapshot next to each processed `.dat` file for traceability

---

# Output Structure

```text
<output_dir>/
└── YYYY/
    └── YYYY_MM_DD/
        ├── LR.txt
        └── LR_meta.txt
```

---

# LR.txt Format

Daily EPIC-compatible reflectance log.

Example:

```text
EPIC LR Log File
LaserWavelength_nm: 640
IncidenceAngle_deg: 60

Date,LR
13/05/2026 09:45:34.650735,0.000276
13/05/2026 09:45:35.267517,0.000278
```

---

# LR_meta.txt Format

Metadata tracking log containing one entry per processed measurement file.

Example:

```text
EPIC LR_metadata Log File

Date,LR_wavelength_nm,LR_angle_deg
13/05/2026 09:45:34.519140,640,60
13/05/2026 10:12:01.123456,532,45
```

---

# XML Snapshot Format

For every processed `.dat` file, a timestamped copy of `settings.xml` is stored beside the source file:

```text
sample_20260520_153011_metadata.xml
```

This preserves the exact instrument configuration used during measurement.

---

# Requirements

- Python 3.x
- `watchdog`

Install dependency:

```bash
pip install watchdog
```

---

# Configuration

The script automatically detects whether it is running in:

- production environment (lab PC)
- development environment (local testing)

Configuration is defined near the top of the script.

## Production Configuration

```python
DEFAULT_LR_META_DIR    = r"d:\PDIRS"
DEFAULT_EPIC_LOGS_DIR  = r"c:\EPIC\Latest\Logs"
DEFAULT_SETTINGS_XML   = r"F:\PDI Reflectance Monitor\settings.xml"
INACTIVITY_PERIOD      = 20
```

## Development Configuration

```python
DEFAULT_LR_META_DIR    = r"source"
DEFAULT_EPIC_LOGS_DIR  = r"destination"
DEFAULT_SETTINGS_XML   = r"source\settings.xml"
INACTIVITY_PERIOD      = 5
```

---

# Usage

# 1. Watchdog Mode

Continuously monitor the configured input directory:

```bash
python pdi_lr_convert.py -w
```

Use modification-time timing mode:

```bash
python pdi_lr_convert.py -w -tm
```

---

# 2. Manual Conversion Mode

Convert a specific `.dat` file manually:

```bash
python pdi_lr_convert.py sample.dat settings.xml
```

Using modification-time timing mode:

```bash
python pdi_lr_convert.py -tm sample.dat settings.xml
```

---

# Command Line Options

| Option | Description |
|---|---|
| `-w` | Run in watchdog monitoring mode |
| `-tc` | Use file creation time (default) |
| `-tm` | Use modification time minus last offset |
| `dat_file` | Target `.dat` file for manual conversion |
| `xml_file` | Target `settings.xml` file |

---

# Input File Format

Input `.dat` files must contain two tab-separated columns:

```text
<time_offset_seconds>    <intensity>
```

Example:

```text
0.0	0.000276
0.5	0.000280
1.0	0.000278
```

---

# Logging

All runtime activity, warnings, and errors are written to:

```text
watchdog_debug.log
```

The log file includes:

- conversion events
- timing calculations
- XML parsing errors
- duplicate protection activity
- watchdog startup/shutdown events

---

# Processing Workflow

1. Detect `.dat` file creation/modification
2. Wait until file is stable (`INACTIVITY_PERIOD`)
3. Calculate experiment base time
4. Convert relative timestamps into absolute timestamps
5. Split data into daily output groups
6. Append data into `LR.txt`
7. Update `LR_meta.txt`
8. Copy timestamped XML snapshot
9. Mark file as processed

---

# Notes

- Files are processed only after a period of inactivity to avoid partial reads.
- Invalid or malformed data rows are skipped automatically.
- Empty or invalid `.dat` files are ignored and logged.
- UTF-8 decoding errors are ignored to improve robustness against malformed instrument output.
- The `-tm` timing mode assumes file modification time approximately matches experiment end time.

---

# Example

## Start watchdog monitoring

```bash
python pdi_lr_convert.py -w
```

Console output:

```text
Starting watchdog | folder: d:\PDIRS | timing: -tc
```

---

## Manual conversion

```bash
python pdi_lr_convert.py -tm test.dat settings.xml
```

Console output:

```text
Converting: test.dat
Settings:   settings.xml
Timing:     -tm
Done.
```