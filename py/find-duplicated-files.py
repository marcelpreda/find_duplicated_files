#!/usr/bin/env python3
# pylint: disable=C0103
"""
Find duplicated files in given directories.

Duplicates are identified by:
- Same file extension
- Identical byte content

Only files larger than min_size (in KB) are considered.
Output is sorted by file size (largest first).
"""

import argparse
import hashlib
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path


class FileDuplicateFinder:
    """Find duplicate files in given directories."""

    CHUNK_SIZE = 65536
    PROGRESS_INTERVAL = 1000  # Log progress every N files

    def __init__(self, min_size_kb: int = 1, logger: logging.Logger = None):
        """
        Initialize the duplicate file finder.

        Args:
            min_size_kb: Minimum file size in KB
            logger: Logger instance for progress reporting
        """
        self.min_size_kb = min_size_kb
        self.min_size_bytes = min_size_kb * 1024
        self.file_info = defaultdict(lambda: defaultdict(list))
        self.file_count = 0
        self.logger = logger or logging.getLogger(__name__)

    def _format_size(self, size_kb: int) -> str:
        """
        Format file size in human-readable format.

        Args:
            size_kb: Size in kilobytes

        Returns:
            Human-readable size string (e.g., "2.5 MB", "1.2 GB")
        """
        if size_kb < 1024:
            return f"{size_kb} KB"
        if size_kb < 1024 * 1024:
            return f"{size_kb / 1024:.1f} MB"
        return f"{size_kb / (1024 * 1024):.1f} GB"

    def get_file_hash(self, file_path: str) -> str:
        """
        Calculate SHA256 hash of file content.

        Args:
            file_path: Path to the file

        Returns:
            Hex digest of SHA256 hash or None if error
        """
        hash_obj = hashlib.sha256()
        try:
            with open(file_path, "rb") as f_read:
                while chunk := f_read.read(self.CHUNK_SIZE):
                    hash_obj.update(chunk)
            return hash_obj.hexdigest()
        except (IOError, OSError):
            return None

    def scan_folders(self, folders: list) -> None:
        """
        Scan folders for files.

        Args:
            folders: List of folder paths to scan
        """
        self.logger.info(
            "Scanning %d folder(s) for files larger than %d KB...", len(folders), self.min_size_kb
        )
        for folder in folders:
            self._scan_folder(folder)
        self.logger.info("Scan complete. Processed %d files.", self.file_count)

        # Calculate hashes only for files with duplicate size+extension combinations
        self._calculate_hashes_for_duplicates()

    def _scan_folder(self, folder: str) -> None:
        """
        Scan a single folder for files.

        Args:
            folder: Path to folder
        """
        folder_path = Path(folder)
        if not folder_path.exists():
            self.logger.warning("Folder '%s' does not exist", folder)
            return

        if not folder_path.is_dir():
            self.logger.warning("'%s' is not a directory", folder)
            return

        self.logger.info("Scanning folder: %s", folder)

        # Walk through all files in the folder
        for root, _dummy, files in os.walk(folder_path):
            for file_name in files:
                self._process_file(os.path.join(root, file_name))

    def _process_file(self, file_path: str) -> None:
        """
        Process a single file.

        Args:
            file_path: Path to the file
        """
        try:
            file_size = os.path.getsize(file_path)
        except (IOError, OSError):
            return

        # Skip files smaller than min_size
        if file_size < self.min_size_bytes:
            return

        self.file_count += 1

        # Log progress every N files
        if self.file_count % self.PROGRESS_INTERVAL == 0:
            self.logger.info("  Processed %d files...", self.file_count)

        # Get file extension
        _, ext = os.path.splitext(file_path)

        # Group files by exact byte size and extension (hash calculation deferred)
        self.file_info[file_size][ext].append(os.path.abspath(file_path))

    def _calculate_hashes_for_duplicates(self) -> None:
        """
        Calculate hashes only for files with duplicate size+extension combinations.
        Reorganizes file_info from [file_size][ext] to [file_size][(ext, hash)].
        """
        self.logger.info("Calculating hashes for potential duplicates...")
        hashed_info = defaultdict(lambda: defaultdict(list))
        hash_count = 0

        for file_size, ext_groups in self.file_info.items():
            for ext, file_paths in ext_groups.items():
                # Skip if only one file for this size+extension combination
                if len(file_paths) < 2:
                    continue

                # Calculate hashes only for files with potential duplicates
                for file_path in file_paths:
                    file_hash = self.get_file_hash(file_path)
                    if file_hash is None:
                        continue

                    hash_count += 1

                    # Log progress every N files
                    if hash_count % self.PROGRESS_INTERVAL == 0:
                        self.logger.info("  Hashed %d files...", hash_count)

                    key = (ext, file_hash)
                    hashed_info[file_size][key].append(file_path)

        # Replace the file_info with hashed version
        self.file_info = hashed_info
        self.logger.info("Completed hashing %d potential duplicate files.", hash_count)

    def get_duplicates(self) -> dict:
        """
        Get only groups with 2 or more files.

        Returns:
            dict: {file_size_kb: [[file_paths]]} sorted by size descending
        """
        self.logger.info("Analyzing files for duplicates...")
        duplicates = {}
        duplicate_count = 0

        for file_size in sorted(self.file_info.keys(), reverse=True):
            size_groups = self.file_info[file_size]
            groups = [paths for paths in size_groups.values() if len(paths) >= 2]

            if groups:
                size_kb = file_size // 1024
                duplicates[size_kb] = groups
                duplicate_count += sum(len(g) for g in groups)

        self.logger.info("Found %d duplicate files.", duplicate_count)
        return duplicates

    def print_duplicates(self, duplicates: dict) -> None:
        """
        Print duplicates in the specified format.

        Args:
            duplicates: Dictionary of duplicate files grouped by size
        """
        for size_kb in sorted(duplicates.keys(), reverse=True):
            groups = duplicates[size_kb]

            for paths in groups:
                formatted_size = self._format_size(size_kb)
                print(f"{formatted_size}:")
                for path in sorted(paths):
                    print(path)


def main():
    """Main entry point."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H%M%S",
        stream=sys.stderr,
    )
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(
        description="Find duplicate files in given folders.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -d /home/user/photos /home/user/backup -m 100
  %(prog)s --directories . --min-size 1024
        """,
    )

    parser.add_argument(
        "-d",
        "--directories",
        nargs="+",
        required=True,
        help="folders to search for duplicate files",
    )

    parser.add_argument("--min-size", "-m", type=int, required=True, help="minimum file size in KB")

    args = parser.parse_args()

    if args.min_size < 1:
        logger.error("min-size must be at least 1 KB")
        sys.exit(1)

    # Create finder and scan files
    finder = FileDuplicateFinder(min_size_kb=args.min_size, logger=logger)
    finder.scan_folders(args.directories)

    # Get and print duplicates
    duplicates = finder.get_duplicates()

    if duplicates:
        finder.print_duplicates(duplicates)
    else:
        logger.info("No duplicate files found.")

    logger.info("Finished.")


if __name__ == "__main__":
    main()
