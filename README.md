# Summary

This script was created with the help from chatgpt. 

This script is designed for processing media files such as RAW images, videos, and jpg formats from specified directories. It identifies the type of each file, reads its metadata (including camera make/model and created date), computes the hash of each file, and checks for duplicates in the SQLite database. It then moves each file to the appropriate output directory based on file type, camera make/model, and the creation date. If the file is identified as a duplicate, it's moved to a separate directory.

The script uses a configuration file (`config.txt`) to set up parameters including the file formats it processes and the input and output directories.


Info

This script is particularly useful for organizing large collections of photos and videos that are disorganized and have possible duplicates. It has been optimized for performance and can handle large volumes of files.

It is recommended that you test the script with a small sample of your media files before running it on your entire collection. Be aware that the script moves files, which is a destructive operation. Ensure that you have backups of your media files before running this script.


The primary functionalities of this script include:

    Loading configurations from a file and setting up the logging process.
    Determining the file format for each file.
    Fetching metadata for each file.
    Processing each file, including checking for duplicates and moving files to the corresponding directory.
    Running the operation based on the config settings.

It uses the SQLite3 database to keep track of files and their associated details, such as file path, name, extension, size, hash, format, camera make and model, creation date, input directory, output directory, processed tag, and duplicate tag
# Usage Instructions

## Installation
The script uses python3. Make sure you have python3 installed on your system.

## Configuration
To run the script, you'll need to create a configuration file named `config.txt` in the same directory as the script. The configuration file should follow the below format:

```txt
[settings]
raw_formats = file_extension1, file_extension2, ...
video_formats = file_extension1, file_extension2, ...
jpg_formats = file_extension1, file_extension2, ...
input_dirs = dir1, dir2, ...
raw_formats_output_dir = output_dir_for_raw_formats
video_formats_output_dir = output_dir_for_video_formats
jpg_formats_output_dir = output_dir_for_jpg_formats
duplicate_dir = dir_for_duplicates
log_dir = dir_for_logs
error_dir = dir_for_error_files
operation_scan = yes/no
operation_run = yes/no
```
`operation_scan` and `operation_run` are for specifying whether to process files in the `input_dirs` and to run operations on unprocessed files in the database, respectively. Set them to 'yes' or 'no' as per your requirement.

    raw_formats: list of raw file formats to be processed, separated by commas
    video_formats: list of video file formats to be processed, separated by commas
    jpg_formats: list of jpg file formats to be processed, separated by commas
    input_dirs: list of directories to process, separated by commas
    raw_formats_output_dir: directory to move raw files to
    video_formats_output_dir: directory to move video files to
    jpg_formats_output_dir: directory to move jpg files to
    duplicate_dir: directory to move duplicate files to
    log_dir: directory to output logs to
    operation_scan: set to 'yes' if the script should scan directories, 'no' otherwise
    operation_run: set to 'yes' if the script should process files, 'no' otherwise

## Running the Script
To run the script, navigate to the directory containing the script and execute the command:

```bash
python3 mediasorting.py
```

The script logs its operation and any errors encountered in a log file located in the specified `log_dir`. (the direcroty needs to exist or it will throw an error.)

# Information

The script utilizes the following python libraries:

- os
- hashlib
- sqlite3
- json
- subprocess
- logging
- collections
- configparser
- sys
- shutil
- datetime
- dateutil.parser
- time
- concurrent.futures
- xxhash
- threading
- re

It also uses a separate tool, `exiftool`, for reading metadata from files.

Please make sure all these dependencies are installed on your system. You can install Python packages using `pip install package-name` and `exiftool` can be installed following its official guide.

The script is designed to work with a multi-threaded setup to improve the performance of file processing. It works by submitting jobs to a thread pool executor that allows processing of multiple files in parallel.
