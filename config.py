"""
Houston Texans YouTube Dashboard Configuration
All settings, rules, and constants in one place
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# =============================================================================
# CHANNEL CONFIGURATION
# =============================================================================
CHANNEL_ID = "UCa_FcpOBe8G6VAR18RYS-aA"
CHANNEL_NAME = "Houston Texans"
TIMEZONE = ZoneInfo("America/Chicago")

# =============================================================================
# FISCAL YEAR CONFIGURATION
# Fiscal years are named by starting year: FY25 = April 1, 2025 → March 31, 2026
# =============================================================================
def get_fiscal_year(date=None):
    """Return fiscal year for a given date (defaults to today)"""
    if date is None:
        date = datetime.now(TIMEZONE)
    if date.month >= 4:  # April onwards = current calendar year's FY
        return date.year
    else:  # Jan-March = previous calendar year's FY
        return date.year - 1

def get_fy_date_range(fy_year):
    """Return start and end dates for a fiscal year"""
    start = datetime(fy_year, 4, 1, tzinfo=TIMEZONE)
    end = datetime(fy_year + 1, 3, 31, 23, 59, 59, tzinfo=TIMEZONE)
    return start, end

CURRENT_FY = get_fiscal_year()
FY_START, FY_END = get_fy_date_range(CURRENT_FY)

# =============================================================================
# TIME FILTERS
# =============================================================================
def get_date_ranges():
    """Return all date ranges for dashboard filters"""
    now = datetime.now(TIMEZONE)
    
    return {
        "past_7_days": {
            "start": now - timedelta(days=7),
            "end": now,
            "label": "Past 7 Days"
        },
        "past_month": {
            "start": now - timedelta(days=30),
            "end": now,
            "label": "Past Month"
        },
        "current_fy": {
            "start": FY_START,
            "end": min(now, FY_END),
            "label": f"FY{CURRENT_FY % 100}"
        },
        "previous_fy": {
            "start": get_fy_date_range(CURRENT_FY - 1)[0],
            "end": get_fy_date_range(CURRENT_FY - 1)[1],
            "label": f"FY{(CURRENT_FY - 1) % 100}"
        },
        "same_week_last_year": {
            "start": now - timedelta(days=372),  # ~52 weeks + 7 days
            "end": now - timedelta(days=365),    # ~52 weeks
            "label": "Same Week Last Year"
        }
    }

# =============================================================================
# CONTENT EXCLUSIONS
# =============================================================================
EXCLUDED_VIDEO_IDS = [
    "3prgmt5euW8",  # Watson-related content - hard exclusion
]

BLOCKED_KEYWORDS = [
    "watson",
    "deshaun",
    "show up and show out",
    "showupandshowout",
]

BLOCKED_HASHTAGS = [
    "#WeAreTexans",
    "#wearetexans",
]

# =============================================================================
# FLAGGED CONTENT (requires extra review, not blocked)
# =============================================================================
FLAGGED_PLAYERS = {
    "stefon diggs": {
        "flag_emoji": "⚠️",
        "note": "Verify current roster status before publishing",
        "show_banner": True
    }
}

FLAGGED_CONTENT_TYPES = [
    "sponsored",
    "partnership",
    "ad",
]

# =============================================================================
# BRAND VOICE RULES
# =============================================================================
BRAND_VOICE = {
    "tone": ["energetic", "conversational", "positive"],
    "location_terms": ["Houston", "H-Town"],
    "fan_term": "The Swarm",
    "team_identity": ["Swarming to the ball", "H-Town Made"],
    "allow_clickbait": True,
    "casualty_ok": True,
}

STAR_PLAYERS = {
    "historical": {
        "name": "J.J. Watt",
        "note": "Outperforms all historical content - prioritize"
    },
    "current": {
        "name": "C.J. Stroud", 
        "note": "Outperforms all current content - prioritize"
    }
}

# =============================================================================
# VERIFICATION SOURCES
# =============================================================================
TRUSTED_SOURCES = [
    "HoustonTexans.com",
    "NFL.com",
    "Pro-Football-Reference.com",
    "ESPN.com",
]

# =============================================================================
# KPI THRESHOLDS
# =============================================================================
KPI_THRESHOLDS = {
    "ctr": {
        "poor": 3.0,      # Below this = YouTube stops promoting
        "average": 4.5,
        "good": 6.0,
        "excellent": 10.0,
    },
    "retention_percent": {
        "poor": 30,
        "average": 40,
        "good": 50,
        "excellent": 60,
    },
    "engagement_rate": {
        "poor": 2.0,
        "average": 3.87,
        "good": 6.0,       # Above this = algorithmic boost
        "excellent": 10.0,
    },
    "subscriber_conversion": {
        "poor": 0.5,
        "average": 1.0,
        "good": 2.0,
        "excellent": 5.0,
    },
    "first_30_sec_retention": {
        "poor": 50,
        "average": 65,
        "good": 75,
        "excellent": 85,
    },
    "shorts_swipe_away": {
        "poor": 25,        # >25% in first 3 sec = bad
        "average": 20,
        "good": 15,
        "excellent": 10,
    }
}

# =============================================================================
# SHORTS IDENTIFICATION PARAMETERS
# =============================================================================
SHORTS_CONFIG = {
    "scope": {
        "recent_days": 90,           # Analyze last 90 days
        "top_performers_count": 50,  # Plus all-time top 50
    },
    "detection": {
        "retention_spike_threshold": 0.25,  # 25% above video average
        "min_duration_seconds": 15,
        "max_duration_seconds": 60,
        "sustained_seconds": 10,     # High retention must last 10+ sec
        "skip_intro_percent": 10,    # Don't clip first 10% of video
        "skip_outro_percent": 5,     # Don't clip last 5% of video
    },
    "duration_bonuses": {
        "30-45": 1.2,   # Sweet spot
        "15-30": 1.0,   # Good
        "45-60": 0.9,   # Acceptable
    },
    "clips_per_video": 3,  # Top 3 suggestions per video
}

# =============================================================================
# CONTENT CATEGORIES
# =============================================================================
CONTENT_CATEGORIES = [
    "highlights",
    "interviews",
    "press_conferences",
    "behind_the_scenes",
    "atmosphere",
    "historical",
    "practice",
    "community_events",
    "player_personality",
    "hype",
    "series_content",
]

# =============================================================================
# TITLE PATTERNS BY CATEGORY
# =============================================================================
TITLE_PATTERNS = {
    "highlights": [
        "{player} makes the ENTIRE defense miss 🔥",
        "This {player} {play_type} is UNREAL",
        "{player} said NOT TODAY 🚫",
        "Watch {player} absolutely DOMINATE",
        "How did {player} pull this off?! 😱",
    ],
    "interviews": [
        "{player} on what it means to play for H-Town",
        "{player} gets REAL about {topic}",
        "{player}: \"{quote_preview}...\"",
        "You've never seen {player} like this",
    ],
    "historical": [
        "Prime {player} was a PROBLEM",
        "Remember when {player} did THIS?!",
        "This {player} game was LEGENDARY",
        "{year} {player} was DIFFERENT",
    ],
    "hype": [
        "Houston, we have a SQUAD 🔥",
        "The Swarm is READY 🐝",
        "H-Town Made. Championship Ready.",
        "This team is SPECIAL",
    ],
    "behind_the_scenes": [
        "Ever wonder what happens {location}?",
        "Inside look: {topic}",
        "The side of {player} you don't see",
    ],
}

# =============================================================================
# API CONFIGURATION
# =============================================================================
API_CONFIG = {
    "youtube_data_api": {
        "version": "v3",
        "quota_per_day": 10000,
    },
    "youtube_analytics_api": {
        "version": "v2",
    },
    "rate_limit_delay": 0.1,  # seconds between API calls
}

# =============================================================================
# DASHBOARD DISPLAY
# =============================================================================
DASHBOARD_CONFIG = {
    "refresh_interval_hours": 1,
    "max_videos_displayed": 100,
    "chart_colors": {
        "primary": "#03202F",     # Texans Deep Steel Blue
        "secondary": "#A71930",   # Texans Battle Red
        "accent": "#FFFFFF",      # White
        "warning": "#FFC107",     # Yellow for flags
        "success": "#28A745",     # Green for good metrics
        "danger": "#DC3545",      # Red for poor metrics
    },
    "date_format": "%b %d, %Y",
    "time_format": "%I:%M %p CT",
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
def is_blocked_content(title, description=""):
    """Check if content contains blocked keywords"""
    text = f"{title} {description}".lower()
    
    for keyword in BLOCKED_KEYWORDS:
        if keyword.lower() in text:
            return True, f"Contains blocked keyword: {keyword}"
    
    for hashtag in BLOCKED_HASHTAGS:
        if hashtag.lower() in text:
            return True, f"Contains blocked hashtag: {hashtag}"
    
    return False, None

def is_flagged_content(title, description=""):
    """Check if content needs flagging (not blocked, but needs review)"""
    text = f"{title} {description}".lower()
    flags = []
    
    for player, info in FLAGGED_PLAYERS.items():
        if player.lower() in text:
            flags.append({
                "type": "player",
                "name": player,
                "emoji": info["flag_emoji"],
                "note": info["note"],
                "show_banner": info["show_banner"]
            })
    
    for content_type in FLAGGED_CONTENT_TYPES:
        if content_type.lower() in text:
            flags.append({
                "type": "content",
                "name": content_type,
                "emoji": "💰",
                "note": "Sponsored content - use conservative titling",
                "show_banner": False
            })
    
    return flags

def is_excluded_video(video_id):
    """Check if video is in exclusion list"""
    return video_id in EXCLUDED_VIDEO_IDS

def get_kpi_status(metric_name, value):
    """Return status (poor/average/good/excellent) for a KPI value"""
    if metric_name not in KPI_THRESHOLDS:
        return "unknown"
    
    thresholds = KPI_THRESHOLDS[metric_name]
    
    # Handle inverse metrics (lower is better)
    inverse_metrics = ["shorts_swipe_away"]
    
    if metric_name in inverse_metrics:
        if value <= thresholds["excellent"]:
            return "excellent"
        elif value <= thresholds["good"]:
            return "good"
        elif value <= thresholds["average"]:
            return "average"
        else:
            return "poor"
    else:
        if value >= thresholds["excellent"]:
            return "excellent"
        elif value >= thresholds["good"]:
            return "good"
        elif value >= thresholds["average"]:
            return "average"
        else:
            return "poor"
