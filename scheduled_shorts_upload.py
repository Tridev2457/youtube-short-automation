#!/usr/bin/env python3
"""
Scheduled YouTube Shorts Upload Script

This script is designed to be run via cron or other schedulers for automated
daily uploads of YouTube Shorts. It includes enhanced error handling and
logging suitable for unattended operation.

Example cron entry (daily at 12:00 PM):
0 12 * * * cd /path/to/repo && python scheduled_shorts_upload.py

The script will:
1. Check if a video has already been uploaded today
2. Run the YouTube Shorts automation pipeline
3. Log the results to a file
4. Send notifications (if configured)
"""

import os
import sys
import logging
import traceback
from datetime import datetime
import json
import smtplib
from email.message import EmailMessage
from youtube_shorts_automation import YouTubeShortsAutomation

# Configure logging
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"shorts_upload_{datetime.now().strftime('%Y%m%d')}.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("scheduled_shorts_upload")

# Track uploads
UPLOAD_HISTORY_FILE = "upload_history.json"


def load_upload_history():
    """Load the upload history from file."""
    if not os.path.exists(UPLOAD_HISTORY_FILE):
        return {}
    
    try:
        with open(UPLOAD_HISTORY_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading upload history: {e}")
        return {}


def save_upload_history(history):
    """Save the upload history to file."""
    try:
        with open(UPLOAD_HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving upload history: {e}")


def send_notification(subject, message):
    """Send an email notification."""
    email = os.getenv("NOTIFICATION_EMAIL")
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    
    if not all([email, smtp_server, smtp_user, smtp_password]):
        logger.warning("Notification settings not configured, skipping notification")
        return False
    
    try:
        msg = EmailMessage()
        msg.set_content(message)
        msg['Subject'] = subject
        msg['From'] = smtp_user
        msg['To'] = email
        
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        
        logger.info(f"Notification sent to {email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        return False


def main():
    """Main entry point for the scheduled upload script."""
    try:
        logger.info("Starting scheduled YouTube Shorts upload")
        
        # Check if we already uploaded today
        today = datetime.now().strftime("%Y-%m-%d")
        history = load_upload_history()
        
        if today in history:
            logger.info(f"Already uploaded a video today (ID: {history[today]})")
            return 0
        
        # Initialize the automation with default settings
        automation = YouTubeShortsAutomation()
        
        # Run the pipeline
        video_id = automation.run_pipeline()
        
        if video_id:
            # Update history
            history[today] = video_id
            save_upload_history(history)
            
            # Log success
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            logger.info(f"Successfully uploaded video: {video_url}")
            
            # Send notification
            send_notification(
                "YouTube Shorts Upload Success",
                f"Successfully uploaded a new YouTube Short!\n\nVideo URL: {video_url}"
            )
            
            return 0
        else:
            logger.error("Failed to upload video")
            
            # Send notification
            send_notification(
                "YouTube Shorts Upload Failed",
                f"Failed to upload YouTube Short. Check logs at {log_file}"
            )
            
            return 1
            
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Unhandled exception: {e}\n{error_details}")
        
        # Send notification
        send_notification(
            "YouTube Shorts Upload Error",
            f"Error during YouTube Shorts upload:\n\n{error_details}\n\nCheck logs at {log_file}"
        )
        
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)