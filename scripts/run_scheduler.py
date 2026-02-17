#!/usr/bin/env python3
"""
Scheduled data updates (runs continuously)
"""
import os
import sys
import time
import schedule
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from dotenv import load_dotenv
load_dotenv()

from collectors.populartimes_scraper import PopulartimesCollector
from database.models import init_database, Bar, CrowdData

def update_crowd_data():
    """Update crowd data for all bars"""
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Updating crowd data...")
    
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key:
        print("Error: GOOGLE_PLACES_API_KEY not set")
        return
    
    collector = PopulartimesCollector(api_key)
    db = init_database()
    
    # Get all bars
    bars = db.query(Bar).all()
    
    updated = 0
    errors = 0
    
    for bar in bars:
        try:
            crowd_data = collector.get_crowd_data(bar.id)
            
            if crowd_data:
                # Find existing crowd record
                crowd = db.query(CrowdData).filter(CrowdData.bar_id == bar.id).first()
                
                if crowd:
                    # Update
                    crowd.current_popularity = crowd_data.current_popularity
                    crowd.current_popularity_timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                    crowd.popularity_by_day = crowd_data.popularity_by_day
                    crowd.time_spent_minutes = crowd_data.time_spent_minutes if hasattr(crowd_data, 'time_spent_minutes') else None
                else:
                    # Create new
                    crowd = CrowdData(
                        bar_id=bar.id,
                        current_popularity=crowd_data.current_popularity,
                        popularity_by_day=crowd_data.popularity_by_day
                    )
                    db.add(crowd)
                
                db.commit()
                updated += 1
            
            # Rate limiting
            time.sleep(2)
            
        except Exception as e:
            print(f"Error updating {bar.name}: {e}")
            errors += 1
            db.rollback()
    
    print(f"  Updated: {updated}, Errors: {errors}")

def main():
    print("Venice Bar Analyzer - Scheduled Data Updates")
    print("=" * 60)
    
    # Schedule jobs
    interval = int(os.getenv("UPDATE_INTERVAL_MINUTES", 15))
    
    print(f"Crowd data updates every {interval} minutes")
    print()
    
    schedule.every(interval).minutes.do(update_crowd_data)
    
    # Run immediately on start
    update_crowd_data()
    
    # Keep running
    print("Scheduler running. Press Ctrl+C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nScheduler stopped.")
