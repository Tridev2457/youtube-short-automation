#!/usr/bin/env python3
"""
YouTube Shorts Automation

Automates creating and uploading YouTube Shorts:
1. Topic selection/generation
2. Script/narration generation
3. Video asset creation
4. Video assembly
5. Upload to YouTube
6. Scheduling via cron/DAG

Requirements:
- Python 3.7+
- FFmpeg in PATH
- Python packages:
  pytrends, openai, google-api-python-client,
  google-auth-oauthlib, google-auth-httplib2,
  python-dotenv, gTTS, moviepy, nltk, requests
- Google API credentials in .env:
  OPENAI_API_KEY, PEXELS_API_KEY, FREESOUND_API_KEY,
  YOUTUBE_CLIENT_SECRETS_FILE, YOUTUBE_CREDENTIALS_FILE
"""
import os
import random
import time
import logging
import shutil
import math
import requests
import nltk
from datetime import datetime
from typing import List, Dict, Any, Optional

# Ensure punkt tokenizer
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)
from nltk.tokenize import sent_tokenize

from pytrends.request import TrendReq
import openai
from gtts import gTTS
import moviepy.editor as mp
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, AudioFileClip, ColorClip
import google.oauth2.credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Logging setup
default_log = "youtube_shorts.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(default_log), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class YouTubeShortsAutomation:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        # Base configuration
        self.config = {
            'output_dir': 'output',
            'temp_dir': 'temp',
            'target_duration': 30,
            'resolution': (1080, 1920),
            'openai_model': 'gpt-3.5-turbo',
            'youtube_category_id': '27',
            'max_retries': 3,
            'retry_delay': 5,
            'video_fps': 24,
            'video_codec': 'libx264',
            'audio_codec': 'aac',
            'video_preset': 'ultrafast',
            'title_font': 'Arial-Bold',
            'title_fontsize': 70,
            'title_color': 'white',
            'subtitle_font': 'Arial',
            'subtitle_fontsize': 50,
            'subtitle_color': 'white',
            'background_color': (0, 0, 0),
            'text_width_margin': 100,
            'pexels_api_key': os.getenv('PEXELS_API_KEY'),
            'freesound_api_key': os.getenv('FREESOUND_API_KEY'),
            'background_music_volume': 0.1
        }
        if config:
            self.config.update(config)
        os.makedirs(self.config['output_dir'], exist_ok=True)
        os.makedirs(self.config['temp_dir'], exist_ok=True)
        self.run_id = None
        self.audio_path = None
        self.video_path = None
        self._init_openai()

    def _init_openai(self):
        key = os.getenv('OPENAI_API_KEY')
        if not key:
            logger.warning("Missing OPENAI_API_KEY; using fallback scripts.")
            openai.api_key = None
        else:
            openai.api_key = key
            logger.info("OpenAI client initialized.")

    def _init_youtube_client(self):
        client_file = os.getenv('YOUTUBE_CLIENT_SECRETS_FILE', 'client_secrets.json')
        cred_file = os.getenv('YOUTUBE_CREDENTIALS_FILE', 'youtube_credentials.json')
        service_file = os.getenv('YOUTUBE_SERVICE_ACCOUNT_FILE')
        # Service account flow
        if service_file and os.path.exists(service_file):
            creds = Credentials.from_service_account_file(
                service_file,
                scopes=['https://www.googleapis.com/auth/youtube.upload']
            )
            return build('youtube', 'v3', credentials=creds)
        # Cached OAuth credentials
        if os.path.exists(cred_file):
            creds = google.oauth2.credentials.Credentials.from_authorized_user_file(cred_file)
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
            return build('youtube', 'v3', credentials=creds)
        # New OAuth flow
        if os.path.exists(client_file):
            flow = InstalledAppFlow.from_client_secrets_file(
                client_file,
                scopes=['https://www.googleapis.com/auth/youtube.upload']
            )
            creds = flow.run_local_server(port=0)
            with open(cred_file, 'w') as f:
                f.write(creds.to_json())
            return build('youtube', 'v3', credentials=creds)
        raise ValueError("YouTube credentials not found!")

    def get_trending_topics(self, count: int = 5, region: str = 'US') -> List[str]:
        try:
            df = TrendReq(hl='en-US', tz=360).trending_searches(pn=region.upper())
            return df.iloc[:, 0].head(count).tolist()
        except Exception as e:
            logger.warning(f"Google Trends failed: {e}")
            return ["Wild Tech Fact", "Crazy Science Hack", "Mind-blowing History"]

    def generate_script(self, topic: str) -> str:
        if not openai.api_key:
            # fallback script
            return f"🚀 {topic}? You won’t believe this crazy fact! Follow for more!"
        prompt = (
            f"🔥 INSANE FACT in under {self.config['target_duration']}s! "
            f"Start with a mind-blowing hook about {topic}, drop 2 jaw-dropping facts, then finish with 'Double-tap if you geek out too!' "
            "Use emojis and keep it under 70 words."
        )
        try:
            resp = openai.ChatCompletion.create(
                model=self.config['openai_model'],
                messages=[
                    {"role": "system", "content": "You write wild, engaging YouTube Shorts scripts."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.9,
                max_tokens=120
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"OpenAI generate error: {e}")
            return f"🚀 {topic}? You won’t believe this crazy fact! Follow for more!"

    def fetch_background_video(self, topic: str) -> Optional[str]:
        key = self.config.get('pexels_api_key')
        if not key:
            logger.info("No PEXELS_API_KEY; skipping video fetch.")
            return None
        hdr = {'Authorization': key}
        params = {'query': topic, 'orientation': 'portrait', 'size': 'medium', 'per_page': 1}
        r = requests.get('https://api.pexels.com/videos/search', headers=hdr, params=params)
        vids = r.json().get('videos', [])
        if not vids:
            logger.info("Pexels returned no videos.")
            return None
        url = vids[0]['video_files'][0]['link']
        out = os.path.join(self.config['temp_dir'], 'broll.mp4')
        with open(out, 'wb') as f:
            f.write(requests.get(url).content)
        logger.info(f"Downloaded B-roll: {out}")
        return out

    def fetch_background_music(self) -> Optional[str]:
        """Download an upbeat royalty-free music clip from FreeSound for this topic."""
        key = self.config.get('freesound_api_key')
        if not key:
            logger.info("No FREESOUND_API_KEY; skipping music fetch.")
            return None
        headers = {'Authorization': f'Token {key}'}
        params = {
            'query': 'upbeat',
            'duration__lte': self.config['target_duration'],
            'page_size': 1
        }
        resp = requests.get('https://freesound.org/apiv2/search/text/', headers=headers, params=params)
        if resp.status_code != 200:
            logger.warning(f"FreeSound API error: HTTP {resp.status_code}")
            return None
        results = resp.json().get('results', [])
        if not results:
            logger.info("FreeSound returned no results.")
            return None
        first = results[0]
        previews = first.get('previews', {})
        url = previews.get('preview-hq-mp3')
        if not url:
            logger.warning("No preview URL found for FreeSound result.")
            return None
        out_path = os.path.join(self.config['temp_dir'], 'bgm.mp3')
        try:
            with open(out_path, 'wb') as f:
                f.write(requests.get(url).content)
            logger.info(f"Downloaded background music to {out_path}")
            return out_path
        except Exception as e:
            logger.warning(f"Failed to download FreeSound preview: {e}")
            return None

    def text_to_speech(self, text: str, out_path: str) -> bool:
        try:
            tts = gTTS(text=text, lang='en', slow=False)
            tts.save(out_path)
            return True
        except Exception as e:
            logger.error(f"TTS error: {e}")
            return False

    def create_video(self, script: str, topic: str) -> bool:
        if not self.text_to_speech(script, self.audio_path):
            return False
        audio = AudioFileClip(self.audio_path)
        dur = audio.duration
        w, h = self.config['resolution']
        clips = []
        # background video or solid color
        bfile = self.fetch_background_video(topic)
        if bfile:
            bg = VideoFileClip(bfile).subclip(0, dur)
            bg = bg.resize(height=h).crop(x_center=w/2, y_center=h/2, width=w, height=h)
        else:
            bg = ColorClip((w, h), color=self.config['background_color'], duration=dur)
        clips.append(bg)
        # title overlay
        td = min(4.0, dur * 0.2)
        title = TextClip(
            txt=topic.upper(),
            fontsize=self.config['title_fontsize'],
            color=self.config['title_color'],
            font=self.config['title_font'],
            size=(w - self.config['text_width_margin'], None),
            method='caption',
            align='center'
        ).set_position(('center', h * 0.2)).set_duration(td)
        clips.append(title)
        # subtitles
        est_wps = len(script.split()) / dur if dur>0 else 10
        cursor = td
        for sent in sent_tokenize(script):
            d = max(0.5, len(sent.split()) / est_wps)
            d = min(d, dur - cursor)
            if d < 0.1:
                break
            sub = TextClip(
                txt=sent,
                fontsize=self.config['subtitle_fontsize'],
                color=self.config['subtitle_color'],
                font=self.config['subtitle_font'],
                size=(w - self.config['text_width_margin'], None),
                method='caption',
                align='center'
            ).set_position(('center', 'center')).set_start(cursor).set_duration(d)
            clips.append(sub)
            cursor += d
        # compose video
        video = CompositeVideoClip(clips, size=(w, h)).set_audio(audio).set_duration(dur)
        # background music mix
        mfile = self.fetch_background_music()
        if mfile:
            bgm = AudioFileClip(mfile).volumex(self.config['background_music_volume'])
            if bgm.duration < dur:
                bgm = mp.concatenate_audioclips([bgm] * math.ceil(dur / bgm.duration)).subclip(0, dur)
            else:
                bgm = bgm.subclip(0, dur)
            video = video.set_audio(mp.CompositeAudioClip([audio, bgm]))
        # export
        video.write_videofile(
            self.video_path,
            fps=self.config['video_fps'],
            codec=self.config['video_codec'],
            audio_codec=self.config['audio_codec'],
            preset=self.config['video_preset']
        )
        return True

    def upload_to_youtube(self, title: str, topic: str, description: str, tags: List[str]) -> Optional[str]:
        if not os.path.exists(self.video_path):
            return None
        youtube = self._init_youtube_client()
        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': list(set(tags + [topic, 'Shorts'])),
                'categoryId': self.config['youtube_category_id']
            },
            'status': {
                'privacyStatus': 'public',
                'selfDeclaredMadeForKids': False
            }
        }
        media = MediaFileUpload(self.video_path, mimetype='video/mp4', chunksize=10*1024*1024, resumable=True)
        request = youtube.videos().insert(part=','.join(body.keys()), body=body, media_body=media)
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                logger.info(f"Upload {int(status.progress()*100)}%")
        vid = response.get('id')
        logger.info(f"Uploaded video ID: {vid}")
        return vid

    def cleanup_temp_files(self):
        shutil.rmtree(self.config['temp_dir'], ignore_errors=True)
        os.makedirs(self.config['temp_dir'], exist_ok=True)

    def run_pipeline(self) -> Optional[str]:
        # setup file paths
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.run_id = f'short_{ts}'
        self.audio_path = os.path.join(self.config['temp_dir'], f'{self.run_id}_audio.mp3')
        self.video_path = os.path.join(self.config['output_dir'], f'{self.run_id}.mp4')
        self.cleanup_temp_files()

        topics = self.get_trending_topics()
        topic = random.choice(topics)
        logger.info(f"Selected topic: {topic}")

        script = self.generate_script(topic)
        logger.info(f"Script: {script}")

        if not self.create_video(script, topic):
            logger.error("Video creation failed.")
            return None

        title = f"{topic} Explained in 30 Seconds! ⏱️ #Shorts"
        description = (
            f"Quick facts about {topic}! 🔥\n\n"
            "#shorts #CrazyFacts #LearnOnYouTube\n"
            "Auto-generated by script."
        )
        tags = [topic, 'Crazy', 'Facts']
        return self.upload_to_youtube(title, topic, description, tags)

if __name__ == '__main__':
    if shutil.which('ffmpeg') is None:
        logger.error("FFmpeg not found in PATH. Please install FFmpeg.")
        exit(1)
    auto = YouTubeShortsAutomation()
    vid = auto.run_pipeline()
    if vid:
        logger.info(f"🚀 Completed! Video https://youtu.be/{vid}")
    else:
        logger.error("❌ Pipeline failed.")
