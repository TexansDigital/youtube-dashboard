"""
Shorts Clip Identifier
Analyzes video retention curves to identify potential Shorts clips
"""

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from auth import get_youtube_data_api, get_youtube_analytics_api
from config import (
    CHANNEL_ID, TIMEZONE, SHORTS_CONFIG, EXCLUDED_VIDEO_IDS,
    is_blocked_content, is_flagged_content, is_excluded_video,
    TITLE_PATTERNS, BRAND_VOICE, STAR_PLAYERS
)
from fetch_data import get_top_videos, get_video_details, get_retention_data, get_all_videos

def identify_shorts_candidates():
    """
    Main function to identify potential Shorts clips from existing videos.
    Analyzes: Last 90 days + all-time top 50 performers
    """
    print("🎬 Identifying Shorts candidates...")
    
    candidates = []
    
    # Get videos from last 90 days
    print("  Fetching recent videos (last 90 days)...")
    end_date = datetime.now(TIMEZONE)
    start_date = end_date - timedelta(days=SHORTS_CONFIG['scope']['recent_days'])
    
    recent_videos = get_top_videos(start_date, end_date, max_results=100)
    
    # Get all-time top performers
    print("  Fetching all-time top performers...")
    all_time_start = datetime(2015, 1, 1, tzinfo=TIMEZONE)  # Channel history start
    top_videos = get_top_videos(all_time_start, end_date, max_results=SHORTS_CONFIG['scope']['top_performers_count'])
    
    # Combine and deduplicate
    all_videos = {v['video_id']: v for v in recent_videos}
    for v in top_videos:
        if v['video_id'] not in all_videos:
            all_videos[v['video_id']] = v
    
    print(f"  Analyzing {len(all_videos)} unique videos...")
    
    for video_id, video in all_videos.items():
        # Skip already-short videos
        if video.get('is_short') or video.get('duration_seconds', 0) <= 60:
            continue
        
        # Skip excluded videos
        if is_excluded_video(video_id):
            continue
        
        # Skip blocked content
        is_blocked, _ = is_blocked_content(video.get('title', ''), video.get('description', ''))
        if is_blocked:
            continue
        
        # Get retention curve
        retention_curve = get_retention_data(video_id)
        
        if not retention_curve:
            continue
        
        # Find high-retention segments
        clips = find_clip_segments(video, retention_curve)
        
        if clips:
            candidates.extend(clips)
    
    # Sort by priority score and limit
    candidates.sort(key=lambda x: x['priority_score'], reverse=True)
    
    print(f"✅ Found {len(candidates)} potential Shorts clips")
    
    return candidates

def find_clip_segments(video, retention_curve):
    """
    Analyze retention curve to find high-engagement segments suitable for Shorts.
    
    Algorithm:
    1. Calculate average retention for the video
    2. Find segments with retention >= 25% above average
    3. Ensure segment is 15-60 seconds and sustained 10+ seconds
    4. Skip intro (first 10%) and outro (last 5%)
    """
    if not retention_curve or len(retention_curve) < 10:
        return []
    
    config = SHORTS_CONFIG['detection']
    video_duration = video.get('duration_seconds', 0)
    
    if video_duration < 60:  # Too short to clip
        return []
    
    # Calculate average retention
    avg_retention = sum(r['retention'] for r in retention_curve) / len(retention_curve)
    spike_threshold = avg_retention * (1 + config['retention_spike_threshold'])
    
    # Define skip zones
    intro_cutoff = config['skip_intro_percent'] / 100
    outro_cutoff = 1 - (config['skip_outro_percent'] / 100)
    
    # Find retention spikes
    spikes = []
    current_spike = None
    
    for point in retention_curve:
        time_ratio = point['time_ratio']
        retention = point['retention']
        
        # Skip intro and outro
        if time_ratio < intro_cutoff or time_ratio > outro_cutoff:
            if current_spike:
                spikes.append(current_spike)
                current_spike = None
            continue
        
        # Check if this is a spike
        if retention >= spike_threshold:
            if current_spike is None:
                current_spike = {
                    'start_ratio': time_ratio,
                    'end_ratio': time_ratio,
                    'peak_retention': retention,
                    'retention_values': [retention]
                }
            else:
                current_spike['end_ratio'] = time_ratio
                current_spike['peak_retention'] = max(current_spike['peak_retention'], retention)
                current_spike['retention_values'].append(retention)
        else:
            if current_spike:
                spikes.append(current_spike)
                current_spike = None
    
    if current_spike:
        spikes.append(current_spike)
    
    # Convert spikes to clip candidates
    clips = []
    
    for spike in spikes:
        start_seconds = int(spike['start_ratio'] * video_duration)
        end_seconds = int(spike['end_ratio'] * video_duration)
        duration = end_seconds - start_seconds
        
        # Check duration constraints
        if duration < config['min_duration_seconds']:
            continue
        if duration > config['max_duration_seconds']:
            # Trim to max duration around peak
            duration = config['max_duration_seconds']
            end_seconds = start_seconds + duration
        
        # Check sustained threshold
        if len(spike['retention_values']) < config['sustained_seconds']:
            continue
        
        # Calculate priority score
        avg_spike_retention = sum(spike['retention_values']) / len(spike['retention_values'])
        retention_boost = avg_spike_retention / avg_retention
        duration_bonus = get_duration_bonus(duration)
        priority_score = retention_boost * duration_bonus * 100
        
        # Get content flags
        flags = is_flagged_content(video.get('title', ''), video.get('description', ''))
        
        clip = {
            'video_id': video['video_id'],
            'video_title': video.get('title', ''),
            'video_url': f"https://youtube.com/watch?v={video['video_id']}",
            'timestamped_url': f"https://youtube.com/watch?v={video['video_id']}&t={start_seconds}",
            'start_seconds': start_seconds,
            'end_seconds': end_seconds,
            'start_formatted': format_timestamp(start_seconds),
            'end_formatted': format_timestamp(end_seconds),
            'clip_duration': duration,
            'retention_score': round(avg_spike_retention * 100, 1),
            'video_avg_retention': round(avg_retention * 100, 1),
            'retention_boost': round(retention_boost, 2),
            'priority_score': round(priority_score, 1),
            'flags': flags,
            'suggested_title': generate_title_suggestion(video),
            'suggested_hashtags': generate_hashtags(video),
            'content_type': classify_content_type(video),
            'source_video_views': video.get('views', 0),
            'identified_at': datetime.now(TIMEZONE).isoformat(),
            'clip_created': False,  # To be updated manually
            'shorts_video_id': None,  # To be filled when clip is created
        }
        
        clips.append(clip)
    
    # Sort by priority and limit per video
    clips.sort(key=lambda x: x['priority_score'], reverse=True)
    return clips[:SHORTS_CONFIG['clips_per_video']]

def get_duration_bonus(duration):
    """Get duration bonus multiplier based on ideal Shorts length"""
    bonuses = SHORTS_CONFIG['duration_bonuses']
    
    if 30 <= duration <= 45:
        return bonuses['30-45']
    elif 15 <= duration < 30:
        return bonuses['15-30']
    elif 45 < duration <= 60:
        return bonuses['45-60']
    else:
        return 0.8  # Outside ideal range

def format_timestamp(seconds):
    """Format seconds to MM:SS or HH:MM:SS"""
    if seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}:{secs:02d}"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:02d}"

def generate_title_suggestion(video):
    """Generate a suggested title for the Shorts clip"""
    import hashlib
    
    original_title = video.get('title', '')
    video_id = video.get('video_id', '')
    title_lower = original_title.lower()
    
    # Use video_id to create consistent but varied selection
    hash_val = int(hashlib.md5(video_id.encode()).hexdigest(), 16)
    
    # Detect content type and players
    content_type = classify_content_type(video)
    
    # Player-specific patterns
    if STAR_PLAYERS['current']['name'].lower() in title_lower or 'stroud' in title_lower:
        player = "C.J. Stroud"
        patterns = [
            f"{player} is DIFFERENT 🔥",
            f"This {player} throw is INSANE 😱",
            f"{player} doing {player} things 😤",
            f"QB1 came to PLAY 🔥",
            f"{player} said WATCH THIS 👀",
            f"How did {player} make this throw?!",
        ]
    elif STAR_PLAYERS['historical']['name'].lower() in title_lower or 'watt' in title_lower:
        player = "J.J. Watt"
        patterns = [
            f"Prime {player} was a PROBLEM 😤",
            f"Never forget this {player} moment",
            f"{player} was BUILT DIFFERENT",
            f"This is why {player} is a legend 🐐",
            f"{player} absolutely DOMINATED here",
        ]
    elif 'dell' in title_lower or 'tank' in title_lower:
        patterns = [
            "Tank Dell is a PROBLEM 🔥",
            "This Tank Dell catch is UNREAL 😱",
            "Tank making it look EASY 💪",
            "How did Tank Dell do this?!",
        ]
    elif 'collins' in title_lower or 'nico' in title_lower:
        patterns = [
            "Nico Collins can't be stopped 🔥",
            "This Nico Collins play is CRAZY 😱",
            "Nico doing Nico things 😤",
            "WR1 showed up BIG 💪",
        ]
    elif 'pitre' in title_lower or 'jalen' in title_lower:
        patterns = [
            "Jalen Pitre said NOT TODAY 🚫",
            "This interception was INSANE 😱",
            "Pitre with the TAKEAWAY 🔥",
            "The defense came to PLAY 💪",
        ]
    elif 'ryans' in title_lower or 'demeco' in title_lower:
        patterns = [
            "Coach DeMeco Ryans is HIM 🔥",
            "This is why we love DeMeco 💪",
            "DeMeco Ryans gets it 😤",
            "Leadership like no other 🐐",
        ]
    # Content-type specific patterns
    elif content_type == 'highlight':
        patterns = [
            "This play is UNBELIEVABLE 😱",
            "How did they pull this off?! 🔥",
            "H-Town made a STATEMENT 💪",
            "The Texans came to DOMINATE 😤",
            "You have to see this play 👀",
            "REPLAY THIS. Over and over. 🔥",
        ]
    elif content_type == 'interview':
        patterns = [
            "This interview hits DIFFERENT 💯",
            "Real talk from the squad 🎙️",
            "You need to hear this 👀",
            "H-Town keeps it 💯",
            "The mentality is ELITE 😤",
        ]
    elif content_type == 'behind_the_scenes':
        patterns = [
            "Inside look at H-Town 👀",
            "This is what you DON'T see 🔥",
            "Behind the scenes access 🎬",
            "The Texans way 💪",
        ]
    elif content_type == 'atmosphere' or 'fan' in title_lower or 'game day' in title_lower:
        patterns = [
            "The Swarm showed UP 🐝",
            "Houston fans are DIFFERENT 🔥",
            "This atmosphere is ELECTRIC ⚡",
            "NRG was ROCKING 💪",
        ]
    else:
        patterns = [
            "Houston is BUILT DIFFERENT 🔥",
            "H-Town Made 💪",
            "The Swarm came to PLAY 🐝",
            "You have to see this 😱",
            "This is TEXANS football 🏈",
            "Houston showed UP 🔥",
        ]
    
    # Select pattern based on hash (consistent per video, but varied across videos)
    selected_pattern = patterns[hash_val % len(patterns)]
    
    return {
        'suggestion': selected_pattern,
        'alternatives': [p for p in patterns if p != selected_pattern][:2],
        'confidence': '📊 Performance-based',
        'note': 'Based on title patterns from high-performing Texans content'
    }

def generate_hashtags(video):
    """Generate suggested hashtags for the Shorts clip"""
    base_hashtags = ['#Texans', '#NFL', '#Houston', '#HoustonTexans']
    
    title_lower = video.get('title', '').lower()
    
    # Add player-specific hashtags
    if 'stroud' in title_lower or 'c.j.' in title_lower:
        base_hashtags.extend(['#CJStroud', '#QB1'])
    if 'watt' in title_lower:
        base_hashtags.extend(['#JJWatt', '#99'])
    
    # Add content-type hashtags
    if any(word in title_lower for word in ['highlight', 'play', 'touchdown', 'catch']):
        base_hashtags.append('#NFLHighlights')
    if any(word in title_lower for word in ['interview', 'talks', 'speaks']):
        base_hashtags.append('#NFLInterview')
    
    # Always add Shorts tag
    base_hashtags.append('#Shorts')
    
    return base_hashtags[:8]  # Limit to 8 hashtags

def classify_content_type(video):
    """Classify the content type of a video"""
    title_lower = video.get('title', '').lower()
    description_lower = video.get('description', '').lower()
    text = f"{title_lower} {description_lower}"
    
    if any(word in text for word in ['highlight', 'touchdown', 'interception', 'sack', 'catch']):
        return 'highlight'
    elif any(word in text for word in ['interview', 'talks', 'speaks', 'discusses']):
        return 'interview'
    elif any(word in text for word in ['press conference', 'postgame', 'pregame', 'presser']):
        return 'press_conference'
    elif any(word in text for word in ['behind the scenes', 'inside look', 'exclusive']):
        return 'behind_the_scenes'
    elif any(word in text for word in ['practice', 'training', 'workout']):
        return 'practice'
    elif any(word in text for word in ['fan', 'gameday', 'atmosphere', 'crowd']):
        return 'atmosphere'
    elif any(word in text for word in ['history', 'throwback', 'classic', 'remember']):
        return 'historical'
    else:
        return 'general'

def save_shorts_candidates(candidates, filepath='data/shorts_candidates.json'):
    """Save Shorts candidates to JSON file"""
    import os
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    output = {
        'generated_at': datetime.now(TIMEZONE).isoformat(),
        'total_candidates': len(candidates),
        'candidates': candidates
    }
    
    with open(filepath, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"Shorts candidates saved to {filepath}")

def generate_shorts_report(candidates):
    """Generate a summary report of Shorts candidates"""
    if not candidates:
        return "No Shorts candidates found."
    
    report = []
    report.append(f"# Shorts Candidates Report")
    report.append(f"Generated: {datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M CT')}")
    report.append(f"Total candidates: {len(candidates)}")
    report.append("")
    
    # Group by content type
    by_type = {}
    for c in candidates:
        content_type = c.get('content_type', 'unknown')
        if content_type not in by_type:
            by_type[content_type] = []
        by_type[content_type].append(c)
    
    report.append("## By Content Type")
    for content_type, clips in by_type.items():
        report.append(f"- {content_type}: {len(clips)} clips")
    report.append("")
    
    # Top 10 candidates
    report.append("## Top 10 Candidates")
    for i, c in enumerate(candidates[:10], 1):
        flags_str = " ⚠️" if c.get('flags') else ""
        report.append(f"\n### {i}. {c['video_title'][:50]}...{flags_str}")
        report.append(f"- **Clip:** {c['start_formatted']} → {c['end_formatted']} ({c['clip_duration']}s)")
        report.append(f"- **Priority Score:** {c['priority_score']}")
        report.append(f"- **Retention:** {c['retention_score']}% (video avg: {c['video_avg_retention']}%)")
        report.append(f"- **Link:** {c['timestamped_url']}")
        report.append(f"- **Suggested Title:** {c['suggested_title']['suggestion']}")
        report.append(f"- **Type:** {c['content_type']}")
    
    return '\n'.join(report)

if __name__ == "__main__":
    candidates = identify_shorts_candidates()
    save_shorts_candidates(candidates)
    
    report = generate_shorts_report(candidates)
    print("\n" + report)
