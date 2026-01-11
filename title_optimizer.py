"""
YouTube Title Optimizer
Integrates with the Houston Texans YouTube Dashboard to identify and optimize
underperforming video titles for videos published 3+ years ago.

This module uses the existing auth.py for authentication and outputs to data/
for dashboard integration.

Usage:
    python title_optimizer.py                    # Default: 3+ year old videos
    python title_optimizer.py --min-age-years 2  # Custom age threshold
    python title_optimizer.py --include-all      # All videos
"""

import os
import sys
import json
import re
import csv
import time
import argparse
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

# Import from existing project
from auth import get_authenticated_service
from config import (
    BLOCKED_VIDEO_IDS,
    BLOCKED_KEYWORDS,
    FLAGGED_PLAYERS,
    STAR_PLAYERS,
)

# =============================================================================
# CONFIGURATION
# =============================================================================

# Title optimization settings
TITLE_CONFIG = {
    "max_length": 60,
    "high_ctr_threshold": 0.10,    # 10% - don't suggest changes
    "low_ctr_threshold": 0.05,     # 5% - prioritize for optimization
    "min_views_for_priority": 10000,
    
    # Series branding
    "series_names": [
        "Texans Radio", 
        "Texans All-Access", 
        "Puntos Extra", 
        "En la Jugada", 
        "The 53", 
        "Iron Sharpens Iron",
        "Coffee With Coach"
    ],
    
    # Spanish content indicators
    "spanish_indicators": ["puntos extra", "en la jugada", "español", "spanish"],
    
    # Coach naming preferences
    "coach_preferred": "Head Coach DeMeco Ryans",
    "coach_alternates": ["DeMeco Ryans", "Coach Ryans", "DeMeco"],
    
    # Power words that drive CTR
    "power_words": {
        "action": ["Dominates", "Crushes", "Shuts Down", "Explodes", "Powers Through", "STUNS"],
        "curiosity": ["Reveals", "Inside Look", "Behind the Scenes", "Exclusive", "Must-See"],
        "emotion": ["Incredible", "Clutch", "Epic", "Game-Changing", "Historic", "Emotional"]
    },
    
    # Words to NEVER use (brand safety)
    "forbidden_words": ["CHOKES", "EMBARRASSED", "FAILS", "DESTROYED", "HUMILIATED", "IDIOT", "STUPID"],
}

# Output paths
DATA_DIR = Path("data")
OUTPUT_FILE = DATA_DIR / "title_suggestions.json"
CSV_OUTPUT = DATA_DIR / "title_suggestions.csv"

# API settings
BATCH_SIZE = 50
API_DELAY = 0.1


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class VideoData:
    """Video data from YouTube API."""
    video_id: str
    title: str
    description: str
    published_at: datetime
    duration_seconds: int
    view_count: int
    like_count: int
    comment_count: int
    tags: List[str]
    thumbnail_url: str
    ctr: float = 0.0
    impressions: int = 0
    avg_view_duration: float = 0.0
    
    @property
    def age_days(self) -> int:
        return (datetime.now() - self.published_at).days
    
    @property
    def age_years(self) -> float:
        return self.age_days / 365
    
    @property
    def is_short(self) -> bool:
        return self.duration_seconds <= 60
    
    @property
    def youtube_url(self) -> str:
        return f"https://youtube.com/watch?v={self.video_id}"


@dataclass
class TitleSuggestion:
    """A title optimization suggestion."""
    video_id: str
    youtube_url: str
    publish_date: str
    current_title: str
    suggested_title: str
    thumbnail_concept: str
    rationale: str
    priority: str
    confidence: str
    content_type: str
    current_ctr: float
    current_views: int
    potential_impact: str
    language: str
    is_blocked: bool = False
    requires_review: bool = False


# =============================================================================
# VIDEO FETCHER
# =============================================================================

class VideoFetcher:
    """Fetches all videos from YouTube API."""
    
    def __init__(self, youtube_service):
        self.youtube = youtube_service
        self.channel_id = None
        
    def get_channel_id(self) -> str:
        """Get the authenticated channel's ID."""
        if self.channel_id:
            return self.channel_id
            
        response = self.youtube.channels().list(
            part='id,snippet',
            mine=True
        ).execute()
        
        if response['items']:
            self.channel_id = response['items'][0]['id']
            channel_name = response['items'][0]['snippet']['title']
            print(f"✓ Channel: {channel_name} ({self.channel_id})")
            return self.channel_id
        raise ValueError("Could not get channel ID")
    
    def get_all_videos(self) -> List[VideoData]:
        """Fetch ALL videos from the channel with pagination."""
        channel_id = self.get_channel_id()
        videos = []
        
        # Get uploads playlist
        channel_response = self.youtube.channels().list(
            part='contentDetails',
            id=channel_id
        ).execute()
        
        uploads_playlist = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        print(f"Fetching from playlist: {uploads_playlist}")
        
        # Paginate through all videos
        next_page_token = None
        
        while True:
            playlist_response = self.youtube.playlistItems().list(
                part='snippet,contentDetails',
                playlistId=uploads_playlist,
                maxResults=BATCH_SIZE,
                pageToken=next_page_token
            ).execute()
            
            video_ids = [item['contentDetails']['videoId'] for item in playlist_response['items']]
            
            if video_ids:
                batch_videos = self._get_video_details(video_ids)
                videos.extend(batch_videos)
                print(f"  Fetched {len(videos)} videos...", end='\r')
            
            next_page_token = playlist_response.get('nextPageToken')
            if not next_page_token:
                break
            
            time.sleep(API_DELAY)
        
        print(f"\n✓ Total videos: {len(videos)}")
        return videos
    
    def _get_video_details(self, video_ids: List[str]) -> List[VideoData]:
        """Get detailed info for a batch of videos."""
        videos = []
        
        response = self.youtube.videos().list(
            part='snippet,statistics,contentDetails',
            id=','.join(video_ids)
        ).execute()
        
        for item in response.get('items', []):
            video = self._parse_video(item)
            if video:
                videos.append(video)
        
        return videos
    
    def _parse_video(self, item: Dict) -> Optional[VideoData]:
        """Parse API response into VideoData."""
        try:
            # Parse duration
            duration_str = item['contentDetails']['duration']
            duration_seconds = self._parse_duration(duration_str)
            
            # Parse date
            pub_date = datetime.fromisoformat(
                item['snippet']['publishedAt'].replace('Z', '+00:00')
            ).replace(tzinfo=None)
            
            # Get best thumbnail
            thumbnails = item['snippet'].get('thumbnails', {})
            thumbnail_url = (
                thumbnails.get('maxres', {}).get('url') or
                thumbnails.get('high', {}).get('url') or
                thumbnails.get('default', {}).get('url', '')
            )
            
            return VideoData(
                video_id=item['id'],
                title=item['snippet']['title'],
                description=item['snippet'].get('description', ''),
                published_at=pub_date,
                duration_seconds=duration_seconds,
                view_count=int(item['statistics'].get('viewCount', 0)),
                like_count=int(item['statistics'].get('likeCount', 0)),
                comment_count=int(item['statistics'].get('commentCount', 0)),
                tags=item['snippet'].get('tags', []),
                thumbnail_url=thumbnail_url
            )
        except Exception as e:
            print(f"Error parsing video: {e}")
            return None
    
    def _parse_duration(self, duration_str: str) -> int:
        """Parse ISO 8601 duration to seconds."""
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
        if not match:
            return 0
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        return hours * 3600 + minutes * 60 + seconds


# =============================================================================
# TITLE OPTIMIZER
# =============================================================================

class TitleOptimizer:
    """Analyzes videos and generates optimization suggestions."""
    
    def __init__(self):
        self.config = TITLE_CONFIG
        
    def analyze_video(self, video: VideoData) -> Dict[str, Any]:
        """Analyze a video's title and content."""
        title = video.title
        title_lower = title.lower()
        
        return {
            "content_type": self._detect_content_type(video),
            "is_spanish": self._is_spanish(video),
            "has_series_tag": any(s.lower() in title_lower for s in self.config["series_names"]),
            "has_emoji": bool(re.search(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF]', title)),
            "has_power_word": self._has_power_word(title),
            "has_date_reference": bool(re.search(r'\d{1,2}[/-]\d{1,2}', title)),
            "title_length": len(title),
            "truncation_risk": len(title) > 60,
            "is_short_video": video.is_short,
            "is_blocked": self._is_blocked(video),
            "requires_review": self._requires_review(video),
        }
    
    def _detect_content_type(self, video: VideoData) -> str:
        """Detect content type from title."""
        title_lower = video.title.lower()
        
        patterns = [
            ('silent_drill', ['silent drill', 'drill platoon', 'drill team']),
            ('press_conference', ['press conference', 'presser', 'addresses media', 'at the podium']),
            ('micd_up', ["mic'd up", 'micd up', 'wired']),
            ('highlights', ['highlights', 'every play', 'best plays']),
            ('game_recap', ['recap', 'full game', 'game winning']),
            ('interview', ['interview', 'talks', '1-on-1']),
            ('behind_scenes', ['behind', 'exclusive', 'inside', 'locker room']),
            ('reaction', ['react', 'reaction', 'reacts']),
            ('draft', ['draft', 'draft class']),
        ]
        
        for content_type, keywords in patterns:
            if any(kw in title_lower for kw in keywords):
                return content_type
        
        return 'short' if video.is_short else 'other'
    
    def _is_spanish(self, video: VideoData) -> bool:
        """Check if video is Spanish content."""
        combined = (video.title + ' ' + video.description).lower()
        return any(ind in combined for ind in self.config["spanish_indicators"])
    
    def _has_power_word(self, title: str) -> bool:
        """Check for engagement power words."""
        title_lower = title.lower()
        for words in self.config["power_words"].values():
            if any(w.lower() in title_lower for w in words):
                return True
        return False
    
    def _is_blocked(self, video: VideoData) -> bool:
        """Check if video should be blocked based on config.py rules."""
        # Check blocked video IDs
        if video.video_id in BLOCKED_VIDEO_IDS:
            return True
        
        # Check blocked keywords
        combined = (video.title + ' ' + video.description).lower()
        for keyword in BLOCKED_KEYWORDS:
            if keyword.lower() in combined:
                return True
        
        return False
    
    def _requires_review(self, video: VideoData) -> bool:
        """Check if video requires manual review."""
        combined = (video.title + ' ' + video.description).lower()
        
        # Check flagged players
        for player in FLAGGED_PLAYERS:
            if player.lower() in combined:
                return True
        
        return False
    
    def generate_suggestion(self, video: VideoData, analysis: Dict) -> Optional[TitleSuggestion]:
        """Generate optimization suggestion for a video."""
        
        # Skip shorts
        if analysis["is_short_video"]:
            return None
        
        # Skip blocked content
        if analysis["is_blocked"]:
            return TitleSuggestion(
                video_id=video.video_id,
                youtube_url=video.youtube_url,
                publish_date=video.published_at.strftime('%Y-%m-%d'),
                current_title=video.title,
                suggested_title="[BLOCKED - DO NOT OPTIMIZE]",
                thumbnail_concept="",
                rationale="Content blocked per brand safety rules",
                priority="blocked",
                confidence="n/a",
                content_type=analysis["content_type"],
                current_ctr=video.ctr,
                current_views=video.view_count,
                potential_impact="N/A",
                language="es" if analysis["is_spanish"] else "en",
                is_blocked=True,
                requires_review=False
            )
        
        # Generate suggestion
        suggested_title, thumbnail, rationale = self._create_suggestion(
            video, analysis["content_type"], analysis["is_spanish"], analysis
        )
        
        # Skip if no change
        if suggested_title == video.title:
            return None
        
        priority = self._determine_priority(video, analysis)
        confidence = "needs_verification" if self._needs_verification(suggested_title) else "pattern_based"
        impact = self._estimate_impact(video)
        
        return TitleSuggestion(
            video_id=video.video_id,
            youtube_url=video.youtube_url,
            publish_date=video.published_at.strftime('%Y-%m-%d'),
            current_title=video.title,
            suggested_title=suggested_title,
            thumbnail_concept=thumbnail,
            rationale=rationale,
            priority=priority,
            confidence=confidence,
            content_type=analysis["content_type"],
            current_ctr=video.ctr,
            current_views=video.view_count,
            potential_impact=impact,
            language="es" if analysis["is_spanish"] else "en",
            is_blocked=False,
            requires_review=analysis["requires_review"]
        )
    
    def _create_suggestion(self, video: VideoData, content_type: str, 
                          is_spanish: bool, analysis: Dict) -> Tuple[str, str, str]:
        """Create title suggestion based on content type."""
        
        title = video.title
        suggested = title
        thumbnail = ""
        rationale_parts = []
        
        # Content-specific optimization
        if content_type == 'silent_drill':
            suggested, thumbnail, rationale_parts = self._optimize_silent_drill(video)
        elif content_type == 'micd_up':
            suggested, thumbnail, rationale_parts = self._optimize_micd_up(video)
        elif content_type == 'press_conference':
            suggested, thumbnail, rationale_parts = self._optimize_press_conference(video, is_spanish)
        elif content_type == 'behind_scenes':
            suggested, thumbnail, rationale_parts = self._optimize_behind_scenes(video, analysis)
        elif content_type == 'interview':
            suggested, thumbnail, rationale_parts = self._optimize_interview(video, is_spanish, analysis)
        else:
            suggested, thumbnail, rationale_parts = self._optimize_general(video, analysis)
        
        # Ensure under 60 characters
        if len(suggested) > 60:
            suggested = self._smart_truncate(suggested)
            rationale_parts.append("Shortened for display")
        
        rationale = "; ".join(rationale_parts) if rationale_parts else "Pattern-based optimization"
        return suggested, thumbnail, rationale
    
    def _optimize_silent_drill(self, video: VideoData) -> Tuple[str, str, List[str]]:
        """Optimize Silent Drill content - HIGH VALUE."""
        title_lower = video.title.lower()
        rationale = []
        
        if 'marine' in title_lower and 'corps' in title_lower:
            unit = "U.S. Marine Corps Silent Drill Platoon"
        elif 'naval academy' in title_lower or 'jolly rogers' in title_lower:
            unit = "Navy's 'Jolly Rogers' Silent Drill Team"
        elif 'marine' in title_lower:
            unit = "U.S. Marines Silent Drill Platoon"
        else:
            unit = "Silent Drill Platoon"
        
        suggested = f"{unit} | Precision That Will Give You Chills"
        thumbnail = "Close-up of synchronized rifle movement, dramatic lighting"
        rationale.append("Removed game reference for evergreen appeal")
        rationale.append("Added emotional hook")
        
        return suggested, thumbnail, rationale
    
    def _optimize_micd_up(self, video: VideoData) -> Tuple[str, str, List[str]]:
        """Optimize Mic'd Up content."""
        title = video.title
        rationale = []
        
        if "watt" in title.lower() and "t.j." in title.lower():
            suggested = "J.J. Watt vs T.J. Watt: Brothers Mic'd Up | Texans vs Steelers"
            thumbnail = "Split screen of both Watts, 'BROTHERS' text"
            rationale.append("Story hook: brothers competing")
        elif "simone biles" in title.lower():
            suggested = "Simone Biles Reacts to Husband's Biggest NFL Moment | Mic'd Up"
            thumbnail = "Simone's reaction, Jonathan Owens in action"
            rationale.append("Celebrity angle + emotional moment")
        else:
            suggested = title
            if "| mic'd up" not in title.lower():
                suggested = re.sub(r"\s*\|\s*$", "", title) + " | Mic'd Up"
                rationale.append("Added Mic'd Up branding")
            thumbnail = "Player in action, audio wave overlay"
        
        return suggested, thumbnail, rationale
    
    def _optimize_press_conference(self, video: VideoData, is_spanish: bool) -> Tuple[str, str, List[str]]:
        """Optimize press conference content."""
        title = video.title
        rationale = []
        
        # Remove dates
        suggested = re.sub(r'\s*\d{1,2}[/-]\d{1,2}[/-]?\d{0,4}\s*', ' ', title)
        suggested = re.sub(r'\s*\(\d{1,2}/\d{1,2}\)\s*', ' ', suggested)
        
        if suggested != title:
            rationale.append("Removed date for evergreen appeal")
        
        # Add branding if missing
        if 'texans' not in suggested.lower():
            suggested = suggested.strip() + " | Houston Texans"
            rationale.append("Added team branding")
        
        thumbnail = "Speaker at podium, Texans branding, topic text overlay"
        return suggested.strip(), thumbnail, rationale
    
    def _optimize_behind_scenes(self, video: VideoData, analysis: Dict) -> Tuple[str, str, List[str]]:
        """Optimize behind-the-scenes content."""
        title = video.title
        rationale = []
        suggested = title
        
        if 'exclusive' not in title.lower() and 'inside' not in title.lower():
            if title.lower().startswith('behind'):
                suggested = title.replace('Behind', 'Inside', 1).replace('behind', 'Inside', 1)
                rationale.append("Changed to 'Inside' for intrigue")
        
        if not analysis["has_series_tag"]:
            suggested = suggested.strip() + " | Texans All-Access"
            rationale.append("Added series branding")
        
        thumbnail = "Candid moment, 'EXCLUSIVE' text"
        return suggested, thumbnail, rationale
    
    def _optimize_interview(self, video: VideoData, is_spanish: bool, analysis: Dict) -> Tuple[str, str, List[str]]:
        """Optimize interview content."""
        title = video.title
        rationale = []
        
        suggested = re.sub(r'\s*\d{1,2}[/-]\d{1,2}[/-]?\d{0,4}\s*', ' ', title)
        if suggested != title:
            rationale.append("Removed date reference")
        
        if not analysis["has_series_tag"]:
            series = "Puntos Extra" if is_spanish else "Texans Radio"
            suggested = suggested.strip() + f" | {series}"
            rationale.append("Added series branding")
        
        thumbnail = "Player headshot, quote bubble or topic text"
        return suggested.strip(), thumbnail, rationale
    
    def _optimize_general(self, video: VideoData, analysis: Dict) -> Tuple[str, str, List[str]]:
        """General optimization."""
        title = video.title
        rationale = []
        
        # Remove dates
        suggested = re.sub(r'\s*\d{1,2}[/-]\d{1,2}[/-]?\d{0,4}\s*', ' ', title)
        if suggested != title:
            rationale.append("Removed date reference")
        
        # Add branding for longer content
        if video.duration_seconds > 180 and 'texans' not in suggested.lower():
            suggested = suggested.strip() + " | Houston Texans"
            rationale.append("Added team branding")
        
        thumbnail = "Clear subject, Texans branding"
        return suggested.strip(), thumbnail, rationale
    
    def _smart_truncate(self, title: str, max_length: int = 60) -> str:
        """Truncate preserving pipe separator."""
        if len(title) <= max_length:
            return title
        
        if '|' in title:
            parts = title.rsplit('|', 1)
            main = parts[0].strip()
            suffix = parts[1].strip()
            available = max_length - len(suffix) - 3
            if available > 20:
                return main[:available].strip() + " | " + suffix
        
        return title[:max_length-3].strip() + "..."
    
    def _determine_priority(self, video: VideoData, analysis: Dict) -> str:
        """Determine optimization priority."""
        if video.view_count > 100000 and analysis["content_type"] == 'silent_drill':
            return "high"
        if video.view_count > self.config["min_views_for_priority"]:
            return "high"
        if analysis["content_type"] in ['micd_up', 'behind_scenes']:
            return "medium"
        return "low"
    
    def _needs_verification(self, title: str) -> bool:
        """Check if title has claims needing verification."""
        if re.search(r'\d+\s*(yards?|td|touchdowns?|ints?|sacks?)', title, re.I):
            return True
        if re.search(r'\d+-\d+', title):
            return True
        return False
    
    def _estimate_impact(self, video: VideoData) -> str:
        """Estimate potential impact."""
        if video.view_count > 1000000:
            return "VERY HIGH - Millions of views"
        elif video.view_count > 100000:
            return "HIGH - 100K+ views"
        elif video.view_count > 10000:
            return "MEDIUM - 10K+ views"
        return "LOW - Under 10K views"


# =============================================================================
# OUTPUT GENERATION
# =============================================================================

def save_suggestions(suggestions: List[TitleSuggestion], videos: List[VideoData], min_age: float):
    """Save suggestions to JSON and CSV."""
    DATA_DIR.mkdir(exist_ok=True)
    
    # Prepare data
    output_data = {
        "generated_at": datetime.now().isoformat(),
        "total_videos_analyzed": len(videos),
        "min_age_years": min_age,
        "suggestions_count": len(suggestions),
        "priority_breakdown": {
            "high": len([s for s in suggestions if s.priority == "high"]),
            "medium": len([s for s in suggestions if s.priority == "medium"]),
            "low": len([s for s in suggestions if s.priority == "low"]),
            "blocked": len([s for s in suggestions if s.priority == "blocked"]),
        },
        "suggestions": [asdict(s) for s in suggestions]
    }
    
    # Save JSON
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, default=str)
    print(f"✓ Saved {OUTPUT_FILE}")
    
    # Save CSV
    with open(CSV_OUTPUT, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Priority', 'Video ID', 'URL', 'Publish Date', 'Content Type',
            'Views', 'Impact', 'Current Title', 'Suggested Title',
            'Thumbnail Concept', 'Rationale', 'Confidence', 'Language',
            'Blocked', 'Needs Review', 'Approved (Y/N)', 'Notes'
        ])
        for s in suggestions:
            writer.writerow([
                s.priority.upper(), s.video_id, s.youtube_url, s.publish_date,
                s.content_type, s.current_views, s.potential_impact,
                s.current_title, s.suggested_title, s.thumbnail_concept,
                s.rationale, s.confidence, s.language,
                'YES' if s.is_blocked else '', 'YES' if s.requires_review else '',
                '', ''
            ])
    print(f"✓ Saved {CSV_OUTPUT}")


def print_summary(suggestions: List[TitleSuggestion], videos: List[VideoData], min_age: float):
    """Print summary to console."""
    high = [s for s in suggestions if s.priority == "high"]
    medium = [s for s in suggestions if s.priority == "medium"]
    blocked = [s for s in suggestions if s.is_blocked]
    review = [s for s in suggestions if s.requires_review]
    
    print("\n" + "=" * 60)
    print("TITLE OPTIMIZATION SUMMARY")
    print("=" * 60)
    print(f"Videos analyzed: {len(videos)}")
    print(f"Age filter: {min_age}+ years")
    print(f"Suggestions generated: {len(suggestions)}")
    print()
    print(f"🔴 HIGH PRIORITY:   {len(high)}")
    print(f"🟡 MEDIUM PRIORITY: {len(medium)}")
    print(f"🟢 LOW PRIORITY:    {len(suggestions) - len(high) - len(medium) - len(blocked)}")
    print(f"⛔ BLOCKED:         {len(blocked)}")
    print(f"⚠️  NEEDS REVIEW:    {len(review)}")
    print()
    
    if high:
        print("TOP OPPORTUNITIES:")
        print("-" * 60)
        for s in high[:5]:
            print(f"\n• {s.video_id} ({s.current_views:,} views)")
            print(f"  Current:   {s.current_title[:55]}...")
            print(f"  Suggested: {s.suggested_title[:55]}...")
    
    print("\n" + "=" * 60)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='YouTube Title Optimizer')
    parser.add_argument('--min-age-years', type=float, default=3.0,
                        help='Minimum video age in years (default: 3)')
    parser.add_argument('--include-all', action='store_true',
                        help='Include all videos regardless of age')
    args = parser.parse_args()
    
    print("=" * 60)
    print("HOUSTON TEXANS TITLE OPTIMIZER")
    print("=" * 60)
    print()
    
    # Authenticate using existing auth.py
    print("Authenticating...")
    youtube = get_authenticated_service()
    print("✓ Authenticated")
    print()
    
    # Fetch all videos
    print("Fetching videos...")
    fetcher = VideoFetcher(youtube)
    all_videos = fetcher.get_all_videos()
    
    # Filter by age
    if args.include_all:
        filtered = all_videos
        print(f"Processing all {len(filtered)} videos")
    else:
        min_days = int(args.min_age_years * 365)
        filtered = [v for v in all_videos if v.age_days >= min_days]
        print(f"Filtered to {len(filtered)} videos ({args.min_age_years}+ years old)")
    
    if not filtered:
        print("No videos match criteria")
        return
    
    # Generate suggestions
    print("\nAnalyzing titles...")
    optimizer = TitleOptimizer()
    suggestions = []
    
    for video in filtered:
        analysis = optimizer.analyze_video(video)
        suggestion = optimizer.generate_suggestion(video, analysis)
        if suggestion:
            suggestions.append(suggestion)
    
    # Sort by priority
    priority_order = {'high': 0, 'medium': 1, 'low': 2, 'blocked': 3}
    suggestions.sort(key=lambda x: (priority_order.get(x.priority, 99), -x.current_views))
    
    # Output
    save_suggestions(suggestions, filtered, args.min_age_years)
    print_summary(suggestions, filtered, args.min_age_years)
    
    print("\nDone! Review data/title_suggestions.csv to approve changes.")


if __name__ == "__main__":
    main()
