import os
import hashlib
import sqlite3
import json
import subprocess
import logging
from collections import defaultdict
from configparser import ConfigParser
from logging.handlers import RotatingFileHandler
from logging import handlers
import sys
import shutil
from datetime import datetime
from dateutil.parser import parse
import time
from concurrent.futures import ThreadPoolExecutor
import xxhash
import threading
import configparser
import re

config = configparser.ConfigParser()
config.read('config.txt')

raw_formats = config.get('settings', 'raw_formats').split(', ')
video_formats = config.get('settings', 'video_formats').split(', ')
jpg_formats = config.get('settings', 'jpg_formats').split(', ')

all_formats = raw_formats + video_formats + jpg_formats


def load_config(file_path):
    config = ConfigParser()
    config.read(file_path)
    settings = defaultdict(list)
    settings['raw_formats'] = config.get('settings', 'raw_formats').split(', ')
    settings['video_formats'] = config.get('settings', 'video_formats').split(', ')
    settings['jpg_formats'] = config.get('settings', 'jpg_formats').split(', ')
    settings['input_dirs'] = config.get('settings', 'input_dirs').split(', ')
    settings['raw_formats_output_dir'] = config.get('settings', 'raw_formats_output_dir')
    settings['video_formats_output_dir'] = config.get('settings', 'video_formats_output_dir')
    settings['jpg_formats_output_dir'] = config.get('settings', 'jpg_formats_output_dir')
    settings['duplicate_dir'] = config.get('settings', 'duplicate_dir')
    settings['log_dir'] = config.get('settings', 'log_dir')
    settings['error_dir'] = config.get('settings', 'error_dir')
    settings['operation_scan'] = config.get('settings', 'operation_scan')
    settings['operation_run'] = config.get('settings', 'operation_run')
    settings['all_formats'] = settings['raw_formats'] + settings['video_formats'] + settings['jpg_formats']
    settings['file_hashes'] = set()
    settings['hashes_lock'] = threading.Lock()

    return settings


def setup_logging(log_file_path):
    log = logging.getLogger('')
    log.setLevel(logging.DEBUG)
    format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(format)
    log.addHandler(ch)

    fh = handlers.RotatingFileHandler(log_file_path, maxBytes=(1048576*5), backupCount=7)
    fh.setFormatter(format)
    log.addHandler(fh)

    return log


def sanitize_directory_name(name):
    # Replace any characters that are not alphanumeric or underscores with a hyphen
    return re.sub(r'\W+', '-', name)

def sanitize_file_name(name):
    # Replace any characters that are not alphanumeric, underscores, or hyphens with an underscore
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', name)

def get_hash(file_path):
    """Compute the hash of the given file."""
    file_size_threshold = 100  # Set a threshold size in bytes (adjust as needed)

    file_size = os.path.getsize(file_path)
    if file_size < file_size_threshold:
        logging.warning(f"File is too small: {file_path}. File size: {file_size} bytes.")
        return None
    hasher = xxhash.xxh64()
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
            hasher.update(data)
    except Exception as e:
        logging.error(f"Error reading file: {file_path}. Error: {str(e)}")
        return None

    return hasher.hexdigest()

def get_metadata(file_path, *tags):
    try:
        result = subprocess.run(['exiftool', '-j', file_path], stdout=subprocess.PIPE)
        try:
            metadata = json.loads(result.stdout)[0]
        except json.JSONDecodeError:
            logging.error(f"Could not decode metadata for file: {file_path}")
            return None
        for tag in tags:
            value = metadata.get(tag)
            if value is not None:
                return value
        return None
    except Exception as e:
        logging.error(f"Error getting metadata for file: {file_path}. Error: {str(e)}")
        return None


def determine_file_format(file_extension, settings):
    file_extension = file_extension.lower()
    for format_type, extensions in settings.items():
        if file_extension in extensions:
            return format_type
    return 'unknown'


def process_file(settings, file_path):
    file_extension = file_path.split('.')[-1].lower()
    if file_extension not in settings['all_formats']:
        logging.info(f"Skipped unsupported file: {file_path}. File extension: {file_extension}")
        return
    file_size = os.path.getsize(file_path)
    file_hash = get_hash(file_path)
    file_format = determine_file_format(file_extension, settings)
    camera_make = get_metadata(file_path, 'Make', 'DeviceManufacturer', 'Composer', 'Encoder',
                               'AppleProappsImageTIFFMake', 'HandlerVendorID', 'HandlerDescription',
                               'NoMake') or 'NoCamera'
    camera_model = get_metadata(file_path, 'Model', 'DeviceModelName', 'AppleProappsImageTIFFModel',
                                'HandlerVendorID', 'NoModel') or 'NoModel'
    created_date = get_metadata(file_path, 'DateTimeOriginal', 'CreateDate', 'FileCreateDate',
                                'MediaCreateDate', 'QuickTime:CreateDate',
                                'QuickTime:FileCreateDate')
    if created_date is None:
        created_date = str(datetime.fromtimestamp(os.path.getmtime(file_path)))

    if file_format != 'unknown':
        logging.info(f"Processing file: {file_path}, File format: {file_format}, Camera make: {camera_make}, "
                     f"Camera model: {camera_model}, Created date: {created_date}")

        # Adding a transaction to ensure atomicity of database operations
        with sqlite3.connect('files.db') as conn:
            c = conn.cursor()

            # Check if the file is a duplicate
            c.execute("SELECT * FROM files WHERE file_hash=?", (file_hash,))
            data = c.fetchall()

            if len(data) == 0:
                destination_folder = get_destination_folder(settings, file_format, camera_make, camera_model, created_date)
                move_file(file_path, destination_folder)

                # Inserting the new row in a single database operation
                c.execute("INSERT INTO files (file_path, file_name, file_extension, file_size, file_hash, file_format, "
                          "camera_make, camera_model, created_date, input_directory, output_directory, processed_tag, duplicate_tag) "
                          "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (file_path, os.path.basename(file_path), file_extension,
                                                              file_size, file_hash, file_format, camera_make,
                                                              camera_model, created_date, os.path.dirname(file_path), destination_folder,
                                                              'Processed', 'Original'))
                conn.commit()
            else:
                logging.info(f"File is a duplicate: {file_path}, File format: {file_format}, Camera make: {camera_make}, "
                             f"Camera model: {camera_model}, Created date: {created_date}")
                destination_folder = get_destination_folder(settings, file_format, camera_make, camera_model, created_date,
                                                           duplicate=True)
                move_file(file_path, destination_folder)

                # Inserting the new row in a single database operation
                c.execute("INSERT INTO files (file_path, file_name, file_extension, file_size, file_hash, file_format, "
                          "camera_make, camera_model, created_date, input_directory, output_directory, processed_tag, duplicate_tag) "
                          "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (file_path, os.path.basename(file_path), file_extension,
                                                              file_size, file_hash, file_format, camera_make,
                                                              camera_model, created_date, os.path.dirname(file_path), destination_folder,
                                                              'Processed', 'Duplicate'))
                conn.commit()

    else:
        logging.info(f"Skipped unsupported file: {file_path}. Identified format: {file_extension}")


def get_destination_folder(settings, file_format, camera_make, camera_model, created_date, duplicate=False):
    year = created_date.split(':')[0]
    month = datetime.strptime(created_date, "%Y:%m:%d %H:%M:%S").strftime("%B")
    camera_make = sanitize_directory_name(camera_make) if camera_make != '' else 'NoMake'
    camera_model = sanitize_directory_name(camera_model) if camera_model != '' else 'NoModel'

    if duplicate:
        return os.path.join(settings['duplicate_dir'], camera_make, camera_model, year, month)
    else:
        if file_format == 'raw_formats':
            return os.path.join(settings['raw_formats_output_dir'], camera_make, camera_model, year, month)
        elif file_format == 'video_formats':
            return os.path.join(settings['video_formats_output_dir'], camera_make, camera_model, year, month)
        elif file_format == 'jpg_formats':
            return os.path.join(settings['jpg_formats_output_dir'], camera_make, camera_model, year, month)


def move_file(source, destination):
    print("Source:", source)
    print("Destination:", destination)
    if not os.path.exists(source):
        logging.error(f"File does not exist: {source}")
        return False

    try:
        if not os.path.exists(destination):
            os.makedirs(destination)

        # Get the file name without the extension
        file_name, file_extension = os.path.splitext(os.path.basename(source))

        # Ensure the file name is valid by replacing disallowed characters with underscore (_)
        file_name = sanitize_file_name(file_name)

        # Append the file extension back to the sanitized file name
        destination_file = os.path.join(destination, file_name + file_extension)

        shutil.move(source, destination_file)
        logging.info(f"Successfully moved file: {source} to destination: {destination_file}")
        return True
    except Exception as e:
        logging.error(f"Error moving file: {source}. Error: {str(e)}")
        return False


def process_files(settings):
    conn = sqlite3.connect('files.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS files
                (file_path text, file_name text, file_extension text, file_size integer, file_hash text, file_format text, 
                camera_make text, camera_model text, created_date text, input_directory text, output_directory text, 
                processed_tag text, duplicate_tag text)''')
    c.execute("CREATE INDEX IF NOT EXISTS idx_hash ON files (file_hash)")
    conn.close()

    with ThreadPoolExecutor(max_workers=8) as executor:
        for directory in settings['input_dirs']:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    file_path = os.path.join(root, file)
                    executor.submit(process_file, settings, file_path)


def run_operation(settings):
    conn = sqlite3.connect('files.db')
    c = conn.cursor()
    c.execute("SELECT * FROM files WHERE processed_tag='Not processed' ORDER BY file_format, camera_make, camera_model, created_date")
    rows = c.fetchall()
    conn.close()

    with ThreadPoolExecutor(max_workers=8) as executor:
        for row in rows:
            file_path, file_name, file_extension, file_size, file_hash, file_format, camera_make, camera_model, created_date, input_directory, output_directory, processed_tag, duplicate_tag = row

            if duplicate_tag != 'Duplicate':
                executor.submit(process_file, settings, file_path)
            else:
                executor.submit(process_file, settings, file_path)


if __name__ == "__main__":
    settings = load_config('config.txt')
    log_file_path = os.path.join(settings['log_dir'], 'file_processing.log')
    log = setup_logging(log_file_path)
    logging.info("Script started")

    if settings['operation_scan'] == 'yes':
        process_files(settings)

    if settings['operation_run'] == 'yes':
        run_operation(settings)
