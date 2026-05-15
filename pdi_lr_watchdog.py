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

# ── Configuration ─────────────────────────────────────────────
LR_META_DIR       = r"d:\PDIRS"               #  source folder
EPIC_LOGS_DIR     = r"c:\EPIC\Latest\Logs"    #  destination folder
SETTINGS_XML_PATH = r"F:\PDI Reflectance Monitor\settings.xml"
INACTIVITY_PERIOD = 20                      
# ───────────────────────────────────────────────────────────────────────────




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
    Converts a .dat file to EPIC log format. Splits data into multiple 
    daily LR.txt files if the experiment spans across midnight.
    """
    try:
        base_time = datetime.fromtimestamp(os.path.getctime(file_path))
    except Exception as e:
        logging.error(f"Failed to get base_time for {file_path}: {e}")
        base_time = datetime.now()

    # ── 1. Read and Split Data by Day ────────────────────────────────────────
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()

        data_by_day = {}

        for line in lines:
            parts = line.strip().split("\t")
            if len(parts) != 2:
                continue
            try:
                # Calculate the timestamp for this specific line
                line_time = base_time + timedelta(seconds=float(parts[0]))
                day_key = line_time.strftime("%Y_%m_%d")
                year_key = line_time.strftime("%Y")
                
                # Format the line for EPIC
                formatted_line = f"{line_time.strftime('%d/%m/%Y %H:%M:%S.%f')},{parts[1]}\n"
                
                if day_key not in data_by_day:
                    data_by_day[day_key] = {"year": year_key, "lines": []}
                
                data_by_day[day_key]["lines"].append(formatted_line)
            except ValueError:
                continue

        # ── 2. Write to the respective daily files ───────────────────────────
        for day_str, info in data_by_day.items():
            dated_output_dir = os.path.join(output_base_dir, info["year"], day_str)
            os.makedirs(dated_output_dir, exist_ok=True)
            
            output_file_path = os.path.join(dated_output_dir, "LR.txt")
            file_exists = os.path.isfile(output_file_path)

            with open(output_file_path, 'a') as f:
                if not file_exists:
                    f.write("EPIC LR Log File\n\n")
                    f.write("Date,LR\n")
                f.writelines(info["lines"])
            
            logging.info(f"Appended {len(info['lines'])} lines to {output_file_path}")

    except Exception as e:
        logging.error(f"Failed to process multi-day file {file_path}: {e}")
        return

    # ── 3. Handle Metadata ──────
    wl, ang = _read_settings_values()
    
    start_day_dir = os.path.join(
        output_base_dir, 
        base_time.strftime("%Y"), 
        base_time.strftime("%Y_%m_%d")
    )
    os.makedirs(start_day_dir, exist_ok=True)
    
    meta_log_path = os.path.join(start_day_dir, "LR_meta.txt")
    meta_exists = os.path.isfile(meta_log_path)

    try:
        with open(meta_log_path, 'a') as f_meta:
            if not meta_exists:
                f_meta.write("EPIC LR_metadata Log File\n\n")
                f_meta.write("Date,LR_wavelength_nm,LR_angle_deg\n")
            f_meta.write(f"{base_time.strftime('%d/%m/%Y %H:%M:%S.%f')},{wl},{ang}\n")
    except Exception as e:
        logging.error(f"Meta log update failed: {e}")

    # ── 4. Precise XML Snapshot ────────────────────
    try:
        name_part, _ = os.path.splitext(os.path.basename(file_path))
        seconds_str = base_time.strftime("%S")
        if len(name_part) >= 10 and name_part[:10].isdigit():
            new_meta_name = f"{name_part[:10]}{seconds_str}{name_part[10:]}_metadata.xml"
        else:
            new_meta_name = f"{name_part}_{seconds_str}_metadata.xml"
        
        shutil.copy2(SETTINGS_XML_PATH, os.path.join(os.path.dirname(file_path), new_meta_name))
    except Exception as e:
        logging.error(f"XML copy failed: {e}")


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