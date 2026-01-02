"""
YouTube API Authentication Helper
Handles OAuth2 authentication using stored credentials
"""

import os
import json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Scopes required for the dashboard
SCOPES = [
    'https://www.googleapis.com/auth/youtube.readonly',
    'https://www.googleapis.com/auth/yt-analytics.readonly'
]

def get_credentials():
    """
    Get valid OAuth2 credentials from environment variables.
    Uses refresh token to generate new access token.
    """
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
    refresh_token = os.environ.get('GOOGLE_REFRESH_TOKEN')
    
    if not all([client_id, client_secret, refresh_token]):
        raise ValueError(
            "Missing required environment variables. "
            "Ensure GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REFRESH_TOKEN are set."
        )
    
    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES
    )
    
    # Refresh to get a valid access token
    if credentials.expired or not credentials.valid:
        credentials.refresh(Request())
    
    return credentials

def get_youtube_data_api():
    """Get authenticated YouTube Data API v3 service"""
    credentials = get_credentials()
    return build('youtube', 'v3', credentials=credentials)

def get_youtube_analytics_api():
    """Get authenticated YouTube Analytics API service"""
    credentials = get_credentials()
    return build('youtubeAnalytics', 'v2', credentials=credentials)

def test_authentication():
    """Test that authentication is working correctly"""
    try:
        youtube = get_youtube_data_api()
        
        # Simple test: get channel info
        response = youtube.channels().list(
            part='snippet,statistics',
            mine=True
        ).execute()
        
        if response.get('items'):
            channel = response['items'][0]
            print(f"✅ Authentication successful!")
            print(f"   Channel: {channel['snippet']['title']}")
            print(f"   Subscribers: {channel['statistics'].get('subscriberCount', 'Hidden')}")
            return True
        else:
            print("❌ Authentication worked but no channel found")
            return False
            
    except Exception as e:
        print(f"❌ Authentication failed: {str(e)}")
        return False

if __name__ == "__main__":
    test_authentication()
