#!/usr/bin/env python3
"""
One-time collection of all bars in Venice
Run this to populate the database initially
"""

import os
import sys
import time
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

from collectors.google_places import GooglePlacesCollector
from collectors.populartimes_scraper import PopulartimesCollector
from processors.capacity_estimator import CapacityEstimator
from database.models import Bar, CrowdData, Base

def main():
    print("=" * 60)
    print("Venice Bar Collection")
    print("=" * 60)
    
    load_dotenv()
    
    # Get API keys
    google_api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not google_api_key:
        print("\n❌ Error: GOOGLE_PLACES_API_KEY not set in .env")
        sys.exit(1)
    
    # Database setup
    database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/venice_bars")
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    # Initialize collectors
    print("\n🔄 Initializing collectors...")
    places_collector = GooglePlacesCollector(google_api_key)
    crowd_collector = PopulartimesCollector(google_api_key)
    capacity_estimator = CapacityEstimator()
    
    # Search for bars
    print("\n🔍 Searching for bars in Venice...")
    print("   This may take a few minutes due to API rate limits...")
    
    try:
        bars = places_collector.search_bars_in_venice(
            radius_meters=5000,
            max_results=200
        )
        print(f"\n✅ Found {len(bars)} bars")
        
    except Exception as e:
        print(f"\n❌ Error searching bars: {e}")
        sys.exit(1)
    
    # Process each bar
    print("\n📊 Processing bars...")
    added_count = 0
    error_count = 0
    
    for i, bar_data in enumerate(bars):
        print(f"\n[{i+1}/{len(bars)}] {bar_data.name}")
        
        try:
            # Check if already exists
            existing = db.query(Bar).filter(Bar.id == bar_data.place_id).first()
            if existing:
                print(f"   ⚠️  Already exists, skipping")
                continue
            
            # Get crowd data
            print(f"   🔄 Fetching crowd data...")
            crowd_data = crowd_collector.get_crowd_data(bar_data.place_id)
            time.sleep(2)  # Respect rate limits
            
            # Estimate capacity
            print(f"   🔄 Estimating capacity...")
            capacity_result = capacity_estimator.estimate_capacity(
                place_id=bar_data.place_id,
                name=bar_data.name,
                types=bar_data.types,
                reviews=[],  # Would need to fetch reviews separately
                price_level=bar_data.price_level,
                review_count=bar_data.review_count or 0,
                rating=bar_data.rating,
                photos_count=len(bar_data.photos)
            )
            
            # Create database records
            bar = Bar(
                id=bar_data.place_id,
                name=bar_data.name,
                address=bar_data.address,
                lat=bar_data.lat,
                lng=bar_data.lng,
                rating=bar_data.rating,
                review_count=bar_data.review_count,
                price_level=bar_data.price_level,
                phone=bar_data.phone,
                website=bar_data.website,
                opening_hours=bar_data.opening_hours,
                types=bar_data.types,
                estimated_capacity=capacity_result.estimated_capacity,
                capacity_confidence=capacity_result.confidence,
                capacity_methodology=capacity_result.methodology
            )
            
            if crowd_data:
                from processors.capacity_estimator import estimate_visit_duration
                
                crowd = CrowdData(
                    bar_id=bar_data.place_id,
                    current_popularity=crowd_data.current_popularity,
                    current_popularity_timestamp=datetime.utcnow(),
                    popularity_by_day=crowd_data.popularity_by_day,
                    time_spent_minutes=estimate_visit_duration(crowd_data.time_spent),
                    wait_time_minutes=crowd_data.wait_time,
                    peak_hours=crowd_data.get_peak_hours(),
                    best_time_to_visit=crowd_data.get_best_time_to_visit()
                )
                bar.crowd_data = crowd
            
            db.add(bar)
            db.commit()
            added_count += 1
            
            print(f"   ✅ Added (capacity: {capacity_result.estimated_capacity}, "
                  f"confidence: {capacity_result.confidence})")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            error_count += 1
            db.rollback()
            continue
    
    print("\n" + "=" * 60)
    print("Collection Complete!")
    print("=" * 60)
    print(f"\n✅ Added: {added_count} bars")
    print(f"❌ Errors: {error_count} bars")
    print(f"📊 Total in database: {db.query(Bar).count()} bars")
    
    db.close()

if __name__ == "__main__":
    main()
