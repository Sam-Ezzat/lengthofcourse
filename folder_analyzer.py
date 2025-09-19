"""
Main folder analyzer application for scanning folders and calculating media durations.
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

from file_classifier import FileClassifier
from media_utils import MediaDurationCalculator


class FolderAnalyzer:
    """Main class for analyzing folder contents and media durations."""
    
    def __init__(self):
        self.classifier = FileClassifier()
        self.media_calculator = MediaDurationCalculator()
        
    def scan_folder(self, folder_path):
        """
        Recursively scan a folder and return all file paths.
        
        Args:
            folder_path (str): Path to the folder to scan
            
        Returns:
            list: List of all file paths found
        """
        file_paths = []
        
        try:
            folder_path = Path(folder_path).resolve()
            
            if not folder_path.exists():
                print(f"Error: Folder '{folder_path}' does not exist.")
                return []
                
            if not folder_path.is_dir():
                print(f"Error: '{folder_path}' is not a directory.")
                return []
                
            print(f"Scanning folder: {folder_path}")
            
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    file_path = Path(root) / file
                    file_paths.append(str(file_path))
                    
        except PermissionError as e:
            print(f"Permission error: {e}")
        except Exception as e:
            print(f"Error scanning folder: {e}")
            
        return file_paths
    
    def analyze_folder(self, folder_path, calculate_durations=True):
        """
        Analyze a folder's contents and generate a comprehensive report.
        
        Args:
            folder_path (str): Path to the folder to analyze
            calculate_durations (bool): Whether to calculate media durations
            
        Returns:
            dict: Analysis results
        """
        print(f"\n{'='*60}")
        print(f"FOLDER ANALYSIS STARTED")
        print(f"{'='*60}")
        
        # Scan folder for files
        file_paths = self.scan_folder(folder_path)
        
        if not file_paths:
            return {
                'folder_path': folder_path,
                'total_files': 0,
                'classified_files': {},
                'media_durations': {},
                'total_size': 0,
                'error': 'No files found or unable to access folder'
            }
        
        print(f"Found {len(file_paths)} files")
        
        # Classify files by extension
        print("Classifying files by type...")
        classified_files = self.classifier.classify_files(file_paths)
        summary = self.classifier.get_category_summary(classified_files)
        
        # Calculate total size
        total_size = 0
        for file_path in file_paths:
            try:
                total_size += os.path.getsize(file_path)
            except OSError:
                pass
        
        # Calculate media durations if requested
        media_durations = {}
        if calculate_durations:
            print("Calculating media durations...")
            
            # Check FFmpeg availability
            ffmpeg_status = self.media_calculator.check_ffmpeg_availability()
            if not ffmpeg_status['available']:
                print(f"Warning: {ffmpeg_status['error']}")
                print("Media durations will not be calculated.")
                calculate_durations = False
            
            if calculate_durations:
                # Calculate video durations
                video_files = classified_files.get('video', [])
                if video_files:
                    print(f"Calculating durations for {len(video_files)} video files...")
                    video_duration_data = self.media_calculator.calculate_total_duration(video_files)
                    media_durations['video'] = video_duration_data
                
                # Calculate audio durations
                audio_files = classified_files.get('audio', [])
                if audio_files:
                    print(f"Calculating durations for {len(audio_files)} audio files...")
                    audio_duration_data = self.media_calculator.calculate_total_duration(audio_files)
                    media_durations['audio'] = audio_duration_data
        
        return {
            'folder_path': str(Path(folder_path).resolve()),
            'scan_time': datetime.now().isoformat(),
            'total_files': len(file_paths),
            'classified_files': classified_files,
            'file_summary': summary,
            'media_durations': media_durations,
            'total_size': total_size,
            'ffmpeg_available': calculate_durations
        }
    
    def format_size(self, size_bytes):
        """
        Format file size in human-readable format.
        
        Args:
            size_bytes (int): Size in bytes
            
        Returns:
            str: Formatted size string
        """
        if size_bytes == 0:
            return "0 B"
            
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
            
        return f"{size_bytes:.1f} {size_names[i]}"
    
    def print_report(self, analysis_results):
        """
        Print a formatted analysis report.
        
        Args:
            analysis_results (dict): Results from analyze_folder()
        """
        results = analysis_results
        
        print(f"\n{'='*60}")
        print(f"FOLDER ANALYSIS RESULTS")
        print(f"{'='*60}")
        print(f"Folder: {results['folder_path']}")
        print(f"Scan Time: {results.get('scan_time', 'Unknown')}")
        print(f"Total Files: {results['total_files']}")
        print(f"Total Size: {self.format_size(results['total_size'])}")
        
        if 'error' in results:
            print(f"\nError: {results['error']}")
            return
        
        # File types summary
        print(f"\n{'File Types Found:'}")
        print(f"{'-'*40}")
        
        file_summary = results['file_summary']
        
        # Sort categories by count (descending)
        sorted_categories = sorted(file_summary.items(), 
                                 key=lambda x: x[1]['count'], 
                                 reverse=True)
        
        for category, info in sorted_categories:
            extensions_str = ", ".join(info['extensions']) if info['extensions'] else "no extensions"
            print(f"- {category.title()}: {info['count']} files ({extensions_str})")
        
        # Media durations
        if results['media_durations']:
            print(f"\n{'Media Duration:'}")
            print(f"{'-'*40}")
            
            for media_type, duration_data in results['media_durations'].items():
                total_duration = duration_data['total_duration']
                file_count = duration_data['total_files']
                formatted_duration = MediaDurationCalculator.format_duration(total_duration)
                
                print(f"- Total {media_type.title()} Duration: {formatted_duration} ({file_count} files)")
        
        elif not results.get('ffmpeg_available', False):
            print(f"\n{'Media Duration:'}")
            print(f"{'-'*40}")
            print("- Media durations not calculated (FFmpeg not available)")
        
        print(f"\n{'='*60}")
    
    def save_report(self, analysis_results, output_file):
        """
        Save analysis results to a file.
        
        Args:
            analysis_results (dict): Results from analyze_folder()
            output_file (str): Path to output file
        """
        try:
            import json
            
            # Create a JSON-serializable version of the results
            json_results = analysis_results.copy()
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(json_results, f, indent=2, ensure_ascii=False)
                
            print(f"\nAnalysis results saved to: {output_file}")
            
        except Exception as e:
            print(f"Error saving report: {e}")


def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(
        description="Analyze folder structure and calculate media durations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python folder_analyzer.py --path "C:\\Videos"
  python folder_analyzer.py --path "/home/user/media" --output report.json
  python folder_analyzer.py --path "." --no-duration
        """
    )
    
    parser.add_argument(
        '--path', '-p',
        required=True,
        help='Path to the folder to analyze'
    )
    
    parser.add_argument(
        '--output', '-o',
        help='Save results to a JSON file'
    )
    
    parser.add_argument(
        '--no-duration',
        action='store_true',
        help='Skip media duration calculation'
    )
    
    args = parser.parse_args()
    
    # Create analyzer instance
    analyzer = FolderAnalyzer()
    
    # Analyze the folder
    try:
        calculate_durations = not args.no_duration
        results = analyzer.analyze_folder(args.path, calculate_durations=calculate_durations)
        
        # Print the report
        analyzer.print_report(results)
        
        # Save to file if requested
        if args.output:
            analyzer.save_report(results, args.output)
            
    except KeyboardInterrupt:
        print("\n\nAnalysis interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()