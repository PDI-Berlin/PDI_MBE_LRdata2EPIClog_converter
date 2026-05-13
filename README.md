# PDI_MBE_LRdata2EPIClog_converter

## Overview

This tool monitors a directory for `.dat` files, converts the data into EPIC log format, and stores the output in a structured daily logging directory.

It reads instrument parameters from a `settings.xml` file to ensure full traceability of measurement conditions.

---

## Features

- Watches a folder for new or modified `.dat` files
- Waits until files are stable (inactivity period) before processing
- Converts time-offset intensity data into absolute timestamped format
- Appends results to daily log files (`LR.txt`)
- Writes a daily metadata log (`LR_meta.txt`) with instrument settings per measurement
- Enriches the `LR.txt` header with laser wavelength and measurement angle on first creation
- Copies `settings.xml` as a per-measurement metadata snapshot next to each `.dat` file

---

## Output Structure

```
<output_dir>/
└── YYYY/
    └── YYYY_MM_DD/
        ├── LR.txt
        └── LR_meta.txt
```

### LR.txt

Daily log of converted reflectance data. On first creation, the header includes instrument parameters:

```
EPIC LR Log File

LaserWavelength_nm: 640
IncidenceAngle_deg: 60

Date,LR
13/05/2026 09:45:34.650735,0.000276
13/05/2026 09:45:35.267517,0.000278
...
```

### LR_meta.txt

Created in the same dated folder. One row is appended each time a `.dat` file is processed, recording the instrument settings at that moment:

```
EPIC LR_metadata Log File

Date,LR_wavelength_nm,LR_angle_deg
13/05/2026 09:45:34.519140,640,60
13/05/2026 10:12:01.123456,532,45
```

---

## Requirements

- Python 3.x
- `watchdog` library

Install dependency:

```
pip install watchdog
```

---

## Configuration

All paths and timing are set at the top of the script:

```python
LR_META_DIR       = r"d:\PDIRS"                          # folder to watch for .dat files
EPIC_LOGS_DIR     = r"c:\EPIC\Latest\Logs"               # where LR.txt and LR_meta.txt go
SETTINGS_XML_PATH = r"F:\PDI Reflectance Monitor\settings.xml"
INACTIVITY_PERIOD = 20                                   # seconds of inactivity before processing
```

---

## Usage

Run the script:

```
python pdi_lr_watchdog.py
```

The script runs continuously, logging all activity to `watchdog_debug.log` in the same directory.

---

## Input Format

`.dat` files must be tab-separated with two columns — time offset in seconds and intensity:

```
0.0	0.000276
0.5	0.000280
1.0	0.000278
```

Timestamps are computed by adding each offset to the file's creation time.

---

## Notes

- Files are processed only after `INACTIVITY_PERIOD` seconds of no modification, to avoid reading partial writes.
- `LR_meta.txt` records one row per processed `.dat` file — useful for tracking if instrument settings changed during a session.
- A copy of `settings.xml` is saved next to each source `.dat` file as `<filename>_metadata.xml` for per-measurement traceability.