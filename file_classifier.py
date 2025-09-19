"""
File classifier module for categorizing files by extension type.
"""

import os
from collections import defaultdict
from pathlib import Path


class FileClassifier:
    """Classifies files by their extension types."""
    
    def __init__(self):
        # Define file extension categories
        self.categories = {
            'video': {
                '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', 
                '.m4v', '.3gp', '.mpg', '.mpeg', '.m2v', '.mxf'
            },
            'audio': {
                '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a',
                '.aiff', '.au', '.ra', '.3ga', '.amr', '.awb'
            },
            'documents': {
                '.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt', '.pages',
                '.xls', '.xlsx', '.ppt', '.pptx', '.odp', '.ods'
            },
            'images': {
                '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif',
                '.svg', '.webp', '.ico', '.psd', '.raw', '.cr2', '.nef'
            },
            'archives': {
                '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.Z'
            },
            'code': {
                '.py', '.js', '.html', '.css', '.java', '.cpp', '.c', '.h',
                '.php', '.rb', '.go', '.rs', '.swift', '.kt', '.ts', '.jsx',
                '.tsx', '.vue', '.sql', '.xml', '.json', '.yaml', '.yml'
            }
        }
        
    def get_category(self, file_path):
        """
        Get the category of a file based on its extension.
        
        Args:
            file_path (str): Path to the file
            
        Returns:
            str: Category name ('video', 'audio', 'documents', etc.) or 'others'
        """
        extension = Path(file_path).suffix.lower()
        
        for category, extensions in self.categories.items():
            if extension in extensions:
                return category
                
        return 'others'
    
    def classify_files(self, file_paths):
        """
        Classify a list of file paths into categories.
        
        Args:
            file_paths (list): List of file paths
            
        Returns:
            dict: Dictionary with categories as keys and lists of files as values
        """
        classified = defaultdict(list)
        
        for file_path in file_paths:
            if os.path.isfile(file_path):
                category = self.get_category(file_path)
                classified[category].append(file_path)
                
        return dict(classified)
    
    def get_extensions_by_category(self, category):
        """
        Get all extensions for a specific category.
        
        Args:
            category (str): Category name
            
        Returns:
            set: Set of extensions for the category
        """
        return self.categories.get(category, set())
    
    def get_category_summary(self, classified_files):
        """
        Generate a summary of classified files.
        
        Args:
            classified_files (dict): Dictionary from classify_files()
            
        Returns:
            dict: Summary with counts and unique extensions per category
        """
        summary = {}
        
        for category, files in classified_files.items():
            extensions = set()
            for file_path in files:
                ext = Path(file_path).suffix.lower()
                if ext:
                    extensions.add(ext)
            
            summary[category] = {
                'count': len(files),
                'extensions': sorted(list(extensions)),
                'files': files
            }
            
        return summary