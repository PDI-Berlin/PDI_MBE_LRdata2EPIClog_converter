import os
import time
import logging
import shutil
from datetime import datetime, timedelta
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logging.basicConfig(
    filename="watchdog_debug.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


def convert_lr_to_epic(file_path, output_base_dir):
    """
    Converts LR metadata from .dat format to EPIC log format and appends it to LR.txt
    inside the correct dated folder. Adds a header if the file doesn't exist yet.
    """


    try:
        base, _ = os.path.splitext(file_path)
        meta_dest = base + "_metadata.xml"
        if os.path.isfile(SETTINGS_XML_PATH):
            shutil.copy2(SETTINGS_XML_PATH, meta_dest)
            logging.info(f"Copied settings.xml to metadata file: {meta_dest}")
        else:
            logging.warning(
                f"settings.xml not found at {SETTINGS_XML_PATH}; "
                f"cannot create metadata snapshot for {file_path}"
            )
    except Exception as e:
        logging.error(f"Failed to copy settings.xml for {file_path}: {e}")




    try:
        base_time = datetime.fromtimestamp(os.path.getctime(file_path))

        with open(file_path, 'r') as f:
            lines = f.readlines()

        converted_lines = []
        for line in lines:
            parts = line.strip().split("\t")
            if len(parts) != 2:
                continue
            try:
                time_offset = float(parts[0])
                intensity = parts[1]

                new_time = base_time + timedelta(seconds=time_offset)
                formatted_time = new_time.strftime("%d/%m/%Y %H:%M:%S.%f")

                converted_line = f"{formatted_time},{intensity}\n"
                converted_lines.append(converted_line)

            except ValueError:
                logging.warning(f"Skipping invalid line: {line.strip()} in file {file_path}")

        now = datetime.now()
        year_str = now.strftime("%Y")
        date_str = now.strftime("%Y_%m_%d")
        dated_output_dir = os.path.join(output_base_dir, year_str, date_str)
        os.makedirs(dated_output_dir, exist_ok=True)

        output_file_path = os.path.join(dated_output_dir, "LR.txt")

        # Check
        file_exists = os.path.isfile(output_file_path)

        # Write
        with open(output_file_path, 'a') as f:
            if not file_exists:
                f.write("EPIC LR Log File\n\n")
                f.write("Date,LR\n")
            f.writelines(converted_lines)

        logging.info(f"Appended converted data to: {output_file_path}")

    except Exception as e:
        logging.error(f"Failed to convert file {file_path}: {e}")


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
        files_to_process = []

        for file_path, last_modified in list(self.file_timestamps.items()):
            logging.info(f"Checking file: {file_path}, last modified: {last_modified}")
            if current_time - last_modified > self.inactivity_period:
                files_to_process.append(file_path)

        for file_path in files_to_process:
            logging.info(f"Processing file: {file_path}")
            try:
                convert_lr_to_epic(file_path, self.output_dir)
                del self.file_timestamps[file_path]
            except Exception as e:
                logging.error(f"Error processing {file_path}: {e}")


if __name__ == "__main__":
    lr_meta_dir = r"d:\PDIRS"
    epic_logs_dir = r"c:\EPIC\Latest\Logs"
    SETTINGS_XML_PATH = r"F:\PDI Reflectance Monitor\settings.xml"
    inactivity_period = 20

    try:
        event_handler = LRMetaDataHandler(output_dir=epic_logs_dir, inactivity_period=inactivity_period)
        observer = Observer()
        observer.schedule(event_handler, path=lr_meta_dir, recursive=False)
        observer.start()

        logging.info("Started watchdog. Monitoring for new .dat files...")

        while True:
            event_handler.check_and_process_files()
            time.sleep(5)

    except Exception as e:
        logging.error(f"Watchdog crashed: {e}")
        time.sleep(5)


#  EXTRA CODE: settings.xml logic
import xml.etree.ElementTree as ET
import shutil

SETTINGS_XML_PATH = r"F:\PDI Reflectance Monitor\settings.xml"


def _parse_float_from_text(text, default="NA"):
    """
    Parse a float from scientific-notation string, return a clean string
    (integer if close to int, else compact float). On failure, return default.
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

    XML example:
      <settings>
        <settings.defaultPath>D:\PDIRS</settings.defaultPath>
        <settings.laserWavelength>6.400000000E+2</settings.laserWavelength>
        <settings.measurementAngle>6.000000000E+1</settings.measurementAngle>
        ...
      </settings>

    Returns: (wavelength_str, angle_str)
    """
    try:
        tree = ET.parse(SETTINGS_XML_PATH)
        root = tree.getroot()

        wl_text = root.findtext("./settings.laserWavelength")
        ang_text = root.findtext("./settings.measurementAngle")

        wl_str = _parse_float_from_text(wl_text)
        ang_str = _parse_float_from_text(ang_text)

        return wl_str, ang_str
    except Exception as e:
        logging.error(f"Failed to read settings.xml at {SETTINGS_XML_PATH}: {e}")
        return "NA", "NA"


_original_convert_lr_to_epic = convert_lr_to_epic


def convert_lr_to_epic(file_path, output_base_dir):
    """
    Wrapper around your original convert_lr_to_epic.

    - Calls the original function to generate/append LR.txt.
    - Copies settings.xml next to the .dat as FILENAME_metadata.xml.
    - If LR.txt is newly created for that date, enriches the header with
      LaserWavelength_nm and IncidenceAngle_deg from settings.xml.
    """

    try:
        now = datetime.now()
        year_str = now.strftime("%Y")
        date_str = now.strftime("%Y_%m_%d")
        dated_output_dir = os.path.join(output_base_dir, year_str, date_str)
        output_file_path = os.path.join(dated_output_dir, "LR.txt")
        file_exists_before = os.path.isfile(output_file_path)
    except Exception:
        output_file_path = None
        file_exists_before = False

    _original_convert_lr_to_epic(file_path, output_base_dir)

    try:
        base, _ = os.path.splitext(file_path)
        meta_dest = base + "_metadata.xml"
        if os.path.isfile(SETTINGS_XML_PATH):
            shutil.copy2(SETTINGS_XML_PATH, meta_dest)
            logging.info(f"Copied settings.xml to metadata file: {meta_dest}")
        else:
            logging.warning(
                f"settings.xml not found at {SETTINGS_XML_PATH}; "
                f"cannot create metadata snapshot for {file_path}"
            )
    except Exception as e:
        logging.error(f"Failed to copy settings.xml for {file_path}: {e}")

    try:
        if output_file_path is not None and (not file_exists_before) and os.path.isfile(output_file_path):
            wl, ang = _read_settings_values()

            with open(output_file_path, "r") as f:
                lines = f.readlines()

            header_index = None
            for i, line in enumerate(lines):
                if line.strip().startswith("Date,LR"):
                    header_index = i
                    break

            if header_index is not None:
                data_lines = lines[header_index + 1:]


                with open(output_file_path, "w") as f:
                    f.write("EPIC LR Log File\n\n")
                    f.write(f"LaserWavelength_nm: {wl}\n")
                    f.write(f"IncidenceAngle_deg: {ang}\n\n")
                    f.write("Date,LR\n")
                    f.writelines(data_lines)

                logging.info(
                    f"Updated LR.txt header with settings.xml data: "
                    f"wavelength={wl}, angle={ang}"
                )
            else:
                logging.warning(
                    f"Could not find 'Date,LR' header line in {output_file_path}; "
                    f"leaving file unchanged."
                )
    except Exception as e:
        logging.error(f"Failed to update LR.txt header for {output_file_path}: {e}")
