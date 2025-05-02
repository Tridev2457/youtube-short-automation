# Patching

This repository contains various utility scripts for automation tasks.

## YouTube Shorts Automation

An end-to-end automation system for creating and uploading YouTube Shorts videos.

### Features

- Automatic topic selection using Google Trends
- AI-generated scripts using OpenAI GPT
- Text-to-speech narration
- Automatic video assembly with captions
- YouTube upload via API
- Error handling and retries

### Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Set up environment variables:
   - Copy `.env.example` to `.env`
   - Add your OpenAI API key
   - Configure YouTube API credentials (see below)

3. YouTube API Setup:
   - Create a project in [Google Cloud Console](https://console.cloud.google.com/)
   - Enable the YouTube Data API v3
   - Create OAuth credentials or a service account
   - Download the credentials file and update the path in `.env`

### Usage

Run the script:
```
python youtube_shorts_automation.py
```

The script will:
1. Select a trending topic
2. Generate a script
3. Convert the script to speech
4. Create a video with captions
5. Upload to YouTube as a Short

### Scheduling

For automated daily uploads, set up a cron job:
```
0 12 * * * cd /path/to/repo && python youtube_shorts_automation.py
```