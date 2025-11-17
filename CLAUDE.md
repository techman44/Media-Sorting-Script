# CLAUDE.md - AI Assistant Guide for Media-Sorting-Script

## Project Overview

**Media-Sorting-Script** is a Python-based media file organization tool that processes RAW images, videos, and JPG files. It:
- Identifies file types and extracts metadata (camera make/model, creation date)
- Computes file hashes to detect duplicates
- Organizes files into structured directories based on file type, camera, and date
- Uses SQLite for tracking processed files and preventing duplicate processing
- Employs multi-threading for performance optimization

**Original Context**: This script was created with help from ChatGPT and is designed to organize large, disorganized media collections that may contain duplicates.

## Repository Structure

```
/home/user/Media-Sorting-Script/
├── mediasorting.py    # Main script (278 lines)
├── config.txt         # Configuration file (template)
├── README.md          # User documentation
├── files.db           # SQLite database (created at runtime)
└── .git/              # Git repository
```

### File Purposes

- **mediasorting.py**: Core application logic containing all processing functions
- **config.txt**: Configuration template defining file formats, input/output directories, and operation modes
- **README.md**: End-user documentation with installation and usage instructions
- **files.db**: SQLite database created at runtime to track file processing state

## Architecture

### Design Patterns

1. **Configuration-Driven**: All parameters loaded from `config.txt` using ConfigParser
2. **Multi-threaded Processing**: ThreadPoolExecutor with 8 workers for parallel file processing
3. **Database-Backed Deduplication**: SQLite tracks file hashes to prevent duplicate processing
4. **Metadata Extraction**: External `exiftool` for reading EXIF and media metadata
5. **Structured Logging**: RotatingFileHandler with console and file output

### Execution Flow

1. Load configuration from `config.txt`
2. Setup logging infrastructure
3. Initialize SQLite database with files table and hash index
4. If `operation_scan=yes`: Scan input directories and process files
5. If `operation_run=yes`: Process unprocessed files from database
6. Each file: extract metadata → compute hash → check duplicates → move to destination

## Key Components

### Core Functions (mediasorting.py)

| Function | Lines | Purpose |
|----------|-------|---------|
| `load_config(file_path)` | 32-52 | Parse config.txt and initialize settings dictionary |
| `setup_logging(log_file_path)` | 55-68 | Configure rotating file and console loggers |
| `get_hash(file_path)` | 79-96 | Compute xxhash64 file hash (files >100 bytes) |
| `get_metadata(file_path, *tags)` | 98-113 | Extract EXIF metadata using exiftool subprocess |
| `determine_file_format(file_extension, settings)` | 116-121 | Classify file as raw/video/jpg format |
| `process_file(settings, file_path)` | 124-184 | Main processing logic: metadata → hash → DB check → move |
| `get_destination_folder(...)` | 187-201 | Calculate target directory: `{type}/{make}/{model}/{year}/{month}` |
| `move_file(source, destination)` | 204-229 | Move file with sanitization and error handling |
| `process_files(settings)` | 232-247 | Scan input directories and submit files to thread pool |
| `run_operation(settings)` | 250-264 | Process unprocessed files from database |
| `sanitize_directory_name(name)` | 71-73 | Replace non-alphanumeric chars with hyphens |
| `sanitize_file_name(name)` | 75-77 | Replace disallowed chars with underscores |

### Database Schema

**Table: files**
```sql
CREATE TABLE files (
    file_path TEXT,
    file_name TEXT,
    file_extension TEXT,
    file_size INTEGER,
    file_hash TEXT,
    file_format TEXT,
    camera_make TEXT,
    camera_model TEXT,
    created_date TEXT,
    input_directory TEXT,
    output_directory TEXT,
    processed_tag TEXT,      -- 'Processed' or 'Not processed'
    duplicate_tag TEXT       -- 'Original', 'Duplicate'
)
CREATE INDEX idx_hash ON files (file_hash)
```

## Dependencies

### Python Packages (Required)
- **Standard Library**: os, hashlib, sqlite3, json, subprocess, logging, collections, configparser, sys, shutil, datetime, time, threading, re
- **External Packages**:
  - `xxhash` - Fast hashing algorithm
  - `python-dateutil` - Date parsing utilities
  - `concurrent.futures` - Thread pool (backport for Python 2, standard in Python 3)

### System Dependencies
- **exiftool** - External binary for metadata extraction (must be in PATH)
- **Python 3** - Required runtime

### Installation Commands
```bash
pip install xxhash python-dateutil
# Install exiftool following official guide for your OS
```

## Configuration Guide

### config.txt Format

```ini
[settings]
raw_formats = nef, cr2, arw, dng
video_formats = mp4, mov, avi, mkv
jpg_formats = jpg, jpeg, png
input_dirs = /path/to/source1, /path/to/source2
raw_formats_output_dir = /path/to/raw_output
video_formats_output_dir = /path/to/video_output
jpg_formats_output_dir = /path/to/jpg_output
duplicate_dir = /path/to/duplicates
log_dir = /path/to/logs
error_dir = /path/to/errors
operation_scan = yes
operation_run = no
```

### Configuration Keys

- **File Formats**: Comma-separated extensions (lowercase)
- **Directories**: Absolute or relative paths, comma-separated for input_dirs
- **Operations**:
  - `operation_scan=yes` - Walk input directories and process new files
  - `operation_run=yes` - Process files marked 'Not processed' in database

### Important Notes
- **log_dir must exist** or script will throw error on startup
- Output directories are created automatically
- File extensions are case-insensitive (converted to lowercase)

## Development Workflows

### Adding Support for New File Formats

1. Edit `config.txt` and add extension to appropriate format list
2. No code changes needed - configuration-driven design

### Modifying Destination Path Structure

Current structure: `{output_dir}/{camera_make}/{camera_model}/{year}/{month}/`

To modify, edit `get_destination_folder()` at line 187-201:
```python
def get_destination_folder(settings, file_format, camera_make, camera_model, created_date, duplicate=False):
    year = created_date.split(':')[0]
    month = datetime.strptime(created_date, "%Y:%m:%d %H:%M:%S").strftime("%B")
    # Modify path structure here
```

### Adding New Metadata Fields

1. Update metadata extraction in `process_file()` at lines 132-141
2. Add new fallback tags to `get_metadata()` call
3. Update database schema creation at line 235-238
4. Update INSERT statements at lines 160-165 and 175-180

### Customizing Hash Algorithm

Currently uses xxhash64 (fast, non-cryptographic). To change:

Edit `get_hash()` at line 79-96:
```python
hasher = xxhash.xxh64()  # Replace with hashlib.sha256() etc.
```

## Coding Conventions

### Style Guidelines
- **Indentation**: 4 spaces
- **Naming**: snake_case for functions and variables
- **Line Length**: Generally <120 characters
- **String Quotes**: Single quotes preferred
- **Logging**: Use logging module, not print (except debug prints at line 205-206)

### Error Handling
- **File Operations**: Try-except with logging.error()
- **Metadata Failures**: Return None, use default values
- **Small Files**: Skip if <100 bytes with warning
- **Missing Files**: Log error and return False from move_file()

### Concurrency
- **Thread Pool**: 8 workers (hardcoded at lines 242, 257)
- **Database Connections**: One connection per thread in process_file()
- **Hash Set Lock**: threading.Lock() in settings for thread-safe hash tracking

### Database Practices
- **Context Manager**: Use `with sqlite3.connect()` for automatic commit/rollback
- **Indexes**: Create index on file_hash for duplicate lookup performance
- **Atomic Operations**: Single INSERT per file processing

## Common AI Assistant Tasks

### 1. Bug Fixes

**Check these areas first**:
- Thread safety: Database connections, shared state
- Path handling: Windows vs. Unix separators
- Metadata parsing: Null/missing values
- Date parsing: Multiple format support

**Example bugs to watch for**:
- Race conditions in database writes
- Missing directory creation before file moves
- Uncaught exceptions in thread pool workers

### 2. Feature Additions

**Common requests**:
- Add dry-run mode (don't move files, just log)
- Support for additional metadata tags
- CSV export of database contents
- Progress bars or status reporting
- Configurable thread pool size

**Implementation checklist**:
- [ ] Update config.txt with new parameters
- [ ] Update load_config() to read new settings
- [ ] Update README.md with documentation
- [ ] Test with sample files

### 3. Performance Optimization

**Current bottlenecks**:
- exiftool subprocess calls (dominant factor)
- File I/O for hash computation
- SQLite writes (one per file)

**Optimization strategies**:
- Batch exiftool calls (process multiple files per invocation)
- Use exiftool JSON streaming mode
- Batch database inserts with executemany()
- Adjust thread pool size based on I/O vs CPU workload

### 4. Refactoring

**Improvement opportunities**:
- Extract database operations into separate class
- Move configuration to dataclass or Pydantic model
- Separate CLI interface from core logic
- Add type hints (currently none)
- Add unit tests (currently none)

### 5. Testing Strategy

**Manual testing approach** (no automated tests exist):
1. Create test directory with small sample files
2. Use operation_scan=yes with test input
3. Verify database entries with `sqlite3 files.db "SELECT * FROM files"`
4. Check file organization in output directories
5. Re-run with operation_run=yes to test idempotency

## Important Considerations

### Data Safety

**WARNING**: This script moves files (destructive operation)
- **Always backup** before running on real data
- **Test with samples** first
- **Check log files** in log_dir for errors
- Files are moved, not copied (original location cleared)

### Edge Cases

1. **Duplicate file names**: Sanitized but may collide, current implementation overwrites
2. **Missing metadata**: Falls back to 'NoCamera', 'NoModel', file system timestamps
3. **Corrupted files**: May fail hash or metadata extraction, check error logs
4. **Very large files**: Entire file read into memory for hashing (potential issue)
5. **Network drives**: File moves across filesystems may be slow or fail

### Metadata Extraction Notes

**exiftool fallback chain** (process_file:132-141):
- Camera Make: Make → DeviceManufacturer → Composer → Encoder → ... → 'NoCamera'
- Camera Model: Model → DeviceModelName → ... → 'NoModel'
- Created Date: DateTimeOriginal → CreateDate → FileCreateDate → ... → mtime

**Date format assumption**: "%Y:%m:%d %H:%M:%S" (EXIF standard)

### Database Considerations

- **No migration system**: Schema changes require manual ALTER TABLE or recreation
- **No vacuum**: Database may grow with deleted records
- **Single file**: files.db in working directory, not configurable
- **No authentication**: SQLite file accessible to all with file access

## Quick Reference Commands

### Running the Script
```bash
python3 mediasorting.py
```

### Database Queries
```bash
# View all processed files
sqlite3 files.db "SELECT * FROM files"

# Count duplicates
sqlite3 files.db "SELECT COUNT(*) FROM files WHERE duplicate_tag='Duplicate'"

# View unique cameras
sqlite3 files.db "SELECT DISTINCT camera_make, camera_model FROM files"

# Check processing status
sqlite3 files.db "SELECT processed_tag, COUNT(*) FROM files GROUP BY processed_tag"
```

### Debugging
```bash
# Check exiftool availability
which exiftool

# Test metadata extraction manually
exiftool -j sample_file.jpg

# Monitor log file
tail -f /path/to/logs/file_processing.log
```

## Git Workflow

### Current Branch
Branch: `claude/claude-md-mi2p1jqew1rakvqy-01RUThj7uGAEZmWyd7ubhXpo`

### Commit Guidelines
- Use descriptive commit messages
- Reference issue numbers if applicable
- Test before committing
- Keep commits focused on single changes

### Recent History
```
c181046 Update README.md
a03ba34 Create config.txt
78b69ef Create mediasorting.py
e5cd66d Update README.md
f9ce5a5 Initial commit
```

## AI Assistant Guidelines

### When Making Changes

1. **Read before writing**: Always read files before editing
2. **Preserve functionality**: Don't break existing features
3. **Match style**: Follow existing conventions
4. **Update documentation**: Modify README.md if user-facing changes
5. **Test configuration**: Verify config.txt remains valid
6. **Consider threading**: Check for race conditions in multi-threaded code

### Security Considerations

**Potential vulnerabilities**:
- **Path Traversal**: File paths from user input (config.txt) - validate paths
- **Command Injection**: exiftool called with file paths - currently safe (no shell=True)
- **SQL Injection**: Currently safe (uses parameterized queries)
- **File Overwrites**: sanitize_file_name() prevents some issues but collisions possible

### When Uncertain

- **Check logs**: Refer to file_processing.log for runtime behavior
- **Consult README.md**: User-facing documentation for expected behavior
- **Review git history**: Understand recent changes and rationale
- **Test incrementally**: Make small changes and verify before proceeding

## Useful Patterns

### Adding a new configuration option
```python
# 1. Add to config.txt
[settings]
new_option = value

# 2. Load in load_config()
settings['new_option'] = config.get('settings', 'new_option')

# 3. Update README.md
# 4. Use in code via settings['new_option']
```

### Adding database fields
```python
# 1. Update schema (line 235-238)
c.execute('''CREATE TABLE IF NOT EXISTS files
             (..., new_field text)''')

# 2. Update INSERT statements (lines 160, 175)
c.execute("INSERT INTO files (..., new_field) VALUES (?,?,?,?,...,?)",
          (..., new_value))
```

### Extending metadata extraction
```python
# Add to process_file() metadata section
new_metadata = get_metadata(file_path, 'Tag1', 'Tag2', 'FallbackTag') or 'DefaultValue'
```

---

**Last Updated**: 2025-11-17
**Repository**: techman44/Media-Sorting-Script
**Python Version**: 3.x
**Status**: Active development
