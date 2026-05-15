import os
import time
import logging
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logging.basicConfig(
    filename="watchdog_debug.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# # ── Configuration ─────────────────────────────────────────────
# LR_META_DIR       = r"d:\PDIRS"               #  source folder
# EPIC_LOGS_DIR     = r"c:\EPIC\Latest\Logs"    #  destination folder
# SETTINGS_XML_PATH = r"F:\PDI Reflectance Monitor\settings.xml"
# INACTIVITY_PERIOD = 20                      
# # ───────────────────────────────────────────────────────────────────────────

# ── Configuration for my local────────────────────────────────────────────────────────────

LR_META_DIR      = r"source"                 # Folder to watch for .dat files
EPIC_LOGS_DIR    = r"destination"            # Where LR.txt / LR_meta.txt go
SETTINGS_XML_PATH = r"source\settings.xml"  # Instrument settings file
INACTIVITY_PERIOD = 5                        # Seconds of inactivity before processing

# ─────────────────────────────────────────────────────────────────────────────


def _parse_float_from_text(text, default="NA"):
    """
    Parse a float from a scientific-notation string and return a clean string.
    Returns default if parsing fails.
    """
    try:
        value = float(str(text).strip())
        iv = int(round(value))
        if abs(value - iv) < 1e-9:
            return str(iv)
        return f"{value:.6g}"
    except Exception:
        return default


def _read_settings_values():
    """
    Read laser wavelength and measurement angle from settings.xml.
    Returns: (wavelength_str, angle_str)
    """
    try:
        tree = ET.parse(SETTINGS_XML_PATH)
        root = tree.getroot()
        wl_str  = _parse_float_from_text(root.findtext("./settings.laserWavelength"))
        ang_str = _parse_float_from_text(root.findtext("./settings.measurementAngle"))
        return wl_str, ang_str
    except Exception as e:
        logging.error(f"Failed to read settings.xml at {SETTINGS_XML_PATH}: {e}")
        return "NA", "NA"


def convert_lr_to_epic(file_path, output_base_dir):
    """
    Converts a .dat file to EPIC log format and writes/appends to LR.txt.
    Also writes LR_meta.txt and copies settings.xml next to the source file.
    """
    # ── NEW: Define base_time immediately from the file ──────────────────────
    try:
        base_time = datetime.fromtimestamp(os.path.getctime(file_path))
    except Exception as e:
        logging.error(f"Failed to get base_time for {file_path}: {e}")
        base_time = datetime.now() # Fallback

    now = datetime.now()

    # ── Build output paths ───────────────────────────────────────────────────
    try:
        dated_output_dir = os.path.join(
            output_base_dir,
            now.strftime("%Y"),
            now.strftime("%Y_%m_%d")
        )
        os.makedirs(dated_output_dir, exist_ok=True)

        output_file_path = os.path.join(dated_output_dir, "LR.txt")
        meta_log_path    = os.path.join(dated_output_dir, "LR_meta.txt")

        file_exists_before = os.path.isfile(output_file_path)
        meta_exists_before = os.path.isfile(meta_log_path)
    except Exception as e:
        logging.error(f"Failed to build output paths: {e}")
        return

    # ── 1. Convert .dat and append to LR.txt ─────────────────────────────────
    try:
        # Note: base_time is now defined above
        with open(file_path, 'r') as f:
            lines = f.readlines()

        converted_lines = []
        for line in lines:
            parts = line.strip().split("\t")
            if len(parts) != 2:
                continue
            try:
                new_time = base_time + timedelta(seconds=float(parts[0]))
                converted_lines.append(
                    f"{new_time.strftime('%d/%m/%Y %H:%M:%S.%f')},{parts[1]}\n"
                )
            except ValueError:
                logging.warning(f"Skipping invalid line: {line.strip()} in {file_path}")

        with open(output_file_path, 'a') as f:
            if not file_exists_before:
                f.write("EPIC LR Log File\n\n")
                f.write("Date,LR\n")
            f.writelines(converted_lines)

        logging.info(f"Appended converted data to: {output_file_path}")

    except Exception as e:
        logging.error(f"Failed to convert file {file_path}: {e}")
        return

    # ── 2. Read settings ──────────────────────────────────────────────────────
    wl, ang = _read_settings_values()

    # ── 3. Enrich LR.txt header if newly created ──────────────────────────────
    try:
        if not file_exists_before and os.path.isfile(output_file_path):
            with open(output_file_path, "r") as f:
                lines = f.readlines()
            header_index = next(
                (i for i, l in enumerate(lines) if "Date,LR" in l), -1
            )
            if header_index != -1:
                data_lines = lines[header_index + 1:]
                with open(output_file_path, "w") as f:
                    f.write("EPIC LR Log File\n\n")
                    f.write(f"LaserWavelength_nm: {wl}\n")
                    f.write(f"IncidenceAngle_deg: {ang}\n\n")
                    f.write("Date,LR\n")
                    f.writelines(data_lines)
                logging.info(f"Enriched LR.txt header: wavelength={wl}, angle={ang}")
    except Exception as e:
        logging.error(f"Header update failed: {e}")

    # ── 4. Append to LR_meta.txt ──────────────────────────────────────────────
    try:
        with open(meta_log_path, 'a') as f_meta:
            if not meta_exists_before:
                f_meta.write("EPIC LR_metadata Log File\n\n")
                f_meta.write("Date,LR_wavelength_nm,LR_angle_deg\n")
            
            # CHANGE: Use base_time.strftime instead of now.strftime
            f_meta.write(f"{base_time.strftime('%d/%m/%Y %H:%M:%S.%f')},{wl},{ang}\n")
            
        logging.info(f"Updated metadata log with base_time: {meta_log_path}")
    except Exception as e:
        logging.error(f"Failed to update LR_meta.txt: {e}")

    # ── 5. Copy settings.xml next to the source .dat file ────────────────────
    try:
        base, _ = os.path.splitext(file_path)
        shutil.copy2(SETTINGS_XML_PATH, base + "_metadata.xml")
        logging.info(f"Copied settings.xml to: {base}_metadata.xml")
    except Exception as e:
        logging.error(f"Metadata XML copy failed: {e}")


class LRMetaDataHandler(FileSystemEventHandler):
    def __init__(self, output_dir, inactivity_period=30):
        self.output_dir = output_dir
        self.inactivity_period = inactivity_period
        self.file_timestamps = {}

    def on_modified(self, event):
        if event.src_path.endswith('.dat'):
            self.file_timestamps[event.src_path] = time.time()

    def check_and_process_files(self):
        current_time = time.time()
        files_to_process = [
            fp for fp, ts in list(self.file_timestamps.items())
            if current_time - ts > self.inactivity_period
        ]
        for file_path in files_to_process:
            logging.info(f"Processing file: {file_path}")
            try:
                convert_lr_to_epic(file_path, self.output_dir)
                del self.file_timestamps[file_path]
            except Exception as e:
                logging.error(f"Error processing {file_path}: {e}")


if __name__ == "__main__":
    try:
        event_handler = LRMetaDataHandler(
            output_dir=EPIC_LOGS_DIR,
            inactivity_period=INACTIVITY_PERIOD
        )
        observer = Observer()
        observer.schedule(event_handler, path=LR_META_DIR, recursive=False)
        observer.start()
        logging.info("Started watchdog. Monitoring for new .dat files...")

        while True:
            event_handler.check_and_process_files()
            time.sleep(5)

    except Exception as e:
        logging.error(f"Watchdog crashed: {e}")
        time.sleep(5)