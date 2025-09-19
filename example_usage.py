"""
Example script demonstrating how to use the FolderAnalyzer programmatically.
"""

from folder_analyzer import FolderAnalyzer


def example_usage():
    """Demonstrate different ways to use the FolderAnalyzer."""
    
    # Create an analyzer instance
    analyzer = FolderAnalyzer()
    
    # Example 1: Analyze current directory without duration calculation
    print("Example 1: Quick analysis without media durations")
    print("-" * 50)
    
    results = analyzer.analyze_folder(".", calculate_durations=False)
    analyzer.print_report(results)
    
    # Example 2: Check individual file classification
    print("\n\nExample 2: Individual file classification")
    print("-" * 50)
    
    test_files = [
        "example.mp4",
        "document.pdf", 
        "music.mp3",
        "photo.jpg",
        "script.py"
    ]
    
    for file_path in test_files:
        category = analyzer.classifier.get_category(file_path)
        print(f"{file_path} -> {category}")
    
    # Example 3: Format duration examples
    print("\n\nExample 3: Duration formatting examples")
    print("-" * 50)
    
    durations = [45, 125, 3661, 7323, 0]
    for seconds in durations:
        formatted = analyzer.media_calculator.format_duration(seconds)
        print(f"{seconds} seconds -> {formatted}")
    
    # Example 4: Check FFmpeg availability
    print("\n\nExample 4: FFmpeg availability check")
    print("-" * 50)
    
    ffmpeg_status = analyzer.media_calculator.check_ffmpeg_availability()
    print(f"FFmpeg available: {ffmpeg_status['available']}")
    if ffmpeg_status['available']:
        print(f"Path: {ffmpeg_status['path']}")
        print(f"Version: {ffmpeg_status['version']}")
    else:
        print(f"Error: {ffmpeg_status['error']}")


if __name__ == "__main__":
    example_usage()