#!/usr/bin/env python3
"""
Example script demonstrating how to use the YouTube Shorts automation
with custom configuration options.
"""

from youtube_shorts_automation import YouTubeShortsAutomation

def main():
    # Custom configuration
    custom_config = {
        'output_dir': 'custom_output',
        'temp_dir': 'custom_temp',
        'video_length': 45,  # Longer video (45 seconds)
        'resolution': (1080, 1920),  # Standard 9:16 aspect ratio
        'openai_model': 'gpt-4',  # Using GPT-4 for higher quality scripts
        'youtube_category_id': '22',  # People & Blogs category
        'max_retries': 5,  # More retries
        'retry_delay': 10,  # Longer delay between retries
    }
    
    # Initialize with custom configuration
    automation = YouTubeShortsAutomation(config=custom_config)
    
    # Option 1: Run the complete pipeline
    video_id = automation.run_pipeline()
    
    if video_id:
        print(f"Success! Video uploaded: https://www.youtube.com/watch?v={video_id}")
    else:
        print("Pipeline failed. Check logs for details.")
    
    # Option 2: Run individual steps (uncomment to use)
    """
    # Get trending topics
    topics = automation.get_trending_topics(count=10)
    print(f"Trending topics: {topics}")
    
    # Generate a script for a specific topic
    custom_topic = "Artificial Intelligence"
    script = automation.generate_script(custom_topic)
    print(f"Generated script: {script}")
    
    # Create video without uploading
    success = automation.create_video(script, custom_topic)
    if success:
        print(f"Video created at: {automation.video_path}")
    """


if __name__ == "__main__":
    main()