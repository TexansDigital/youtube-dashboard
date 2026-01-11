"""
YouTube Title Updater
Executes approved title changes from the title_suggestions.csv file.

Usage:
    python title_updater.py                     # Dry run (preview only)
    python title_updater.py --execute           # Actually update titles
    python title_updater.py --execute --limit 5 # Update first 5 approved
"""

import os
import sys
import json
import csv
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict

from auth import get_authenticated_service

# Paths
DATA_DIR = Path("data")
SUGGESTIONS_CSV = DATA_DIR / "title_suggestions.csv"
CHANGE_LOG = DATA_DIR / "title_change_log.json"


def load_approved_changes(csv_path: Path) -> List[Dict]:
    """Load approved changes from CSV."""
    approved = []
    
    if not csv_path.exists():
        print(f"Error: {csv_path} not found")
        print("Run title_optimizer.py first to generate suggestions")
        sys.exit(1)
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Check if approved
            if row.get('Approved (Y/N)', '').strip().upper() == 'Y':
                # Skip blocked content
                if row.get('Blocked', '').strip().upper() == 'YES':
                    print(f"⚠️  Skipping blocked video: {row['Video ID']}")
                    continue
                
                approved.append({
                    'video_id': row['Video ID'],
                    'current_title': row['Current Title'],
                    'new_title': row['Suggested Title'],
                    'priority': row['Priority'],
                    'notes': row.get('Notes', '')
                })
    
    return approved


def load_change_log() -> List[Dict]:
    """Load existing change log."""
    if CHANGE_LOG.exists():
        with open(CHANGE_LOG, 'r') as f:
            return json.load(f)
    return []


def save_change_log(log: List[Dict]):
    """Save change log."""
    with open(CHANGE_LOG, 'w') as f:
        json.dump(log, f, indent=2, default=str)


def update_video_title(youtube, video_id: str, new_title: str) -> bool:
    """Update a video's title via API."""
    try:
        # Get current video data
        response = youtube.videos().list(
            part='snippet',
            id=video_id
        ).execute()
        
        if not response['items']:
            print(f"  ❌ Video not found: {video_id}")
            return False
        
        video = response['items'][0]
        snippet = video['snippet']
        old_title = snippet['title']
        
        # Update title
        snippet['title'] = new_title
        
        # Execute update
        youtube.videos().update(
            part='snippet',
            body={
                'id': video_id,
                'snippet': snippet
            }
        ).execute()
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Execute approved title changes')
    parser.add_argument('--execute', action='store_true',
                        help='Actually execute changes (without this flag, dry run only)')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit number of updates')
    parser.add_argument('--csv', type=str, default=str(SUGGESTIONS_CSV),
                        help='Path to CSV file with approved changes')
    args = parser.parse_args()
    
    print("=" * 60)
    print("YOUTUBE TITLE UPDATER")
    print("=" * 60)
    print()
    
    # Load approved changes
    csv_path = Path(args.csv)
    approved = load_approved_changes(csv_path)
    
    if not approved:
        print("No approved changes found.")
        print(f"Open {csv_path} and mark rows with 'Y' in the 'Approved (Y/N)' column")
        return
    
    print(f"Found {len(approved)} approved changes")
    
    if args.limit:
        approved = approved[:args.limit]
        print(f"Limited to first {args.limit}")
    
    print()
    
    # Dry run or execute
    if not args.execute:
        print("🔍 DRY RUN MODE (add --execute to apply changes)")
        print("-" * 60)
        for i, change in enumerate(approved, 1):
            print(f"\n{i}. {change['video_id']} [{change['priority']}]")
            print(f"   FROM: {change['current_title'][:60]}...")
            print(f"   TO:   {change['new_title'][:60]}...")
        print("\n" + "-" * 60)
        print(f"Total: {len(approved)} changes ready")
        print("\nRun with --execute to apply these changes")
        return
    
    # Execute changes
    print("🚀 EXECUTING CHANGES")
    print("-" * 60)
    
    youtube = get_authenticated_service()
    change_log = load_change_log()
    
    success_count = 0
    fail_count = 0
    
    for i, change in enumerate(approved, 1):
        video_id = change['video_id']
        new_title = change['new_title']
        
        print(f"\n[{i}/{len(approved)}] {video_id}")
        print(f"  → {new_title[:55]}...")
        
        if update_video_title(youtube, video_id, new_title):
            print("  ✅ Updated")
            success_count += 1
            
            # Log the change
            change_log.append({
                'video_id': video_id,
                'old_title': change['current_title'],
                'new_title': new_title,
                'updated_at': datetime.now().isoformat(),
                'priority': change['priority'],
                'notes': change['notes']
            })
        else:
            fail_count += 1
    
    # Save log
    save_change_log(change_log)
    
    # Summary
    print("\n" + "=" * 60)
    print("COMPLETE")
    print("=" * 60)
    print(f"✅ Successful: {success_count}")
    print(f"❌ Failed: {fail_count}")
    print(f"\nChange log saved to: {CHANGE_LOG}")
    print("\nMonitor performance in YouTube Studio over the next 30 days")


if __name__ == "__main__":
    main()
