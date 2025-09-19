"""
Media utilities module for calculating media file durations using FFmpeg.
"""

import os
import subprocess
import json
from pathlib import Path


class MediaDurationCalculator:
    """Calculates duration of media files using FFmpeg."""
    
    def __init__(self):
        self.ffprobe_cmd = self._find_ffprobe()
        
    def _find_ffprobe(self):
        """
        Find the ffprobe executable.
        
        Returns:
            str: Path to ffprobe executable or None if not found
        """
        # Common locations for ffprobe
        possible_paths = [
            'ffprobe',
            'ffprobe.exe',
            r'C:\ffmpeg\bin\ffprobe.exe',
            r'C:\Program Files\ffmpeg\bin\ffprobe.exe',
            '/usr/bin/ffprobe',
            '/usr/local/bin/ffprobe'
        ]
        
        for path in possible_paths:
            try:
                result = subprocess.run([path, '-version'], 
                                      capture_output=True, 
                                      text=True, 
                                      timeout=5)
                if result.returncode == 0:
                    return path
            except (subprocess.SubprocessError, FileNotFoundError):
                continue
                
        return None
    
    def get_duration(self, file_path):
        """
        Get the duration of a media file in seconds.
        
        Args:
            file_path (str): Path to the media file
            
        Returns:
            float: Duration in seconds, or 0 if unable to determine
        """
        if not self.ffprobe_cmd:
            print("Warning: FFprobe not found. Media durations will be 0.")
            return 0
            
        if not os.path.isfile(file_path):
            return 0
            
        try:
            cmd = [
                self.ffprobe_cmd,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                file_path
            ]
            
            # Use bytes mode to avoid encoding issues, then decode manually
            result = subprocess.run(cmd, 
                                  capture_output=True, 
                                  text=False,  # Use bytes mode
                                  timeout=30)
            
            if result.returncode != 0:
                return 0
            
            # Manually decode with error handling
            try:
                stdout_text = result.stdout.decode('utf-8', errors='ignore')
            except UnicodeDecodeError:
                try:
                    stdout_text = result.stdout.decode('cp1252', errors='ignore')
                except UnicodeDecodeError:
                    stdout_text = result.stdout.decode('latin1', errors='ignore')
            
            # Check if stdout is None or empty
            if not stdout_text or stdout_text.strip() == "":
                return 0
                
            data = json.loads(stdout_text)
            
            if 'format' in data and 'duration' in data['format']:
                return float(data['format']['duration'])
                
        except (subprocess.SubprocessError, json.JSONDecodeError, ValueError, KeyError, TypeError, UnicodeDecodeError):
            pass
            
        return 0
    
    def calculate_total_duration(self, file_paths):
        """
        Calculate total duration for a list of media files.
        
        Args:
            file_paths (list): List of file paths
            
        Returns:
            dict: Dictionary with individual durations and total
        """
        durations = {}
        total_duration = 0
        
        for file_path in file_paths:
            try:
                # Skip if file_path is None or invalid
                if not file_path or not isinstance(file_path, (str, os.PathLike)):
                    durations[file_path] = 0
                    continue
                
                # Check if file exists and is accessible
                if not os.path.exists(file_path) or not os.path.isfile(file_path):
                    durations[file_path] = 0
                    continue
                
                duration = self.get_duration(file_path)
                durations[file_path] = duration
                total_duration += duration
                
            except Exception as e:
                # Log the error but continue processing other files
                print(f"Warning: Error processing file {file_path}: {e}")
                durations[file_path] = 0
            
        return {
            'individual_durations': durations,
            'total_duration': total_duration,
            'total_files': len(file_paths)
        }
    
    @staticmethod
    def format_duration(seconds):
        """
        Format duration from seconds to human-readable format.
        
        Args:
            seconds (float): Duration in seconds
            
        Returns:
            str: Formatted duration (e.g., "1h 23m 45s")
        """
        if seconds <= 0:
            return "0s"
            
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if secs > 0 or not parts:
            parts.append(f"{secs}s")
            
        return " ".join(parts)
    
    def get_media_info(self, file_path):
        """
        Get detailed media information for a file.
        
        Args:
            file_path (str): Path to the media file
            
        Returns:
            dict: Media information including duration, format, etc.
        """
        if not self.ffprobe_cmd or not os.path.isfile(file_path):
            return {}
            
        try:
            cmd = [
                self.ffprobe_cmd,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                file_path
            ]
            
            # Use bytes mode to avoid encoding issues, then decode manually
            result = subprocess.run(cmd, 
                                  capture_output=True, 
                                  text=False,  # Use bytes mode
                                  timeout=30)
            
            if result.returncode != 0:
                return {}
            
            # Manually decode with error handling
            try:
                stdout_text = result.stdout.decode('utf-8', errors='ignore')
            except UnicodeDecodeError:
                try:
                    stdout_text = result.stdout.decode('cp1252', errors='ignore')
                except UnicodeDecodeError:
                    stdout_text = result.stdout.decode('latin1', errors='ignore')
            
            # Check if stdout is None or empty
            if not stdout_text or stdout_text.strip() == "":
                return {}
                
            data = json.loads(stdout_text)
            
            info = {
                'file_path': file_path,
                'file_size': os.path.getsize(file_path),
                'duration': 0,
                'format_name': '',
                'streams': []
            }
            
            if 'format' in data:
                format_info = data['format']
                info['duration'] = float(format_info.get('duration', 0))
                info['format_name'] = format_info.get('format_name', '')
                info['bit_rate'] = format_info.get('bit_rate', '')
                
            if 'streams' in data:
                for stream in data['streams']:
                    stream_info = {
                        'codec_type': stream.get('codec_type', ''),
                        'codec_name': stream.get('codec_name', ''),
                        'duration': float(stream.get('duration', 0))
                    }
                    
                    if stream_info['codec_type'] == 'video':
                        stream_info['width'] = stream.get('width', 0)
                        stream_info['height'] = stream.get('height', 0)
                        stream_info['fps'] = stream.get('r_frame_rate', '')
                        
                    elif stream_info['codec_type'] == 'audio':
                        stream_info['sample_rate'] = stream.get('sample_rate', '')
                        stream_info['channels'] = stream.get('channels', 0)
                        
                    info['streams'].append(stream_info)
                    
            return info
            
        except (subprocess.SubprocessError, json.JSONDecodeError, ValueError, TypeError, UnicodeDecodeError):
            return {}
            
    def check_ffmpeg_availability(self):
        """
        Check if FFmpeg/FFprobe is available and working.
        
        Returns:
            dict: Status information about FFmpeg availability
        """
        status = {
            'available': False,
            'path': None,
            'version': None,
            'error': None
        }
        
        if not self.ffprobe_cmd:
            status['error'] = "FFprobe not found in system PATH or common locations"
            return status
            
        try:
            result = subprocess.run([self.ffprobe_cmd, '-version'], 
                                  capture_output=True, 
                                  text=False,  # Use bytes mode
                                  timeout=5)
            
            if result.returncode == 0:
                status['available'] = True
                status['path'] = self.ffprobe_cmd
                
                # Manually decode output with error handling
                try:
                    stdout_text = result.stdout.decode('utf-8', errors='ignore')
                except UnicodeDecodeError:
                    try:
                        stdout_text = result.stdout.decode('cp1252', errors='ignore')
                    except UnicodeDecodeError:
                        stdout_text = result.stdout.decode('latin1', errors='ignore')
                
                # Extract version from output
                if stdout_text:
                    lines = stdout_text.split('\n')
                    if lines:
                        status['version'] = lines[0]
            else:
                status['error'] = f"FFprobe returned error code {result.returncode}"
                
        except (subprocess.SubprocessError, UnicodeDecodeError) as e:
            status['error'] = f"Error running FFprobe: {e}"
            
        return status