# 🏈 Houston Texans YouTube Dashboard

An automated YouTube analytics dashboard that tracks KPIs, identifies Shorts clip opportunities, and suggests optimized titles.

## Features

- **📊 KPI Tracking**: Views, watch time, subscribers, engagement, and more
- **⏰ Hourly Updates**: Automated data refresh via GitHub Actions
- **🎬 Shorts Finder**: AI-powered identification of high-retention video segments
- **📈 Performance Comparisons**: FY-over-FY, month-over-month tracking
- **⚠️ Guardrails**: Automatic flagging of concerning metrics
- **🚫 Content Safety**: Auto-blocks restricted content, flags sensitive topics

## Quick Start

### Prerequisites
- GitHub account
- Google Cloud project with YouTube Data API v3 and YouTube Analytics API enabled
- OAuth 2.0 credentials (Desktop app type)

### Setup

1. **Clone this repository**

2. **Add GitHub Secrets** (Settings → Secrets → Actions):
   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_CLIENT_SECRET`
   - `GOOGLE_REFRESH_TOKEN`

3. **Enable GitHub Pages** (Settings → Pages → Source: GitHub Actions)

4. **Trigger first run** (Actions → Update YouTube Dashboard → Run workflow)

## Dashboard Sections

### Overview
- Channel-level KPIs for selected time period
- Top 5 performing videos
- Quick health snapshot

### Top Videos
- Full video performance table
- Sortable by any metric
- Content status flags

### Shorts Candidates
- High-retention segments identified for clipping
- Priority scoring based on retention boost + duration
- Suggested titles and hashtags
- Direct timestamped links

### Traffic Sources
- Breakdown of where views come from
- YouTube Search, Suggested, Browse, External, etc.

### Guardrails
- Videos with concerning metrics
- Low engagement warnings
- Subscriber loss alerts
- Blocked content notifications

## Configuration

Edit `config.py` to customize:

- **Fiscal Year**: Currently set to April 1 - March 31 (FY25 = April 2025 - March 2026)
- **Excluded Content**: Video IDs, blocked keywords, blocked hashtags
- **Flagged Players**: Content requiring extra review
- **KPI Thresholds**: Target values for CTR, engagement, retention
- **Shorts Parameters**: Detection algorithm settings
- **Brand Voice**: Title generation rules

## Content Rules

### Hard Blocks (Auto-filtered)
- ❌ Deshaun Watson content
- ❌ "Show up and show out" phrase
- ❌ #WeAreTexans hashtag
- ❌ Injury-focused content
- ❌ Opponent/player negativity

### Flagged (Requires Review)
- ⚠️ Stefon Diggs content
- 💰 Sponsored/partnership content

### Star Players
- 🌟 **Historical**: J.J. Watt (high priority)
- 🌟 **Current**: C.J. Stroud (high priority)

## API Usage

Daily quota: 10,000 units (free tier)

Estimated usage per refresh:
- Channel stats: 1 unit
- Video list: ~10 units
- Video details: ~10 units
- Analytics queries: ~50 units
- **Total**: ~100 units/hour = ~2,400 units/day

Well within free tier limits.

## File Structure

```
youtube-dashboard/
├── index.html          # Dashboard frontend
├── config.py           # All configuration
├── auth.py             # YouTube API authentication
├── fetch_data.py       # Data fetching scripts
├── shorts_finder.py    # Shorts identification algorithm
├── requirements.txt    # Python dependencies
├── data/
│   ├── dashboard_data.json    # Latest channel data
│   └── shorts_candidates.json # Shorts suggestions
└── .github/
    └── workflows/
        └── update-dashboard.yml  # Automation
```

## Time Filters

- **Past 7 Days**: Rolling week
- **Past Month**: Rolling 30 days
- **Current FY**: April 1, 2025 → March 31, 2026 (FY25)

## Shorts Algorithm

1. **Scope**: Last 90 days + all-time top 50 videos
2. **Detection**: Find segments with retention ≥25% above video average
3. **Duration**: 15-60 seconds, sustained 10+ seconds
4. **Exclusions**: Skip intro (first 10%) and outro (last 5%)
5. **Scoring**: Retention boost × duration bonus
6. **Output**: Top 3 clips per video

## Support

For issues or feature requests, contact the digital team or open a GitHub issue.

---

Built for the Houston Texans Digital Team 🐂
