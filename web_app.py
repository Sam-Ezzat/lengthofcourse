"""
Flask web server for the Folder Explorer and Media Duration Calculator.
Provides a REST API and serves the frontend interface.
"""

import os
import json
import threading
import traceback
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime
import traceback

from folder_analyzer import FolderAnalyzer


app = Flask(__name__)
CORS(app)

# Global variables for analysis state
current_analysis = None
analysis_thread = None
analysis_progress = {
    'status': 'idle',  # idle, running, completed, error
    'message': '',
    'progress': 0,
    'results': None
}


class ProgressTracker:
    """Helper class to track analysis progress."""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        global analysis_progress
        analysis_progress.update({
            'status': 'idle',
            'message': '',
            'progress': 0,
            'results': None
        })
    
    def update(self, status, message, progress=None, results=None):
        global analysis_progress
        analysis_progress.update({
            'status': status,
            'message': message,
            'progress': progress if progress is not None else analysis_progress['progress'],
            'results': results
        })


progress_tracker = ProgressTracker()


def run_analysis_thread(folder_path, calculate_durations=True):
    """Run folder analysis in a separate thread."""
    global current_analysis
    
    try:
        progress_tracker.update('running', 'Initializing analysis...', 0)
        
        analyzer = FolderAnalyzer()
        current_analysis = analyzer
        
        # Custom analyzer with progress reporting
        progress_tracker.update('running', 'Scanning folder structure...', 10)
        
        # Scan folder for files
        file_paths = analyzer.scan_folder(folder_path)
        
        if not file_paths:
            progress_tracker.update('error', 'No files found or unable to access folder')
            return
        
        # Safety check for very large folders
        if len(file_paths) > 100000:
            progress_tracker.update('error', f'Folder contains too many files ({len(file_paths)}). Maximum supported: 100,000 files.')
            return
        
        progress_tracker.update('running', f'Found {len(file_paths)} files. Classifying...', 30)
        
        # Classify files by extension
        try:
            print(f"DEBUG: Starting classification of {len(file_paths)} files")
            classified_files = analyzer.classifier.classify_files(file_paths)
            print(f"DEBUG: Classification completed. Categories: {list(classified_files.keys())}")
            
            summary = analyzer.classifier.get_category_summary(classified_files)
            print(f"DEBUG: Summary generated successfully")
        except Exception as e:
            print(f"ERROR in classification: {e}")
            print(f"ERROR traceback: {traceback.format_exc()}")
            raise
        
        progress_tracker.update('running', 'Calculating file sizes...', 50)
        
        # Calculate total size with progress reporting
        total_size = 0
        total_files = len(file_paths)
        print(f"DEBUG: Starting size calculation for {total_files} files")
        
        for i, file_path in enumerate(file_paths):
            try:
                if file_path is None:
                    print(f"DEBUG: Warning - file_path at index {i} is None")
                    continue
                    
                if not isinstance(file_path, (str, os.PathLike)):
                    print(f"DEBUG: Warning - file_path at index {i} is not a string or path: {type(file_path)}")
                    continue
                
                if os.path.exists(file_path):
                    size = os.path.getsize(file_path)
                    total_size += size
                else:
                    print(f"DEBUG: Warning - file does not exist: {file_path}")
                
                # Update progress every 1000 files
                if i % 1000 == 0 and i > 0:
                    progress = 50 + int((i / total_files) * 10)  # 50-60% range
                    progress_tracker.update('running', f'Calculating sizes... {i}/{total_files}', progress)
                    
            except OSError as e:
                print(f"DEBUG: OSError for file {file_path}: {e}")
            except Exception as e:
                print(f"DEBUG: Unexpected error for file {file_path}: {e}")
                
        print(f"DEBUG: Size calculation completed. Total size: {total_size}")
        
        # Calculate media durations if requested
        media_durations = {}
        if calculate_durations:
            progress_tracker.update('running', 'Checking FFmpeg availability...', 60)
            
            # Check FFmpeg availability
            ffmpeg_status = analyzer.media_calculator.check_ffmpeg_availability()
            if not ffmpeg_status['available']:
                calculate_durations = False
                progress_tracker.update('running', 'FFmpeg not available. Skipping duration calculation...', 70)
            
            if calculate_durations:
                # Calculate video durations
                video_files = classified_files.get('video', [])
                if video_files:
                    try:
                        progress_tracker.update('running', f'Calculating durations for {len(video_files)} video files...', 75)
                        video_duration_data = analyzer.media_calculator.calculate_total_duration(video_files)
                        media_durations['video'] = video_duration_data
                    except Exception as e:
                        print(f"ERROR calculating video durations: {e}")
                        progress_tracker.update('running', 'Warning: Video duration calculation failed, continuing...', 75)
                
                # Calculate audio durations
                audio_files = classified_files.get('audio', [])
                if audio_files:
                    try:
                        progress_tracker.update('running', f'Calculating durations for {len(audio_files)} audio files...', 85)
                        audio_duration_data = analyzer.media_calculator.calculate_total_duration(audio_files)
                        media_durations['audio'] = audio_duration_data
                    except Exception as e:
                        print(f"ERROR calculating audio durations: {e}")
                        progress_tracker.update('running', 'Warning: Audio duration calculation failed, continuing...', 85)
        
        progress_tracker.update('running', 'Finalizing results...', 95)
        
        # Prepare results
        results = {
            'folder_path': str(folder_path),
            'scan_time': datetime.now().isoformat(),
            'total_files': len(file_paths),
            'classified_files': classified_files,
            'file_summary': summary,
            'media_durations': media_durations,
            'total_size': total_size,
            'ffmpeg_available': calculate_durations,
            'formatted_size': analyzer.format_size(total_size)
        }
        
        # Add formatted durations
        if media_durations:
            for media_type, duration_data in media_durations.items():
                duration_data['formatted_duration'] = analyzer.media_calculator.format_duration(
                    duration_data['total_duration']
                )
        
        progress_tracker.update('completed', 'Analysis completed successfully!', 100, results)
        
    except Exception as e:
        error_msg = f"Analysis failed: {str(e)}"
        print(f"Error in analysis thread: {traceback.format_exc()}")
        progress_tracker.update('error', error_msg)


@app.route('/')
def index():
    """Serve the main frontend page."""
    return render_template('index.html')


@app.route('/api/analyze', methods=['POST'])
def start_analysis():
    """Start folder analysis in background thread."""
    global analysis_thread
    
    try:
        data = request.get_json()
        print(f"DEBUG: Received request data: {data}")
        
        if not data or 'folder_path' not in data:
            return jsonify({'error': 'folder_path is required'}), 400
        
        folder_path = data['folder_path']
        calculate_durations = data.get('calculate_durations', True)
        
        print(f"DEBUG: Analyzing folder: {folder_path}")
        print(f"DEBUG: Calculate durations: {calculate_durations}")
        
        # Check if folder exists
        if not os.path.exists(folder_path):
            return jsonify({'error': 'Folder does not exist'}), 400
        
        if not os.path.isdir(folder_path):
            return jsonify({'error': 'Path is not a directory'}), 400
        
        # Check if analysis is already running
        if analysis_thread and analysis_thread.is_alive():
            return jsonify({'error': 'Analysis already in progress'}), 409
        
        # Reset progress and start new analysis
        progress_tracker.reset()
        analysis_thread = threading.Thread(
            target=run_analysis_thread,
            args=(folder_path, calculate_durations)
        )
        analysis_thread.start()
        
        return jsonify({'message': 'Analysis started successfully'})
        
    except Exception as e:
        print(f"ERROR in start_analysis: {e}")
        print(f"ERROR traceback: {traceback.format_exc()}")
        return jsonify({'error': f'Failed to start analysis: {str(e)}'}), 500
    analysis_thread.start()
    
    return jsonify({'message': 'Analysis started', 'status': 'running'})


@app.route('/api/progress', methods=['GET'])
def get_progress():
    """Get current analysis progress."""
    global analysis_progress
    return jsonify(analysis_progress)


@app.route('/api/cancel', methods=['POST'])
def cancel_analysis():
    """Cancel current analysis."""
    global analysis_thread, current_analysis
    
    if analysis_thread and analysis_thread.is_alive():
        # Note: Python threading doesn't support forced termination
        # This is more of a status reset
        progress_tracker.update('idle', 'Analysis cancelled by user')
        return jsonify({'message': 'Analysis cancellation requested'})
    
    return jsonify({'message': 'No analysis running'})


@app.route('/api/sample-folders', methods=['GET'])
def get_sample_folders():
    """Get list of sample folders for easy selection."""
    sample_folders = []
    
    # Add some common folders
    common_paths = [
        os.path.expanduser('~'),  # Home directory
        os.path.expanduser('~/Documents'),
        os.path.expanduser('~/Downloads'),
        os.path.expanduser('~/Desktop'),
        os.path.expanduser('~/Pictures'),
        os.path.expanduser('~/Videos'),
        os.path.expanduser('~/Music'),
        'C:\\' if os.name == 'nt' else '/',  # Root drive
    ]
    
    for path in common_paths:
        if os.path.exists(path) and os.path.isdir(path):
            try:
                # Get basic info about the folder
                file_count = len([f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))])
                sample_folders.append({
                    'path': path,
                    'name': os.path.basename(path) or path,
                    'file_count': file_count
                })
            except (PermissionError, OSError):
                # Skip folders we can't access
                continue
    
    return jsonify(sample_folders)


@app.route('/static/<path:filename>')
def static_files(filename):
    """Serve static files."""
    return send_from_directory('static', filename)


if __name__ == '__main__':
    # Create templates and static directories if they don't exist
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    
    print("Starting Folder Explorer Web Application...")
    print("Open your browser and go to: http://localhost:5000")
    
    app.run(debug=True, host='0.0.0.0', port=5000)