"""
Optimized folder analyzer with enhanced performance for large file collections.
Uses concurrent processing, streaming, and caching for better efficiency.
"""

import os
import sys
import argparse
import asyncio
import aiofiles
import hashlib
import pickle
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from threading import Lock
import multiprocessing
import time

from file_classifier import FileClassifier
from media_utils import MediaDurationCalculator


class OptimizedFolderAnalyzer:
    """High-performance folder analyzer with concurrent processing."""
    
    def __init__(self, max_workers=None, use_cache=True, batch_size=1000):
        self.classifier = FileClassifier()
        self.media_calculator = MediaDurationCalculator()
        
        # Performance settings
        self.max_workers = max_workers or min(32, (os.cpu_count() or 1) + 4)
        self.use_cache = use_cache
        self.batch_size = batch_size
        
        # Cache settings
        self.cache_dir = Path(".folder_analyzer_cache")
        if use_cache:
            self.cache_dir.mkdir(exist_ok=True)
        
        # Thread safety
        self._lock = Lock()
        self._progress_callback = None
        
    def set_progress_callback(self, callback):
        """Set callback function for progress updates."""
        self._progress_callback = callback
        
    def _update_progress(self, message, progress=None):
        """Thread-safe progress update."""
        if self._progress_callback:
            self._progress_callback(message, progress)
    
    def _get_cache_key(self, folder_path):
        """Generate cache key for folder."""
        folder_str = str(Path(folder_path).resolve())
        return hashlib.md5(folder_str.encode()).hexdigest()
    
    def _load_cache(self, cache_key):
        """Load cached results if available and valid."""
        if not self.use_cache:
            return None
            
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        if not cache_file.exists():
            return None
            
        try:
            with open(cache_file, 'rb') as f:
                cached_data = pickle.load(f)
                
            # Check if cache is still valid (within 1 hour)
            cache_time = cached_data.get('timestamp', 0)
            if time.time() - cache_time > 3600:  # 1 hour
                return None
                
            return cached_data
            
        except Exception:
            return None
    
    def _save_cache(self, cache_key, data):
        """Save results to cache."""
        if not self.use_cache:
            return
            
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        try:
            data['timestamp'] = time.time()
            with open(cache_file, 'wb') as f:
                pickle.dump(data, f)
        except Exception:
            pass
    
    def scan_folder_streaming(self, folder_path, max_files=1000000):
        """
        Stream file paths instead of loading all into memory.
        Generator function for memory efficiency.
        """
        count = 0
        try:
            folder_path = Path(folder_path).resolve()
            
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    if count >= max_files:
                        self._update_progress(f"Reached maximum file limit ({max_files})")
                        return
                        
                    file_path = Path(root) / file
                    yield str(file_path)
                    count += 1
                    
                    if count % 10000 == 0:
                        self._update_progress(f"Scanning... found {count} files")
                        
        except PermissionError as e:
            print(f"Permission error: {e}")
        except Exception as e:
            print(f"Error scanning folder: {e}")
    
    def classify_files_batch(self, file_paths_batch):
        """Classify a batch of files efficiently."""
        classified = {}
        
        for file_path in file_paths_batch:
            if not os.path.isfile(file_path):
                continue
                
            category = self.classifier.get_category(file_path)
            if category not in classified:
                classified[category] = []
            classified[category].append(file_path)
            
        return classified
    
    def calculate_sizes_concurrent(self, file_paths, progress_start=50, progress_range=20):
        """Calculate file sizes using concurrent processing."""
        total_size = 0
        processed_count = 0
        total_files = len(file_paths)
        
        def get_file_size(file_path):
            try:
                if os.path.exists(file_path):
                    return os.path.getsize(file_path)
                return 0
            except (OSError, Exception):
                return 0
        
        # Process in batches with concurrent execution
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit files in chunks
            for i in range(0, total_files, self.batch_size):
                batch = file_paths[i:i + self.batch_size]
                
                # Submit batch to executor
                future_to_path = {executor.submit(get_file_size, path): path for path in batch}
                
                # Collect results
                for future in as_completed(future_to_path):
                    size = future.result()
                    total_size += size
                    processed_count += 1
                    
                    # Update progress
                    if processed_count % 1000 == 0:
                        progress = progress_start + int((processed_count / total_files) * progress_range)
                        self._update_progress(f"Calculating sizes... {processed_count}/{total_files}", progress)
        
        return total_size
    
    def calculate_media_durations_parallel(self, media_files_by_type, progress_start=70, progress_range=25):
        """Calculate media durations using parallel processing."""
        media_durations = {}
        
        def calculate_duration_batch(file_paths):
            """Calculate durations for a batch of files."""
            results = {}
            for file_path in file_paths:
                duration = self.media_calculator.get_duration(file_path)
                results[file_path] = duration
            return results
        
        for media_type, files in media_files_by_type.items():
            if not files:
                continue
                
            self._update_progress(f"Calculating {media_type} durations...", progress_start)
            
            all_durations = {}
            total_duration = 0
            
            # Process files in parallel batches
            num_processes = min(self.max_workers, len(files))
            batch_size = max(1, len(files) // num_processes)
            
            with ProcessPoolExecutor(max_workers=num_processes) as executor:
                # Create batches
                batches = [files[i:i + batch_size] for i in range(0, len(files), batch_size)]
                
                # Submit batches
                future_to_batch = {executor.submit(self._calculate_duration_batch_worker, batch): batch for batch in batches}
                
                # Collect results
                for future in as_completed(future_to_batch):
                    batch_results = future.result()
                    all_durations.update(batch_results)
                    
                    # Update total
                    for duration in batch_results.values():
                        total_duration += duration
            
            media_durations[media_type] = {
                'individual_durations': all_durations,
                'total_duration': total_duration,
                'total_files': len(files),
                'formatted_duration': self.media_calculator.format_duration(total_duration)
            }
        
        return media_durations
    
    @staticmethod
    def _calculate_duration_batch_worker(file_paths):
        """Worker function for parallel duration calculation."""
        calculator = MediaDurationCalculator()
        results = {}
        
        for file_path in file_paths:
            try:
                duration = calculator.get_duration(file_path)
                results[file_path] = duration
            except Exception:
                results[file_path] = 0
                
        return results
    
    def analyze_folder_optimized(self, folder_path, calculate_durations=True, max_files=1000000):
        """
        Optimized folder analysis with streaming, caching, and parallel processing.
        """
        start_time = time.time()
        
        self._update_progress("Starting optimized analysis...", 0)
        
        # Check cache first
        cache_key = self._get_cache_key(folder_path)
        cached_data = self._load_cache(cache_key)
        
        if cached_data and not calculate_durations:
            self._update_progress("Using cached results...", 100)
            return cached_data['results']
        
        self._update_progress("Scanning folder (streaming mode)...", 5)
        
        # Stream files instead of loading all into memory
        file_paths = list(self.scan_folder_streaming(folder_path, max_files))
        
        if not file_paths:
            return self._create_empty_results(folder_path, "No files found")
        
        if len(file_paths) >= max_files:
            return self._create_empty_results(folder_path, f"Too many files (>{max_files})")
        
        self._update_progress(f"Processing {len(file_paths)} files...", 10)
        
        # Classify files in batches
        self._update_progress("Classifying files...", 20)
        classified_files = {}
        
        for i in range(0, len(file_paths), self.batch_size):
            batch = file_paths[i:i + self.batch_size]
            batch_classified = self.classify_files_batch(batch)
            
            # Merge results
            for category, files in batch_classified.items():
                if category not in classified_files:
                    classified_files[category] = []
                classified_files[category].extend(files)
            
            progress = 20 + int((i / len(file_paths)) * 20)
            self._update_progress(f"Classifying... {i}/{len(file_paths)}", progress)
        
        # Generate summary
        summary = self.classifier.get_category_summary(classified_files)
        
        # Calculate sizes concurrently
        self._update_progress("Calculating file sizes (concurrent)...", 40)
        total_size = self.calculate_sizes_concurrent(file_paths, 40, 20)
        
        # Calculate media durations if requested
        media_durations = {}
        if calculate_durations:
            self._update_progress("Checking FFmpeg availability...", 60)
            ffmpeg_status = self.media_calculator.check_ffmpeg_availability()
            
            if ffmpeg_status['available']:
                media_files = {
                    'video': classified_files.get('video', []),
                    'audio': classified_files.get('audio', [])
                }
                
                # Filter out empty categories
                media_files = {k: v for k, v in media_files.items() if v}
                
                if media_files:
                    self._update_progress("Calculating media durations (parallel)...", 65)
                    media_durations = self.calculate_media_durations_parallel(media_files, 65, 30)
            else:
                self._update_progress("FFmpeg not available, skipping durations...", 70)
        
        # Prepare results
        self._update_progress("Finalizing results...", 95)
        
        results = {
            'folder_path': str(Path(folder_path).resolve()),
            'scan_time': datetime.now().isoformat(),
            'total_files': len(file_paths),
            'classified_files': classified_files,
            'file_summary': summary,
            'media_durations': media_durations,
            'total_size': total_size,
            'ffmpeg_available': calculate_durations and media_durations,
            'formatted_size': self.format_size(total_size),
            'processing_time': time.time() - start_time,
            'optimization_used': True
        }
        
        # Cache results
        self._save_cache(cache_key, {'results': results})
        
        self._update_progress("Analysis completed!", 100)
        return results
    
    def _create_empty_results(self, folder_path, error_message):
        """Create empty results structure with error."""
        return {
            'folder_path': folder_path,
            'total_files': 0,
            'classified_files': {},
            'media_durations': {},
            'total_size': 0,
            'error': error_message,
            'optimization_used': True
        }
    
    def format_size(self, size_bytes):
        """Format file size in human-readable format."""
        if size_bytes == 0:
            return "0 B"
            
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
            
        return f"{size_bytes:.1f} {size_names[i]}"
    
    def get_performance_stats(self):
        """Get performance statistics and recommendations."""
        return {
            'max_workers': self.max_workers,
            'cpu_count': os.cpu_count(),
            'batch_size': self.batch_size,
            'cache_enabled': self.use_cache,
            'recommended_max_files': min(1000000, self.max_workers * 50000),
            'algorithms': {
                'file_scanning': 'os.walk() streaming generator',
                'classification': 'Batch processing with dictionary lookup',
                'size_calculation': 'Concurrent ThreadPoolExecutor',
                'media_durations': 'Parallel ProcessPoolExecutor',
                'caching': 'Pickle-based with timestamp validation'
            }
        }


def main():
    """Main entry point with optimized analyzer."""
    parser = argparse.ArgumentParser(
        description="Optimized folder analyzer with concurrent processing",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--path', '-p', required=True, help='Folder path to analyze')
    parser.add_argument('--output', '-o', help='Save results to JSON file')
    parser.add_argument('--no-duration', action='store_true', help='Skip media duration calculation')
    parser.add_argument('--workers', '-w', type=int, help='Number of worker threads/processes')
    parser.add_argument('--batch-size', '-b', type=int, default=1000, help='Batch size for processing')
    parser.add_argument('--no-cache', action='store_true', help='Disable caching')
    parser.add_argument('--max-files', type=int, default=1000000, help='Maximum files to process')
    parser.add_argument('--stats', action='store_true', help='Show performance statistics')
    
    args = parser.parse_args()
    
    # Create optimized analyzer
    analyzer = OptimizedFolderAnalyzer(
        max_workers=args.workers,
        use_cache=not args.no_cache,
        batch_size=args.batch_size
    )
    
    # Set up progress callback
    def progress_callback(message, progress=None):
        if progress is not None:
            print(f"[{progress:3d}%] {message}")
        else:
            print(f"[ - ] {message}")
    
    analyzer.set_progress_callback(progress_callback)
    
    # Show performance stats if requested
    if args.stats:
        stats = analyzer.get_performance_stats()
        print("\nPerformance Configuration:")
        print(f"- CPU cores: {stats['cpu_count']}")
        print(f"- Worker threads/processes: {stats['max_workers']}")
        print(f"- Batch size: {stats['batch_size']}")
        print(f"- Caching: {'Enabled' if stats['cache_enabled'] else 'Disabled'}")
        print(f"- Recommended max files: {stats['recommended_max_files']:,}")
        print()
    
    try:
        # Run analysis
        calculate_durations = not args.no_duration
        results = analyzer.analyze_folder_optimized(
            args.path, 
            calculate_durations=calculate_durations,
            max_files=args.max_files
        )
        
        # Print results
        from folder_analyzer import FolderAnalyzer  # For print_report method
        regular_analyzer = FolderAnalyzer()
        regular_analyzer.print_report(results)
        
        # Show performance info
        if 'processing_time' in results:
            print(f"\nProcessing time: {results['processing_time']:.2f} seconds")
        
        # Save to file if requested
        if args.output:
            regular_analyzer.save_report(results, args.output)
            
    except KeyboardInterrupt:
        print("\nAnalysis interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()