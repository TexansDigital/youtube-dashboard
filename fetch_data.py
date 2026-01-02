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
                detail = details_map[video['video_id']]
                video.update(detail)
                
                # Calculate VPH
                video['vph'] = calculate_vph(video['views'], video.get('published_at'))
                
                # Calculate days since published
                if video.get('published_at'):
                    try:
                        pub_date = datetime.fromisoformat(video['published_at'].replace('Z', '+00:00'))
                        days_old = (datetime.now(TIMEZONE) - pub_date).days
                        video['days_since_published'] = days_old
                        video['views_per_day'] = round(video['views'] / max(days_old, 1), 1)
                    except:
                        video['days_since_published'] = None
                        video['views_per_day'] = None
    
    # Calculate channel averages and performance status
    channel_averages = calculate_channel_averages(videos)
    for video in videos:
        video['performance_status'] = calculate_performance_status(video, channel_averages)
    
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

def calculate_vph(views, published_at):
    """Calculate Views Per Hour (lifetime)"""
    from datetime import datetime
    
    if not published_at or views == 0:
        return 0
    
    try:
        # Parse ISO format datetime
        if isinstance(published_at, str):
            pub_date = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
        else:
            pub_date = published_at
        
        now = datetime.now(TIMEZONE)
        hours_since_published = (now - pub_date).total_seconds() / 3600
        
        if hours_since_published <= 0:
            return 0
        
        return round(views / hours_since_published, 1)
    except:
        return 0

def calculate_performance_status(video, channel_averages):
    """
    Calculate if video is performing above/below channel average.
    Returns: 'excellent', 'good', 'average', 'poor'
    """
    if not channel_averages:
        return 'unknown'
    
    scores = []
    
    # Compare engagement rate
    if video.get('engagement_rate') and channel_averages.get('avg_engagement_rate'):
        ratio = video['engagement_rate'] / channel_averages['avg_engagement_rate']
        scores.append(ratio)
    
    # Compare retention
    if video.get('avg_view_percentage') and channel_averages.get('avg_retention'):
        ratio = video['avg_view_percentage'] / channel_averages['avg_retention']
        scores.append(ratio)
    
    # Compare subscriber conversion
    if video.get('subscriber_conversion_rate') and channel_averages.get('avg_sub_conversion'):
        ratio = video['subscriber_conversion_rate'] / channel_averages['avg_sub_conversion']
        scores.append(ratio)
    
    if not scores:
        return 'unknown'
    
    avg_ratio = sum(scores) / len(scores)
    
    if avg_ratio >= 1.5:
        return 'excellent'
    elif avg_ratio >= 1.0:
        return 'good'
    elif avg_ratio >= 0.7:
        return 'average'
    else:
        return 'poor'

def calculate_channel_averages(videos):
    """Calculate channel-wide averages for comparison"""
    if not videos:
        return {}
    
    engagement_rates = [v.get('engagement_rate', 0) for v in videos if v.get('engagement_rate')]
    retention_rates = [v.get('avg_view_percentage', 0) for v in videos if v.get('avg_view_percentage')]
    sub_conversions = [v.get('subscriber_conversion_rate', 0) for v in videos if v.get('subscriber_conversion_rate')]
    
    return {
        'avg_engagement_rate': sum(engagement_rates) / len(engagement_rates) if engagement_rates else 0,
        'avg_retention': sum(retention_rates) / len(retention_rates) if retention_rates else 0,
        'avg_sub_conversion': sum(sub_conversions) / len(sub_conversions) if sub_conversions else 0,
    }

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
        'comparisons': {},
    }
    
    # Define main periods and their comparison periods
    main_periods = ['past_7_days', 'past_month', 'current_fy']
    comparison_mapping = {
        'past_7_days': ['prev_7_days', 'same_7_days_ly'],
        'past_month': ['prev_month', 'same_month_ly'],
        'current_fy': ['prev_fy_to_date']
    }
    
    # Fetch data for main periods
    for period_key in main_periods:
        if period_key not in date_ranges:
            continue
            
        period_info = date_ranges[period_key]
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
    
    # Fetch data for comparison periods
    print("  Fetching comparison periods...")
    for main_period, comp_periods in comparison_mapping.items():
        data['comparisons'][main_period] = {}
        
        for comp_key in comp_periods:
            if comp_key not in date_ranges:
                continue
                
            comp_info = date_ranges[comp_key]
            print(f"    - {comp_info['label']}...")
            
            start = comp_info['start']
            end = comp_info['end']
            
            comp_analytics = get_channel_analytics(start, end)
            
            if comp_analytics:
                data['comparisons'][main_period][comp_key] = {
                    'label': comp_info['label'],
                    'start_date': start.strftime('%Y-%m-%d'),
                    'end_date': end.strftime('%Y-%m-%d'),
                    'analytics': comp_analytics
                }
            
            time.sleep(API_CONFIG['rate_limit_delay'])
    
    # Calculate percentage changes for each comparison
    print("  Calculating comparison percentages...")
    for main_period in main_periods:
        if main_period not in data['periods']:
            continue
            
        current = data['periods'][main_period].get('analytics', {})
        if not current:
            continue
        
        for comp_key, comp_data in data['comparisons'].get(main_period, {}).items():
            previous = comp_data.get('analytics', {})
            if not previous:
                continue
            
            comp_data['changes'] = {
                'views': calculate_pct_change(current.get('views', 0), previous.get('views', 0)),
                'watch_time_hours': calculate_pct_change(current.get('watch_time_hours', 0), previous.get('watch_time_hours', 0)),
                'net_subscribers': calculate_pct_change(current.get('net_subscribers', 0), previous.get('net_subscribers', 0)),
                'engagement_total': calculate_pct_change(current.get('engagement_total', 0), previous.get('engagement_total', 0)),
                'avg_view_duration_seconds': calculate_pct_change(current.get('avg_view_duration_seconds', 0), previous.get('avg_view_duration_seconds', 0)),
                'likes': calculate_pct_change(current.get('likes', 0), previous.get('likes', 0)),
            }
    
    # Apply SEO scoring to all videos
    print("  Applying SEO scoring...")
    try:
        from seo_scoring import calculate_seo_score, analyze_and_update_keywords
        
        for period_key in data['top_videos']:
            for video in data['top_videos'][period_key]:
                video['seo_score'] = calculate_seo_score(video)
        
        # Monthly keyword analysis (only run if we have enough data)
        all_videos = []
        for period_key in data['top_videos']:
            all_videos.extend(data['top_videos'][period_key])
        
        if len(all_videos) >= 20:
            # Check if it's time for monthly analysis (first of month)
            today = datetime.now(TIMEZONE)
            if today.day <= 7:  # Run in first week of month
                print("  Running monthly keyword analysis...")
                analyze_and_update_keywords(all_videos)
    except ImportError:
        print("  SEO scoring module not found, skipping...")
    except Exception as e:
        print(f"  SEO scoring error: {e}")
    
    print("✅ Data fetch complete!")
    return data

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
