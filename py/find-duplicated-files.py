#!/usr/bin/env python3
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
    PROGRESS_INTERVAL = 100  # Log progress every N files
    
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
            with open(file_path, 'rb') as f:
                while chunk := f.read(self.CHUNK_SIZE):
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
        self.logger.info(f"Scanning {len(folders)} folder(s) for files larger than {self.min_size_kb} KB...")
        for folder in folders:
            self._scan_folder(folder)
        self.logger.info(f"Scan complete. Processed {self.file_count} files.")
    
    def _scan_folder(self, folder: str) -> None:
        """
        Scan a single folder for files.
        
        Args:
            folder: Path to folder
        """
        folder_path = Path(folder)
        if not folder_path.exists():
            self.logger.warning(f"Folder '{folder}' does not exist")
            return
        
        if not folder_path.is_dir():
            self.logger.warning(f"'{folder}' is not a directory")
            return
        
        self.logger.info(f"Scanning folder: {folder}")
        
        # Walk through all files in the folder
        for root, dirs, files in os.walk(folder_path):
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
            self.logger.info(f"  Processed {self.file_count} files...")
        
        # Get file extension
        _, ext = os.path.splitext(file_path)
        
        # Calculate hash
        file_hash = self.get_file_hash(file_path)
        if file_hash is None:
            return
        
        # Create unique key: extension + hash
        key = (ext, file_hash)
        size_kb = file_size // 1024
        
        self.file_info[size_kb][key].append(os.path.abspath(file_path))
    
    def get_duplicates(self) -> dict:
        """
        Get only groups with 2 or more files.
        
        Returns:
            dict: {file_size_kb: [[file_paths]]} sorted by size descending
        """
        self.logger.info("Analyzing files for duplicates...")
        duplicates = {}
        duplicate_count = 0
        
        for size_kb in sorted(self.file_info.keys(), reverse=True):
            size_groups = self.file_info[size_kb]
            groups = [paths for paths in size_groups.values() if len(paths) >= 2]
            
            if groups:
                duplicates[size_kb] = groups
                duplicate_count += sum(len(g) for g in groups)
        
        self.logger.info(f"Found {duplicate_count} duplicate files.")
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
                print(f"{size_kb} KB:")
                for path in sorted(paths):
                    print(path)


def main():
    """Main entry point."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H%M%S',
        stream=sys.stderr
    )
    logger = logging.getLogger(__name__)
    
    parser = argparse.ArgumentParser(
        description='Find duplicate files in given folders.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s -d /home/user/photos /home/user/backup -m 100
  %(prog)s --directories . --min-size 1024
        '''
    )
    
    parser.add_argument(
        '-d',
        '--directories',
        nargs='+',
        required=True,
        help='folders to search for duplicate files'
    )
    
    parser.add_argument(
        '--min-size', 
        '-m',
        type=int,
        required=True,
        help='minimum file size in KB'
    )
    
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


if __name__ == '__main__':
    main()
