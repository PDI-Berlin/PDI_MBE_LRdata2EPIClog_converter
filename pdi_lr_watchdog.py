import os
import sys
import time
import logging
import shutil
import argparse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ── Logging Configuration ───────────────────────────────────────────────────
logging.basicConfig(
    filename="watchdog_debug.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ── Smart Configuration (Auto-detects Environment) ─────────────────────────
if os.path.exists(r"d:\PDIRS"):
    # 🧪 PRODUCTION (Lab PC Settings)
    DEFAULT_LR_META_DIR    = r"d:\PDIRS"               
    DEFAULT_EPIC_LOGS_DIR  = r"c:\EPIC\Latest\Logs"    
    DEFAULT_SETTINGS_XML   = r"F:\PDI Reflectance Monitor\settings.xml"
    INACTIVITY_PERIOD      = 20                        
else:
    # 💻 DEVELOPMENT (Your Local Simulation Settings)
    DEFAULT_LR_META_DIR    = r"source"                 
    DEFAULT_EPIC_LOGS_DIR  = r"destination"            
    DEFAULT_SETTINGS_XML   = r"source\settings.xml"    
    INACTIVITY_PERIOD      = 5                         
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


def _read_settings_values(settings_xml_path):
    """
    Read laser wavelength and measurement angle from the specified settings.xml path.
    Returns: (wavelength_str, angle_str)
    """
    try:
        tree = ET.parse(settings_xml_path)
        root = tree.getroot()
        wl_str  = _parse_float_from_text(root.findtext("./settings.laserWavelength"))
        ang_str = _parse_float_from_text(root.findtext("./settings.measurementAngle"))
        return wl_str, ang_str
    except Exception as e:
        logging.error(f"Failed to read settings.xml at {settings_xml_path}: {e}")
        return "NA", "NA"


def calculate_base_time(file_path, method="tc"):
    """
    Calculates the absolute experiment start time (base_time).
    'tc': Uses OS file creation time.
    'tm': Uses OS file modification time minus the last entry's relative offset.
    """
    if method == "tm":
        logging.warning("Using -tm assumes file modification time precisely equals experiment end time.")
        try:
            mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            last_offset = 0.0
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # Loop backwards to find the last valid data row containing a timestamp offset
            for line in reversed(lines):
                parts = line.strip().split("\t")
                if len(parts) == 2:
                    try:
                        last_offset = float(parts[0])
                        break
                    except ValueError:
                        continue
            
            base_time = mod_time - timedelta(seconds=last_offset)
            logging.info(f"Calculated base_time via modification math (-tm): {base_time}")
            return base_time
        except Exception as e:
            logging.error(f"Failed calculating -tm for {file_path} ({e}). Falling back to creation time.")
            print(f"Warning: Failed calculating -tm ({e}). Falling back to creation time.")

    # Default 'tc' behavior
    try:
        return datetime.fromtimestamp(os.path.getctime(file_path))
    except Exception as e:
        logging.error(f"Failed to get file creation time for {file_path}: {e}")
        return datetime.now()


def convert_lr_to_epic(file_path, output_base_dir, settings_xml_path, timing_method="tc"):
    """
    Converts a .dat file to EPIC log format. Splits data into multiple 
    daily LR.txt files if the experiment spans across midnight.
    """
    # Calculate start time dynamically based on the chosen timing flag
    base_time = calculate_base_time(file_path, method=timing_method)

    # Read instrument metadata settings up front for headers and backups
    wl, ang = _read_settings_values(settings_xml_path)

    # ── 1. Read and Split Data by Day ────────────────────────────────────────
    try:
        with open(file_path, r'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        data_by_day = {}

        for line in lines:
            parts = line.strip().split("\t")
            if len(parts) != 2:
                continue
            try:
                line_time = base_time + timedelta(seconds=float(parts[0]))
                day_key = line_time.strftime("%Y_%m_%d")
                year_key = line_time.strftime("%Y")
                
                formatted_line = f"{line_time.strftime('%d/%m/%Y %H:%M:%S.%f')},{parts[1]}\n"
                
                if day_key not in data_by_day:
                    data_by_day[day_key] = {"year": year_key, "lines": []}
                
                data_by_day[day_key]["lines"].append(formatted_line)
            except ValueError:
                continue

        # Guard checking against completely empty or invalid data matrices
        if not data_by_day:
            logging.warning(f"No valid target data structures found inside processed target file: {file_path}")
            return False

        # ── 2. Write to the respective daily files ───────────────────────────
        for day_str, info in data_by_day.items():
            dated_output_dir = os.path.join(output_base_dir, info["year"], day_str)
            os.makedirs(dated_output_dir, exist_ok=True)
            
            output_file_path = os.path.join(dated_output_dir, "LR.txt")
            file_exists = os.path.isfile(output_file_path)

            with open(output_file_path, 'a', encoding='utf-8') as f:
                if not file_exists:
                    f.write("EPIC LR Log File\n")
                    f.write(f"LaserWavelength_nm: {wl}\n")
                    f.write(f"IncidenceAngle_deg: {ang}\n\n")
                    f.write("Date,LR\n")
                f.writelines(info["lines"])
            
            logging.info(f"Appended {len(info['lines'])} lines to {output_file_path}")

    except Exception as e:
        logging.error(f"Failed to process multi-day file {file_path}: {e}")
        return False

    # ── 3. Handle Metadata Log Entry ─────────────────────────────────────────
    start_day_dir = os.path.join(
        output_base_dir, 
        base_time.strftime("%Y"), 
        base_time.strftime("%Y_%m_%d")
    )
    os.makedirs(start_day_dir, exist_ok=True)
    
    meta_log_path = os.path.join(start_day_dir, "LR_meta.txt")
    meta_exists = os.path.isfile(meta_log_path)

    try:
        with open(meta_log_path, 'a', encoding='utf-8') as f_meta:
            if not meta_exists:
                f_meta.write("EPIC LR_metadata Log File\n\n")
                f_meta.write("Date,LR_wavelength_nm,LR_angle_deg\n")
            f_meta.write(f"{base_time.strftime('%d/%m/%Y %H:%M:%S.%f')},{wl},{ang}\n")
    except Exception as e:
        logging.error(f"Meta log update failed: {e}")

    # ── 4. Robust Universal XML Snapshot Name Calculation ────────────────────
    try:
        name_part, _ = os.path.splitext(os.path.basename(file_path))
        timestamp_str = base_time.strftime("%Y%m%d_%H%M%S")
        new_meta_name = f"{name_part}_{timestamp_str}_metadata.xml"
        
        shutil.copy2(settings_xml_path, os.path.join(os.path.dirname(file_path), new_meta_name))
    except Exception as e:
        logging.error(f"XML copy failed: {e}")

    return True


class LRMetaDataHandler(FileSystemEventHandler):
    def __init__(self, output_dir, settings_xml_path, inactivity_period=30, timing_method="tc"):
        self.output_dir = output_dir
        self.settings_xml_path = settings_xml_path
        self.inactivity_period = inactivity_period
        self.timing_method = timing_method
        self.file_timestamps = {}
        # Fixed #1: Track fully processed files to eliminate duplication hazards
        self.processed_files = set()

    def on_created(self, event):
        # Fixed #2: Track file creation for software engines writing complete logs instantly
        if not event.is_directory and event.src_path.endswith('.dat'):
            if event.src_path in self.processed_files:
                return
            self.file_timestamps[event.src_path] = time.time()

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.dat'):
            if event.src_path in self.processed_files:
                return
            self.file_timestamps[event.src_path] = time.time()

    def check_and_process_files(self):
        current_time = time.time()
        files_to_process = [
            fp for fp, ts in list(self.file_timestamps.items())
            if current_time - ts > self.inactivity_period
        ]
        for file_path in files_to_process:
            # Re-verify lock status before running thread logic 
            if file_path in self.processed_files:
                self.file_timestamps.pop(file_path, None)
                continue

            logging.info(f"Processing background file: {file_path}")
            try:
                success = convert_lr_to_epic(
                    file_path=file_path,
                    output_base_dir=self.output_dir,
                    settings_xml_path=self.settings_xml_path,
                    timing_method=self.timing_method
                )
                if success:
                    # Lock processing to prevent downstream duplicate loops
                    self.processed_files.add(file_path)
                
                # Fixed #4: Thread safe map eviction
                self.file_timestamps.pop(file_path, None)
            except Exception as e:
                logging.error(f"Error processing background file {file_path}: {e}")

_holder_lock_fd = None
def main():
    # ── SINGLE INSTANCE LOCK ──────────────────────────────────────────────────────
    LOCK_FILE = "pdi_lr_watchdog.lock"

    try:
        
        _holder_lock_fd = open(LOCK_FILE, 'ab+')
        if os.name == 'nt':  
            import msvcrt
            try:
                # Seek to start boundary position to verify cross-process lock mapping
                _holder_lock_fd.seek(0)
                msvcrt.locking(_holder_lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
            except IOError:
                print(f"\n⚠️ WARNING: This script is already running in another terminal!")
                print("Please close the other instance before running this one.")
                sys.exit(1)
        else:  
            import fcntl
            try:
                fcntl.flock(_holder_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except IOError:
                print(f"\n⚠️ WARNING: This script is already running in another terminal!")
                sys.exit(1)
    except Exception as e:
        print(f"Lockfile initialization failed: {e}")
        sys.exit(1)
    # ──────────────────────────────────────────────────────────────────────────────
    

    parser = argparse.ArgumentParser(
        prog="python pdi_lr_watchdog.py",
        description="Convert PDI .dat files to EPIC log format."
    )
    
    # Modes
    parser.add_argument("-w", action="store_true", help="Run in watchdog mode (monitors folder continuously)")
    
    timing_group = parser.add_mutually_exclusive_group()
    timing_group.add_argument("-tc", action="store_true", help="Use file creation time as base_time (default)")
    timing_group.add_argument("-tm", action="store_true", help="Use file modified time minus last offset as base_time")
    
    parser.add_argument("dat_file", nargs="?", help="Path to the .dat file to convert")
    parser.add_argument("xml_file", nargs="?", help="Path to the settings.xml file")
    
    args = parser.parse_args()

    timing_method = "tm" if args.tm else "tc"

    # ── RULE EVALUATION 1: Running with no parameters at all ──────────────────
    if not args.w and not args.dat_file and not args.xml_file:
        parser.print_help()
        sys.exit(0)

    # ── RULE EVALUATION 2: Watchdog Mode execution path ───────────────────────
    if args.w:
        if args.dat_file or args.xml_file:
            print("Error: Cannot specify explicit file parameters when executing in background daemon mode (-w).")
            parser.print_help()
            sys.exit(1)
            
        print(f"Starting watchdog | folder: {DEFAULT_LR_META_DIR} | timing: -{timing_method}")
        logging.info(f"Started watchdog. Monitoring: {DEFAULT_LR_META_DIR} | timing: -{timing_method}")

        
        try:
            event_handler = LRMetaDataHandler(
                output_dir=DEFAULT_EPIC_LOGS_DIR,
                settings_xml_path=DEFAULT_SETTINGS_XML,
                inactivity_period=INACTIVITY_PERIOD,
                timing_method=timing_method
            )
            observer = Observer()
            observer.schedule(event_handler, path=DEFAULT_LR_META_DIR, recursive=False)
            observer.start()

            # Fixed #3: Graceful shutdown framework listening loop for manual terminates
            while True:
                event_handler.check_and_process_files()
                time.sleep(5)
        except KeyboardInterrupt:
            print("\nStopping watchdog service gracefully...")
            logging.info("Watchdog shutting down via manual user stop signal.")
            observer.stop()
        except Exception as e:
            logging.error(f"Watchdog crashed: {e}")
            sys.exit(1)
        finally:
            observer.join()

    # ── RULE EVALUATION 3: Manual Conversion Mode execution path ──────────────
    else:
        if not args.dat_file or not args.xml_file:
            print("Error: Manual mode requires both [dat_file] and [xml_file] inputs specified.")
            parser.print_help()
            sys.exit(1)

        if not os.path.isfile(args.dat_file):
            print(f"Error: Target data file not found at path Location: '{args.dat_file}'")
            sys.exit(1)
        if not os.path.isfile(args.xml_file):
            print(f"Error: XML config schema file not found at path Location: '{args.xml_file}'")
            sys.exit(1)

        print(f"Converting: {args.dat_file}")
        print(f"Settings:   {args.xml_file}")
        print(f"Timing:     -{timing_method}")
        
        success = convert_lr_to_epic(
            file_path=args.dat_file,
            output_base_dir=DEFAULT_EPIC_LOGS_DIR,
            settings_xml_path=args.xml_file,
            timing_method=timing_method
        )
        if success:
            print("Done.")
        else:
            print("Conversion aborted or failed. Please check watchdog_debug.log for data warnings.")


if __name__ == "__main__":
    main()