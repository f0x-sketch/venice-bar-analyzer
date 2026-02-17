#!/usr/bin/env python3
"""
One-time collection of all bars in Venice
"""
import os
import sys
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from dotenv import load_dotenv
load_dotenv()

from collectors.google_places import GooglePlacesCollector
from collectors.populartimes_scraper import PopulartimesCollector
from processors.capacity_estimator import CapacityEstimator
from database.models import init_database, Bar, CrowdData

def collect_bars():
    """Collect all bars from Google Places and save to database"""
    
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key:
        print("Error: GOOGLE_PLACES_API_KEY not set")
        print("Please set it in .env file")
        return
    
    print("=" * 60)
    print("VENICE BAR COLLECTION")
    print("=" * 60)
    
    # Initialize
    google_collector = GooglePlacesCollector(api_key)
    crowd_collector = PopulartimesCollector(api_key)
    capacity_estimator = CapacityEstimator()
    db = init_database()
    
    # Venice center coordinates
    lat = float(os.getenv("VENICE_CENTER_LAT", 45.4333))
    lng = float(os.getenv("VENICE_CENTER_LNG", 12.3378))
    radius = int(os.getenv("COLLECTION_RADIUS_METERS", 3000))
    
    print(f"\nSearching for bars within {radius}m of Venice center...")
    print(f"Coordinates: {lat}, {lng}")
    print()
    
    # Collect from Google Places
    bars = google_collector.search_bars_in_venice(
        radius_meters=radius,
        max_results=200
    )
    
    print(f"Found {len(bars)} bars\n")
    
    # Save to database
    saved = 0
    errors = 0
    
    for i, bar_data in enumerate(bars, 1):
        print(f"[{i}/{len(bars)}] Processing: {bar_data.name}")
        
        try:
            # Check if already exists
            existing = db.query(Bar).filter(Bar.id == bar_data.place_id).first()
            if existing:
                print(f"  → Already exists, skipping")
                continue
            
            # Get crowd data (rate limited)
            print(f"  → Fetching crowd data...")
            crowd_data = crowd_collector.get_crowd_data(bar_data.place_id)
            time.sleep(2)  # Rate limiting
            
            # Estimate capacity
            print(f"  → Estimating capacity...")
            capacity_estimate = capacity_estimator.estimate_capacity(
                place_id=bar_data.place_id,
                name=bar_data.name,
                types=bar_data.types,
                reviews=[],  # Would need to fetch full reviews for NLP
                price_level=bar_data.price_level,
                review_count=bar_data.review_count or 0,
                rating=bar_data.rating,
                photos_count=len(bar_data.photos)
            )
            
            # Create Bar record
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
                estimated_capacity=capacity_estimate.estimated_capacity,
                capacity_confidence=capacity_estimate.confidence,
                capacity_methodology=capacity_estimate.methodology
            )
            
            db.add(bar)
            
            # Create CrowdData record if available
            if crowd_data:
                crowd = CrowdData(
                    bar_id=bar_data.place_id,
                    current_popularity=crowd_data.current_popularity,
                    popularity_by_day=crowd_data.popularity_by_day,
                    time_spent_minutes=crowd_data.time_spent and int(crowd_data.time_spent.replace(' min', '').split('-')[0]) or None,
                    wait_time_minutes=crowd_data.wait_time,
                    peak_hours=crowd_data.get_peak_hours() if hasattr(crowd_data, 'get_peak_hours') else [],
                    best_time_to_visit=crowd_data.get_best_time_to_visit() if hasattr(crowd_data, 'get_best_time_to_visit') else None
                )
                db.add(crowd)
            
            db.commit()
            saved += 1
            print(f"  ✓ Saved (capacity: {capacity_estimate.estimated_capacity}, confidence: {capacity_estimate.confidence})")
            
        except Exception as e:
            errors += 1
            print(f"  ✗ Error: {e}")
            db.rollback()
        
        print()
    
    print("=" * 60)
    print("COLLECTION COMPLETE")
    print("=" * 60)
    print(f"Total processed: {len(bars)}")
    print(f"New bars saved: {saved}")
    print(f"Errors: {errors}")
    print()
    print("Next steps:")
    print("  1. Start API server: docker-compose up api")
    print("  2. Or: uvicorn src.api.main:app --reload")

if __name__ == "__main__":
    collect_bars()
