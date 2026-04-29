# PDI_MBE_LRdata2EPIClog_converter

## Overview

This tool monitors a directory for `.dat` files, converts the data into EPIC log format, and stores the output in a structured logging directory.

It also attaches metadata from a `settings.xml` file to ensure traceability of measurement parameters.

---

## Features

* Watches a folder for new or modified `.dat` files
* Waits until files are stable before processing
* Converts time-offset data into timestamped format
* Appends results to daily log files (`LR.txt`)
* Copies `settings.xml` as metadata snapshot
* Extracts and logs:

  * Laser wavelength
  * Measurement angle

---

## Folder Structure

Output logs are stored as:

```
<output_dir>/
    └── YYYY/
        └── YYYY_MM_DD/
            └── LR.txt
```

---

## Requirements

* Python 3.x
* watchdog library

Install dependency:

```
pip install watchdog
```

---

## Usage

Update paths inside the script:

```python
lr_meta_dir = "D:\\PDIRS"
epic_logs_dir = "C:\\EPIC\\Latest\\Logs"
SETTINGS_XML_PATH = "F:\\PDI Reflectance Monitor\\settings.xml"
```

Run the script:

```
python src/lr_to_epic_watchdog.py
```

---

## Notes

* Files are processed only after a period of inactivity to avoid partial reads.
* Metadata is embedded into the log header when a new file is created.

