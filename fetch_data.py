"""
YouTube Data Fetcher
Pulls video data, statistics, and analytics from YouTube APIs
"""

import json
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from auth import get_youtube_data_api, get_youtube_analytics_api
from config import (
    CHANNEL_ID, TIMEZONE, EXCLUDED_VIDEO_IDS, API_CONFIG,
    get_date_ranges, is_blocked_content, is_flagged_content, is_excluded_video
)

def get_channel_stats():
    """Get overall channel statistics"""
    youtube = get_youtube_data_api()
    
    response = youtube.channels().list(
        part='snippet,statistics,contentDetails',
        id=CHANNEL_ID
    ).execute()
    
    if not response.get('items'):
        raise ValueError(f"Channel {CHANNEL_ID} not found")
    
    channel = response['items'][0]
    
    return {
        'channel_id': CHANNEL_ID,
        'title': channel['snippet']['title'],
        'description': channel['snippet'].get('description', ''),
        'thumbnail': channel['snippet']['thumbnails']['high']['url'],
        'uploads_playlist': channel['contentDetails']['relatedPlaylists']['uploads'],
        'statistics': {
            'subscribers': int(channel['statistics'].get('subscriberCount', 0)),
            'total_views': int(channel['statistics'].get('viewCount', 0)),
            'video_count': int(channel['statistics'].get('videoCount', 0)),
        },
        'fetched_at': datetime.now(TIMEZONE).isoformat()
    }

def get_all_videos(max_results=500):
    """Get all videos from the channel uploads playlist"""
    youtube = get_youtube_data_api()
    
    # First get the uploads playlist ID
    channel_stats = get_channel_stats()
    uploads_playlist = channel_stats['uploads_playlist']
    
    videos = []
    next_page_token = None
    
    while len(videos) < max_results:
        response = youtube.playlistItems().list(
            part='snippet,contentDetails',
            playlistId=uploads_playlist,
            maxResults=min(50, max_results - len(videos)),
            pageToken=next_page_token
        ).execute()
        
        for item in response.get('items', []):
            video_id = item['contentDetails']['videoId']
            
            # Skip excluded videos
            if is_excluded_video(video_id):
                continue
            
            videos.append({
                'video_id': video_id,
                'title': item['snippet']['title'],
                'description': item['snippet'].get('description', ''),
                'published_at': item['snippet']['publishedAt'],
                'thumbnail': item['snippet']['thumbnails'].get('high', {}).get('url', ''),
            })
        
        next_page_token = response.get('nextPageToken')
        if not next_page_token:
            break
        
        time.sleep(API_CONFIG['rate_limit_delay'])
    
    return videos

def get_video_details(video_ids):
    """Get detailed statistics for a list of video IDs"""
    youtube = get_youtube_data_api()
    
    all_details = []
    
    # Process in batches of 50 (API limit)
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]
        
        response = youtube.videos().list(
            part='snippet,statistics,contentDetails',
            id=','.join(batch)
        ).execute()
        
        for item in response.get('items', []):
            video_id = item['id']
            
            # Parse duration (ISO 8601 format like PT4M13S)
            duration_str = item['contentDetails']['duration']
            duration_seconds = parse_duration(duration_str)
            
            # Check for blocked/flagged content
            title = item['snippet']['title']
            description = item['snippet'].get('description', '')
            is_blocked, block_reason = is_blocked_content(title, description)
            flags = is_flagged_content(title, description)
            
            all_details.append({
                'video_id': video_id,
                'title': title,
                'description': description,
                'published_at': item['snippet']['publishedAt'],
                'thumbnail': item['snippet']['thumbnails'].get('high', {}).get('url', ''),
                'duration_seconds': duration_seconds,
                'duration_formatted': format_duration(duration_seconds),
                'is_short': duration_seconds <= 60,
                'statistics': {
                    'views': int(item['statistics'].get('viewCount', 0)),
                    'likes': int(item['statistics'].get('likeCount', 0)),
                    'comments': int(item['statistics'].get('commentCount', 0)),
                },
                'content_status': {
                    'is_blocked': is_blocked,
                    'block_reason': block_reason,
                    'flags': flags,
                },
            })
        
        time.sleep(API_CONFIG['rate_limit_delay'])
    
    return all_details

def get_video_analytics(video_id, start_date, end_date):
    """Get analytics for a specific video in a date range"""
    analytics = get_youtube_analytics_api()
    
    response = analytics.reports().query(
        ids=f'channel=={CHANNEL_ID}',
        startDate=start_date.strftime('%Y-%m-%d'),
        endDate=end_date.strftime('%Y-%m-%d'),
        metrics='views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained,subscribersLost,likes,comments,shares',
        dimensions='video',
        filters=f'video=={video_id}'
    ).execute()
    
    if response.get('rows'):
        row = response['rows'][0]
        return {
            'video_id': row[0],
            'views': row[1],
            'watch_time_minutes': row[2],
            'avg_view_duration_seconds': row[3],
            'avg_view_percentage': row[4],
            'subscribers_gained': row[5],
            'subscribers_lost': row[6],
            'likes': row[7],
            'comments': row[8],
            'shares': row[9],
        }
    
    return None

def get_channel_analytics(start_date, end_date):
    """Get overall channel analytics for a date range"""
    analytics = get_youtube_analytics_api()
    
    response = analytics.reports().query(
        ids=f'channel=={CHANNEL_ID}',
        startDate=start_date.strftime('%Y-%m-%d'),
        endDate=end_date.strftime('%Y-%m-%d'),
        metrics='views,estimatedMinutesWatched,averageViewDuration,subscribersGained,subscribersLost,likes,comments,shares'
    ).execute()
    
    if response.get('rows'):
        row = response['rows'][0]
        return {
            'views': row[0],
            'watch_time_minutes': row[1],
            'watch_time_hours': round(row[1] / 60, 2),
            'avg_view_duration_seconds': row[2],
            'subscribers_gained': row[3],
            'subscribers_lost': row[4],
            'net_subscribers': row[3] - row[4],
            'likes': row[5],
            'comments': row[6],
            'shares': row[7],
            'engagement_total': row[5] + row[6] + row[7],
        }
    
    return None

def get_traffic_sources(start_date, end_date):
    """Get traffic source breakdown"""
    analytics = get_youtube_analytics_api()
    
    response = analytics.reports().query(
        ids=f'channel=={CHANNEL_ID}',
        startDate=start_date.strftime('%Y-%m-%d'),
        endDate=end_date.strftime('%Y-%m-%d'),
        metrics='views,estimatedMinutesWatched',
        dimensions='insightTrafficSourceType',
        sort='-views'
    ).execute()
    
    sources = []
    for row in response.get('rows', []):
        sources.append({
            'source': row[0],
            'views': row[1],
            'watch_time_minutes': row[2],
        })
    
    return sources

def get_top_videos(start_date, end_date, max_results=50):
    """Get top performing videos in a date range"""
    analytics = get_youtube_analytics_api()
    
    response = analytics.reports().query(
        ids=f'channel=={CHANNEL_ID}',
        startDate=start_date.strftime('%Y-%m-%d'),
        endDate=end_date.strftime('%Y-%m-%d'),
        metrics='views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained,likes,comments,shares',
        dimensions='video',
        sort='-views',
        maxResults=max_results
    ).execute()
    
    videos = []
    video_ids = []
    
    for row in response.get('rows', []):
        video_id = row[0]
        
        if is_excluded_video(video_id):
            continue
            
        video_ids.append(video_id)
        videos.append({
            'video_id': video_id,
            'views': row[1],
            'watch_time_minutes': row[2],
            'avg_view_duration_seconds': row[3],
            'avg_view_percentage': row[4],
            'subscribers_gained': row[5],
            'likes': row[6],
            'comments': row[7],
            'shares': row[8],
            'engagement_rate': calculate_engagement_rate(row[6], row[7], row[8], row[1]),
            'subscriber_conversion_rate': calculate_conversion_rate(row[5], row[1]),
        })
    
    # Enrich with video details
    if video_ids:
        details = get_video_details(video_ids)
        details_map = {d['video_id']: d for d in details}
        
        for video in videos:
            if video['video_id'] in details_map:
                video.update(details_map[video['video_id']])
    
    return videos

def get_retention_data(video_id):
    """Get audience retention curve for a video (for Shorts identification)"""
    analytics = get_youtube_analytics_api()
    
    try:
        response = analytics.reports().query(
            ids=f'channel=={CHANNEL_ID}',
            startDate='2020-01-01',  # Use wide range for lifetime data
            endDate=datetime.now(TIMEZONE).strftime('%Y-%m-%d'),
            metrics='audienceWatchRatio',
            dimensions='elapsedVideoTimeRatio',
            filters=f'video=={video_id}'
        ).execute()
        
        retention_curve = []
        for row in response.get('rows', []):
            retention_curve.append({
                'time_ratio': row[0],  # 0.0 to 1.0 (position in video)
                'retention': row[1],   # 0.0 to 1.0 (% still watching)
            })
        
        return retention_curve
        
    except Exception as e:
        print(f"Warning: Could not get retention data for {video_id}: {e}")
        return []

def calculate_engagement_rate(likes, comments, shares, views):
    """Calculate engagement rate: (likes + comments + shares) / views * 100"""
    if views == 0:
        return 0
    return round((likes + comments + shares) / views * 100, 2)

def calculate_conversion_rate(subscribers_gained, views):
    """Calculate subscriber conversion rate: subscribers / views * 100"""
    if views == 0:
        return 0
    return round(subscribers_gained / views * 100, 3)

def parse_duration(duration_str):
    """Parse ISO 8601 duration (e.g., PT4M13S) to seconds"""
    import re
    
    pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
    match = re.match(pattern, duration_str)
    
    if not match:
        return 0
    
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    
    return hours * 3600 + minutes * 60 + seconds

def format_duration(seconds):
    """Format seconds to human-readable duration"""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}:{secs:02d}"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:02d}"

def fetch_all_dashboard_data():
    """Main function to fetch all data needed for the dashboard"""
    print("Fetching dashboard data...")
    
    date_ranges = get_date_ranges()
    data = {
        'generated_at': datetime.now(TIMEZONE).isoformat(),
        'channel': get_channel_stats(),
        'periods': {},
        'top_videos': {},
        'traffic_sources': {},
    }
    
    # Fetch data for each time period
    for period_key, period_info in date_ranges.items():
        if period_key == 'same_week_last_year':
            continue  # This is for comparison, handled separately
            
        print(f"  Fetching {period_info['label']}...")
        
        start = period_info['start']
        end = period_info['end']
        
        # Channel-level analytics
        data['periods'][period_key] = {
            'label': period_info['label'],
            'start_date': start.strftime('%Y-%m-%d'),
            'end_date': end.strftime('%Y-%m-%d'),
            'analytics': get_channel_analytics(start, end),
        }
        
        # Top videos for the period
        data['top_videos'][period_key] = get_top_videos(start, end)
        
        # Traffic sources
        data['traffic_sources'][period_key] = get_traffic_sources(start, end)
        
        time.sleep(API_CONFIG['rate_limit_delay'])
    
    # Calculate comparisons
    print("  Calculating comparisons...")
    data['comparisons'] = calculate_comparisons(data)
    
    print("✅ Data fetch complete!")
    return data

def calculate_comparisons(data):
    """Calculate period-over-period comparisons"""
    comparisons = {}
    
    # Current FY vs Previous FY
    if 'current_fy' in data['periods'] and 'previous_fy' in data['periods']:
        current = data['periods']['current_fy']['analytics']
        previous = data['periods']['previous_fy']['analytics']
        
        if current and previous:
            comparisons['fy_yoy'] = {
                'views_change': calculate_pct_change(current['views'], previous['views']),
                'watch_time_change': calculate_pct_change(current['watch_time_hours'], previous['watch_time_hours']),
                'subscribers_change': calculate_pct_change(current['net_subscribers'], previous['net_subscribers']),
            }
    
    # Current month vs previous month (approximation)
    if 'past_month' in data['periods']:
        # Note: For true month comparison, would need separate API calls
        pass
    
    return comparisons

def calculate_pct_change(current, previous):
    """Calculate percentage change between two values"""
    if previous == 0:
        return None
    return round((current - previous) / previous * 100, 1)

def save_data(data, filepath='data/dashboard_data.json'):
    """Save data to JSON file"""
    import os
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    
    print(f"Data saved to {filepath}")

if __name__ == "__main__":
    data = fetch_all_dashboard_data()
    save_data(data)
