#!/usr/bin/env python3
"""
YouTube Shorts Automation

This script automates the end-to-end process of creating and uploading YouTube Shorts:
1. Topic selection/generation
2. Script/narration generation
3. Video asset creation
4. Video assembly
5. YouTube upload
6. Scheduling (when run via cron or other scheduler)

Requirements:
- Google API credentials with YouTube Data API v3 access
- OpenAI API key for script generation
- FFmpeg installed for video processing
"""

import os
import random
import time
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# For topic selection
from pytrends.request import TrendReq
import requests

# For script generation
import openai

# For text-to-speech
from gtts import gTTS

# For video processing
import moviepy.editor as mp
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, AudioFileClip
import subprocess

# For YouTube upload
import google.oauth2.credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("youtube_shorts_automation.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class YouTubeShortsAutomation:
    """Main class for YouTube Shorts automation pipeline."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the automation pipeline.
        
        Args:
            config: Configuration dictionary with optional overrides
        """
        self.config = {
            'output_dir': 'output',
            'temp_dir': 'temp',
            'video_length': 30,  # seconds
            'resolution': (1080, 1920),  # width, height (9:16 aspect ratio)
            'openai_model': 'gpt-3.5-turbo',
            'youtube_category_id': '27',  # Education
            'max_retries': 3,
            'retry_delay': 5,  # seconds
        }
        
        if config:
            self.config.update(config)
            
        # Create necessary directories
        os.makedirs(self.config['output_dir'], exist_ok=True)
        os.makedirs(self.config['temp_dir'], exist_ok=True)
        
        # Initialize API clients
        self._init_openai()
        
        # Set paths for the current run
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_id = f"short_{timestamp}"
        self.audio_path = os.path.join(self.config['temp_dir'], f"{self.run_id}_audio.mp3")
        self.video_path = os.path.join(self.config['output_dir'], f"{self.run_id}.mp4")
    
    def _init_openai(self):
        """Initialize OpenAI API client."""
        openai_api_key = os.getenv('OPENAI_API_KEY')
        if not openai_api_key:
            logger.warning("OpenAI API key not found. Script generation will not work.")
        else:
            openai.api_key = openai_api_key
    
    def _init_youtube_client(self):
        """Initialize YouTube API client."""
        # Check for credentials
        client_secrets_file = os.getenv('YOUTUBE_CLIENT_SECRETS_FILE')
        service_account_file = os.getenv('YOUTUBE_SERVICE_ACCOUNT_FILE')
        
        if service_account_file and os.path.exists(service_account_file):
            # Use service account
            credentials = Credentials.from_service_account_file(
                service_account_file,
                scopes=['https://www.googleapis.com/auth/youtube.upload']
            )
            return build('youtube', 'v3', credentials=credentials)
        
        elif client_secrets_file and os.path.exists(client_secrets_file):
            # Use OAuth2
            flow = InstalledAppFlow.from_client_secrets_file(
                client_secrets_file,
                scopes=['https://www.googleapis.com/auth/youtube.upload']
            )
            credentials = flow.run_local_server(port=8080)
            return build('youtube', 'v3', credentials=credentials)
        
        else:
            logger.error("No YouTube API credentials found.")
            raise ValueError("YouTube API credentials are required for upload.")
    
    def get_trending_topics(self, count: int = 5) -> List[str]:
        """
        Get trending topics from Google Trends.
        
        Args:
            count: Number of trending topics to return
            
        Returns:
            List of trending topic strings
        """
        try:
            logger.info("Fetching trending topics from Google Trends")
            pytrends = TrendReq()
            trending_searches = pytrends.trending_searches(pn='united_states')
            topics = trending_searches[0].tolist()[:count]
            logger.info(f"Found trending topics: {topics}")
            return topics
        except Exception as e:
            logger.error(f"Error fetching trending topics: {e}")
            # Fallback to default topics
            return ["Technology Tips", "Life Hacks", "Science Facts", "History Moments", "Health Tips"]
    
    def generate_script(self, topic: str) -> str:
        """
        Generate a script for the given topic using OpenAI GPT.
        
        Args:
            topic: The topic to generate a script for
            
        Returns:
            Generated script text
        """
        if not openai.api_key:
            logger.warning("OpenAI API key not set, using placeholder script")
            return f"Here's a quick tip about {topic}. Did you know that learning about {topic} can improve your life? Stay tuned for more interesting facts!"
        
        try:
            logger.info(f"Generating script for topic: {topic}")
            response = openai.ChatCompletion.create(
                model=self.config['openai_model'],
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that writes engaging, informative scripts for YouTube Shorts."},
                    {"role": "user", "content": f"Write a 30-second, punchy script about {topic}, aimed at a general audience. The script should be engaging, informative, and end with a call to action. Keep it under 100 words."}
                ]
            )
            script = response.choices[0].message.content.strip()
            logger.info(f"Generated script: {script[:50]}...")
            return script
        except Exception as e:
            logger.error(f"Error generating script: {e}")
            return f"Here's a quick tip about {topic}. Did you know that learning about {topic} can improve your life? Stay tuned for more interesting facts!"
    
    def text_to_speech(self, text: str, output_path: str) -> bool:
        """
        Convert text to speech and save as audio file.
        
        Args:
            text: Text to convert to speech
            output_path: Path to save the audio file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("Converting text to speech")
            tts = gTTS(text=text, lang='en', slow=False)
            tts.save(output_path)
            logger.info(f"Saved audio to {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error in text-to-speech conversion: {e}")
            return False
    
    def create_video(self, script: str, topic: str) -> bool:
        """
        Create a video with the given script and topic.
        
        Args:
            script: The narration script
            topic: The topic of the video
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Creating video for topic: {topic}")
            
            # 1. Generate audio from script
            if not self.text_to_speech(script, self.audio_path):
                return False
            
            # 2. Create a solid color background (as a placeholder for real footage)
            width, height = self.config['resolution']
            color_clip = mp.ColorClip(size=(width, height), color=(0, 0, 0), duration=self.config['video_length'])
            
            # 3. Add title text
            title_text = TextClip(
                f"{topic.upper()}", 
                fontsize=70, 
                color='white', 
                font='Arial-Bold',
                size=(width-100, None)
            )
            title_text = title_text.set_position(('center', 200)).set_duration(5)
            
            # 4. Add script text as subtitles (simplified - in real implementation, would split by sentences)
            words = script.split()
            subtitle_clips = []
            
            # Create subtitle clips (simplified approach)
            words_per_clip = 5
            for i in range(0, len(words), words_per_clip):
                subtitle_text = " ".join(words[i:i+words_per_clip])
                subtitle = TextClip(
                    subtitle_text, 
                    fontsize=40, 
                    color='white',
                    font='Arial',
                    size=(width-100, None)
                )
                start_time = i/words_per_clip * 5  # Approximate timing
                subtitle = subtitle.set_position(('center', 'center')).set_start(start_time).set_duration(5)
                subtitle_clips.append(subtitle)
            
            # 5. Add audio
            audio = AudioFileClip(self.audio_path)
            
            # 6. Combine everything
            video = CompositeVideoClip([color_clip, title_text] + subtitle_clips)
            video = video.set_audio(audio)
            
            # 7. Write final video
            video.write_videofile(
                self.video_path,
                fps=24,
                codec='libx264',
                audio_codec='aac',
                preset='ultrafast'  # Use 'medium' for better quality in production
            )
            
            logger.info(f"Video created successfully: {self.video_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating video: {e}")
            return False
    
    def upload_to_youtube(self, title: str, topic: str) -> Optional[str]:
        """
        Upload the video to YouTube.
        
        Args:
            title: Video title
            topic: Video topic for tags and description
            
        Returns:
            YouTube video ID if successful, None otherwise
        """
        try:
            logger.info("Initializing YouTube client")
            youtube = self._init_youtube_client()
            
            # Prepare video metadata
            body = {
                "snippet": {
                    "title": f"{title} 🎥 #Shorts",
                    "description": f"#Shorts\nQuick info about {topic}\n\nAutomatically generated educational content",
                    "tags": [topic, "Shorts", "QuickTip", "Educational"],
                    "categoryId": self.config['youtube_category_id']
                },
                "status": {
                    "privacyStatus": "public",
                    "selfDeclaredMadeForKids": False
                }
            }
            
            # Upload with retries
            for attempt in range(self.config['max_retries']):
                try:
                    logger.info(f"Uploading video to YouTube (attempt {attempt+1}/{self.config['max_retries']})")
                    media = MediaFileUpload(
                        self.video_path, 
                        mimetype="video/mp4", 
                        chunksize=-1, 
                        resumable=True
                    )
                    
                    request = youtube.videos().insert(
                        part=",".join(body.keys()),
                        body=body,
                        media_body=media
                    )
                    
                    response = request.execute()
                    video_id = response["id"]
                    logger.info(f"Video uploaded successfully! Video ID: {video_id}")
                    return video_id
                    
                except Exception as e:
                    logger.error(f"Upload attempt {attempt+1} failed: {e}")
                    if attempt < self.config['max_retries'] - 1:
                        sleep_time = self.config['retry_delay'] * (2 ** attempt)  # Exponential backoff
                        logger.info(f"Retrying in {sleep_time} seconds...")
                        time.sleep(sleep_time)
                    else:
                        logger.error("All upload attempts failed")
                        return None
                        
        except Exception as e:
            logger.error(f"Error in YouTube upload process: {e}")
            return None
    
    def run_pipeline(self) -> Optional[str]:
        """
        Run the complete automation pipeline.
        
        Returns:
            YouTube video ID if successful, None otherwise
        """
        try:
            # 1. Get trending topic
            topics = self.get_trending_topics()
            if not topics:
                logger.error("Failed to get topics")
                return None
            
            topic = random.choice(topics)
            logger.info(f"Selected topic: {topic}")
            
            # 2. Generate script
            script = self.generate_script(topic)
            if not script:
                logger.error("Failed to generate script")
                return None
            
            # 3. Create video
            if not self.create_video(script, topic):
                logger.error("Failed to create video")
                return None
            
            # 4. Upload to YouTube
            title = f"{topic} in 30s"
            video_id = self.upload_to_youtube(title, topic)
            
            return video_id
            
        except Exception as e:
            logger.error(f"Error in automation pipeline: {e}")
            return None


def main():
    """Main entry point for the script."""
    try:
        logger.info("Starting YouTube Shorts automation")
        automation = YouTubeShortsAutomation()
        video_id = automation.run_pipeline()
        
        if video_id:
            logger.info(f"Pipeline completed successfully! Video ID: {video_id}")
            logger.info(f"Video URL: https://www.youtube.com/watch?v={video_id}")
            return 0
        else:
            logger.error("Pipeline failed")
            return 1
            
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)