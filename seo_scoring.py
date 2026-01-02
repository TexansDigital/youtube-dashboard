"""
SEO Scoring System
Dynamically learns which keywords correlate with high performance
and scores videos based on SEO optimization.
"""

import json
import re
import os
from datetime import datetime
from collections import Counter
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("America/Chicago")

# File paths
KEYWORDS_FILE = 'data/seo_keywords.json'
SEO_SCORES_FILE = 'data/seo_scores.json'

# Default boost keywords (Texans-specific, NFL-relevant)
DEFAULT_BOOST_KEYWORDS = [
    # Team identity
    'texans', 'houston', 'h-town', 'htx', 'nrg', 'swarm',
    # Current players (high performers)
    'stroud', 'c.j.', 'cj', 'dell', 'tank', 'collins', 'nico', 
    'pitre', 'anderson', 'mixon',
    # Coaches
    'ryans', 'demeco', 'bobby slowik',
    # Action words (engagement drivers)
    'highlights', 'touchdown', 'td', 'interception', 'int', 'sack',
    'catch', 'run', 'pass', 'throw', 'play', 'win', 'victory',
    # Emotion drivers
    'incredible', 'amazing', 'insane', 'unbelievable', 'crazy',
    'best', 'top', 'epic', 'clutch', 'dominant',
    # Content types that perform well
    "mic'd up", 'micd', 'locker room', 'postgame', 'reaction',
    'behind the scenes', 'exclusive', 'interview',
    # Historical (evergreen)
    'watt', 'j.j.', 'jj', 'hopkins', 'watson-free',  # Note: watson itself is blocked
    # NFL/Football general
    'nfl', 'football', 'playoff', 'playoffs', 'championship',
    'game day', 'gameday', 'matchup',
]

# Default avoid keywords (low engagement or problematic)
DEFAULT_AVOID_KEYWORDS = [
    # Blocked content (from config)
    'watson', 'deshaun',
    # Low-engagement patterns
    'press conference full',  # Full pressers underperform clips
    'full game',  # Too long, low retention
    'compilation',  # Often low engagement
    # Negative framing
    'loss', 'lost', 'defeat', 'injured', 'injury', 'out for season',
    # Generic/weak
    'video', 'clip', 'watch', 'check out', 'new',
]

# Optimal ranges for scoring
OPTIMAL_TITLE_LENGTH = (40, 70)  # characters
OPTIMAL_DESCRIPTION_LENGTH = (200, 500)  # characters
OPTIMAL_TAG_COUNT = (5, 15)
OPTIMAL_HASHTAG_COUNT = (3, 5)


def load_keywords():
    """Load keyword lists from file, or create defaults"""
    if os.path.exists(KEYWORDS_FILE):
        try:
            with open(KEYWORDS_FILE, 'r') as f:
                data = json.load(f)
                return data.get('boost', DEFAULT_BOOST_KEYWORDS), data.get('avoid', DEFAULT_AVOID_KEYWORDS)
        except:
            pass
    
    return DEFAULT_BOOST_KEYWORDS.copy(), DEFAULT_AVOID_KEYWORDS.copy()


def save_keywords(boost_keywords, avoid_keywords, analysis_stats=None):
    """Save keyword lists to file"""
    os.makedirs(os.path.dirname(KEYWORDS_FILE), exist_ok=True)
    
    data = {
        'boost': boost_keywords,
        'avoid': avoid_keywords,
        'last_updated': datetime.now(TIMEZONE).isoformat(),
        'analysis_stats': analysis_stats or {}
    }
    
    with open(KEYWORDS_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def extract_keywords(text):
    """Extract individual words and common phrases from text"""
    if not text:
        return []
    
    text = text.lower()
    
    # Remove special characters but keep apostrophes for contractions
    text = re.sub(r"[^\w\s'-]", ' ', text)
    
    # Split into words
    words = text.split()
    
    # Filter out very short words and common stop words
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
                  'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
                  'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
                  'should', 'may', 'might', 'must', 'this', 'that', 'these', 'those',
                  'i', 'you', 'he', 'she', 'it', 'we', 'they', 'what', 'which', 'who',
                  'when', 'where', 'why', 'how', 'all', 'each', 'every', 'both', 'few',
                  'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only',
                  'own', 'same', 'so', 'than', 'too', 'very', 'just', 'also', 'now'}
    
    keywords = [w for w in words if len(w) > 2 and w not in stop_words]
    
    # Also extract 2-word phrases
    for i in range(len(words) - 1):
        phrase = f"{words[i]} {words[i+1]}"
        if words[i] not in stop_words or words[i+1] not in stop_words:
            keywords.append(phrase)
    
    return keywords


def calculate_seo_score(video, boost_keywords=None, avoid_keywords=None):
    """
    Calculate SEO score for a video (0-100).
    
    Scoring breakdown:
    - Boost keywords present: up to +40 points
    - Avoid keywords absent: up to +20 points  
    - Title optimization: up to +20 points
    - Description optimization: up to +10 points
    - Hashtags present: up to +10 points
    """
    if boost_keywords is None or avoid_keywords is None:
        boost_keywords, avoid_keywords = load_keywords()
    
    score = 0
    breakdown = {}
    suggestions = []
    
    title = (video.get('title') or '').lower()
    description = (video.get('description') or '').lower()
    full_text = f"{title} {description}"
    
    # --- Boost Keywords (up to 40 points) ---
    boost_found = []
    for keyword in boost_keywords:
        if keyword.lower() in full_text:
            boost_found.append(keyword)
    
    boost_score = min(40, len(boost_found) * 5)  # 5 points per keyword, max 40
    score += boost_score
    breakdown['boost_keywords'] = {
        'score': boost_score,
        'found': boost_found[:8],  # Limit display
        'count': len(boost_found)
    }
    
    if len(boost_found) < 3:
        suggestions.append(f"Add more high-performing keywords like: {', '.join(boost_keywords[:5])}")
    
    # --- Avoid Keywords (up to 20 points) ---
    avoid_found = []
    for keyword in avoid_keywords:
        if keyword.lower() in full_text:
            avoid_found.append(keyword)
    
    avoid_penalty = len(avoid_found) * 10  # -10 per bad keyword
    avoid_score = max(0, 20 - avoid_penalty)
    score += avoid_score
    breakdown['avoid_keywords'] = {
        'score': avoid_score,
        'found': avoid_found,
        'penalty': avoid_penalty
    }
    
    if avoid_found:
        suggestions.append(f"Consider removing: {', '.join(avoid_found)}")
    
    # --- Title Optimization (up to 20 points) ---
    title_length = len(video.get('title') or '')
    title_score = 0
    
    if OPTIMAL_TITLE_LENGTH[0] <= title_length <= OPTIMAL_TITLE_LENGTH[1]:
        title_score = 20
    elif title_length < OPTIMAL_TITLE_LENGTH[0]:
        title_score = 10
        suggestions.append(f"Title is short ({title_length} chars). Aim for {OPTIMAL_TITLE_LENGTH[0]}-{OPTIMAL_TITLE_LENGTH[1]} chars.")
    else:
        title_score = 10
        suggestions.append(f"Title is long ({title_length} chars). Consider shortening to under {OPTIMAL_TITLE_LENGTH[1]} chars.")
    
    # Bonus for emoji (engagement driver)
    if any(ord(c) > 127 for c in (video.get('title') or '')):
        title_score = min(20, title_score + 5)
    
    score += title_score
    breakdown['title'] = {
        'score': title_score,
        'length': title_length,
        'optimal_range': OPTIMAL_TITLE_LENGTH
    }
    
    # --- Description Optimization (up to 10 points) ---
    desc_length = len(video.get('description') or '')
    desc_score = 0
    
    if desc_length >= OPTIMAL_DESCRIPTION_LENGTH[0]:
        desc_score = 10
    elif desc_length >= 100:
        desc_score = 5
        suggestions.append("Add more description text (aim for 200+ characters)")
    else:
        desc_score = 0
        suggestions.append("Description is too short. Add context, links, and keywords.")
    
    score += desc_score
    breakdown['description'] = {
        'score': desc_score,
        'length': desc_length
    }
    
    # --- Hashtags (up to 10 points) ---
    hashtag_count = len(re.findall(r'#\w+', video.get('description') or ''))
    hashtag_count += len(re.findall(r'#\w+', video.get('title') or ''))
    
    if OPTIMAL_HASHTAG_COUNT[0] <= hashtag_count <= OPTIMAL_HASHTAG_COUNT[1]:
        hashtag_score = 10
    elif hashtag_count > 0:
        hashtag_score = 5
    else:
        hashtag_score = 0
        suggestions.append("Add 3-5 relevant hashtags (#Texans #NFL #Houston)")
    
    score += hashtag_score
    breakdown['hashtags'] = {
        'score': hashtag_score,
        'count': hashtag_count
    }
    
    return {
        'total_score': min(100, score),
        'grade': get_grade(score),
        'breakdown': breakdown,
        'suggestions': suggestions[:3],  # Top 3 suggestions
        'boost_keywords_found': boost_found,
        'avoid_keywords_found': avoid_found,
    }


def get_grade(score):
    """Convert numeric score to letter grade"""
    if score >= 90:
        return 'A+'
    elif score >= 80:
        return 'A'
    elif score >= 70:
        return 'B'
    elif score >= 60:
        return 'C'
    elif score >= 50:
        return 'D'
    else:
        return 'F'


def analyze_and_update_keywords(videos):
    """
    Analyze video performance to update keyword lists.
    Called monthly to refine the SEO scoring algorithm.
    
    Algorithm:
    1. Split videos into top 20% (winners) and bottom 20% (losers) by engagement
    2. Extract keywords from each group
    3. Find keywords that appear more in winners → boost
    4. Find keywords that appear more in losers → avoid
    5. Update keyword lists
    """
    if not videos or len(videos) < 10:
        print("Not enough videos to analyze keywords")
        return
    
    # Sort by engagement rate (or composite score)
    sorted_videos = sorted(videos, key=lambda v: v.get('engagement_rate', 0), reverse=True)
    
    # Get top 20% and bottom 20%
    cutoff = max(5, len(sorted_videos) // 5)
    winners = sorted_videos[:cutoff]
    losers = sorted_videos[-cutoff:]
    
    # Extract keywords from each group
    winner_keywords = Counter()
    loser_keywords = Counter()
    
    for video in winners:
        text = f"{video.get('title', '')} {video.get('description', '')}"
        for kw in extract_keywords(text):
            winner_keywords[kw] += 1
    
    for video in losers:
        text = f"{video.get('title', '')} {video.get('description', '')}"
        for kw in extract_keywords(text):
            loser_keywords[kw] += 1
    
    # Find keywords that differentiate winners from losers
    boost_keywords, avoid_keywords = load_keywords()
    
    new_boost_candidates = []
    new_avoid_candidates = []
    
    # Keywords appearing 2x+ more in winners than losers
    for kw, count in winner_keywords.items():
        loser_count = loser_keywords.get(kw, 0)
        if count >= 2 and count >= loser_count * 2:
            if kw not in boost_keywords and kw not in avoid_keywords:
                new_boost_candidates.append((kw, count, loser_count))
    
    # Keywords appearing 2x+ more in losers than winners
    for kw, count in loser_keywords.items():
        winner_count = winner_keywords.get(kw, 0)
        if count >= 2 and count >= winner_count * 2:
            if kw not in avoid_keywords and kw not in boost_keywords:
                new_avoid_candidates.append((kw, count, winner_count))
    
    # Add top candidates to lists
    new_boost_candidates.sort(key=lambda x: x[1], reverse=True)
    new_avoid_candidates.sort(key=lambda x: x[1], reverse=True)
    
    added_boost = []
    added_avoid = []
    
    for kw, win_count, lose_count in new_boost_candidates[:10]:
        if kw not in boost_keywords:
            boost_keywords.append(kw)
            added_boost.append(kw)
    
    for kw, lose_count, win_count in new_avoid_candidates[:5]:
        if kw not in avoid_keywords:
            avoid_keywords.append(kw)
            added_avoid.append(kw)
    
    # Save updated keywords
    analysis_stats = {
        'videos_analyzed': len(videos),
        'winners_analyzed': len(winners),
        'losers_analyzed': len(losers),
        'new_boost_keywords': added_boost,
        'new_avoid_keywords': added_avoid,
        'analysis_date': datetime.now(TIMEZONE).isoformat()
    }
    
    save_keywords(boost_keywords, avoid_keywords, analysis_stats)
    
    print(f"Keyword analysis complete:")
    print(f"  - Analyzed {len(videos)} videos")
    print(f"  - Added {len(added_boost)} boost keywords: {added_boost}")
    print(f"  - Added {len(added_avoid)} avoid keywords: {added_avoid}")
    
    return analysis_stats


def score_all_videos(videos):
    """Calculate SEO scores for all videos"""
    boost_keywords, avoid_keywords = load_keywords()
    
    scored_videos = []
    for video in videos:
        seo = calculate_seo_score(video, boost_keywords, avoid_keywords)
        video['seo_score'] = seo
        scored_videos.append(video)
    
    # Save scores to file
    os.makedirs(os.path.dirname(SEO_SCORES_FILE), exist_ok=True)
    
    scores_summary = {
        'generated_at': datetime.now(TIMEZONE).isoformat(),
        'total_videos': len(scored_videos),
        'average_score': sum(v['seo_score']['total_score'] for v in scored_videos) / len(scored_videos) if scored_videos else 0,
        'grade_distribution': {},
        'top_suggestions': get_top_suggestions(scored_videos),
    }
    
    # Count grades
    for video in scored_videos:
        grade = video['seo_score']['grade']
        scores_summary['grade_distribution'][grade] = scores_summary['grade_distribution'].get(grade, 0) + 1
    
    with open(SEO_SCORES_FILE, 'w') as f:
        json.dump(scores_summary, f, indent=2)
    
    return scored_videos


def get_top_suggestions(videos):
    """Get most common SEO suggestions across all videos"""
    all_suggestions = Counter()
    
    for video in videos:
        for suggestion in video.get('seo_score', {}).get('suggestions', []):
            # Normalize suggestion to group similar ones
            if 'hashtag' in suggestion.lower():
                all_suggestions['Add hashtags'] += 1
            elif 'description' in suggestion.lower():
                all_suggestions['Improve descriptions'] += 1
            elif 'title' in suggestion.lower():
                all_suggestions['Optimize title length'] += 1
            elif 'keyword' in suggestion.lower():
                all_suggestions['Add more keywords'] += 1
            else:
                all_suggestions[suggestion] += 1
    
    return dict(all_suggestions.most_common(5))


def get_keyword_report():
    """Generate a report on current keyword performance"""
    boost_keywords, avoid_keywords = load_keywords()
    
    # Load analysis stats if available
    stats = {}
    if os.path.exists(KEYWORDS_FILE):
        try:
            with open(KEYWORDS_FILE, 'r') as f:
                data = json.load(f)
                stats = data.get('analysis_stats', {})
        except:
            pass
    
    return {
        'boost_keywords': boost_keywords,
        'avoid_keywords': avoid_keywords,
        'total_boost': len(boost_keywords),
        'total_avoid': len(avoid_keywords),
        'last_analysis': stats.get('analysis_date'),
        'recent_additions': {
            'boost': stats.get('new_boost_keywords', []),
            'avoid': stats.get('new_avoid_keywords', [])
        }
    }


if __name__ == "__main__":
    # Test with sample video
    test_video = {
        'title': 'C.J. Stroud INCREDIBLE 4th Quarter Comeback vs Ravens 🔥',
        'description': 'Watch C.J. Stroud lead the Houston Texans to an amazing comeback win! #Texans #NFL #Houston'
    }
    
    score = calculate_seo_score(test_video)
    print(f"SEO Score: {score['total_score']}/100 ({score['grade']})")
    print(f"Breakdown: {json.dumps(score['breakdown'], indent=2)}")
    print(f"Suggestions: {score['suggestions']}")
