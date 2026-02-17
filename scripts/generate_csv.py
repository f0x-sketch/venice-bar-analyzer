#!/usr/bin/env python3
"""
Venice Bar CSV Generator
One-shot script that generates a CSV file with all bar data
"""

import os
import sys
import csv
import time
import json
from datetime import datetime
from typing import List, Dict, Optional

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from collectors.google_places import GooglePlacesCollector, Bar
from collectors.populartimes_scraper import PopulartimesCollector, CrowdData
from processors.capacity_estimator import CapacityEstimator, CapacityEstimate

# Configuration
API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
RADIUS = int(os.getenv("COLLECTION_RADIUS", "3000"))
MAX_RESULTS = int(os.getenv("MAX_RESULTS", "200"))
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/output")
REQUEST_DELAY = int(os.getenv("REQUEST_DELAY", "2"))


def collect_all_bars() -> List[Dict]:
    """Collect all bars with full data"""
    
    if not API_KEY:
        print("ERROR: GOOGLE_PLACES_API_KEY not set!")
        print("Set it with: export GOOGLE_PLACES_API_KEY=your_key_here")
        sys.exit(1)
    
    print("=" * 70)
    print("VENICE BAR CSV GENERATOR")
    print("=" * 70)
    print(f"\nConfiguration:")
    print(f"  Radius: {RADIUS}m")
    print(f"  Max results: {MAX_RESULTS}")
    print(f"  Output: {OUTPUT_DIR}")
    print()
    
    # Initialize collectors
    google = GooglePlacesCollector(API_KEY)
    populartimes = PopulartimesCollector(API_KEY)
    capacity_est = CapacityEstimator()
    
    # Collect bars
    print(f"[1/3] Collecting bars from Google Places...")
    bars = google.search_bars_in_venice(radius_meters=RADIUS, max_results=MAX_RESULTS)
    print(f"      Found {len(bars)} bars\n")
    
    # Enrich with crowd data and capacity
    enriched_bars = []
    
    for i, bar in enumerate(bars, 1):
        print(f"[{i}/{len(bars)}] Processing: {bar.name}")
        
        try:
            # Get crowd data
            crowd_data = populartimes.get_crowd_data(bar.place_id)
            if crowd_data:
                print(f"      ✓ Crowd data retrieved")
            else:
                print(f"      ⚠ No crowd data available")
            
            time.sleep(REQUEST_DELAY)
            
            # Get detailed place info for reviews
            detailed = google.get_place_details(bar.place_id)
            reviews = detailed.photos if detailed else []  # Actually need reviews, placeholder
            
            # Estimate capacity
            capacity = capacity_est.estimate_capacity(
                place_id=bar.place_id,
                name=bar.name,
                types=bar.types,
                reviews=[],  # Would need review text for full NLP
                price_level=bar.price_level,
                review_count=bar.review_count or 0,
                rating=bar.rating,
                photos_count=len(bar.photos)
            )
            
            print(f"      ✓ Capacity estimated: {capacity.estimated_capacity} ({capacity.confidence})")
            
            # Build enriched record
            record = build_record(bar, crowd_data, capacity)
            enriched_bars.append(record)
            
        except Exception as e:
            print(f"      ✗ Error: {e}")
            # Still add basic record
            record = build_record(bar, None, None)
            enriched_bars.append(record)
        
        print()
    
    return enriched_bars


def build_record(bar: Bar, crowd: Optional[CrowdData], capacity: Optional[CapacityEstimate]) -> Dict:
    """Build a flat dictionary record for CSV"""
    
    # Calculate affluence score
    affluence = 50.0  # Default
    if crowd and crowd.current_popularity is not None:
        affluence = crowd.current_popularity
    elif crowd and crowd.popularity_by_day:
        # Average of today's data
        today = datetime.now().strftime("%A")
        today_data = crowd.popularity_by_day.get(today, [])
        if today_data:
            affluence = sum(today_data) / len(today_data)
    
    # Get popularity string for today
    popularity_today = ""
    if crowd and crowd.popularity_by_day:
        today = datetime.now().strftime("%A")
        today_data = crowd.popularity_by_day.get(today, [])
        popularity_today = "|".join(str(x) for x in today_data) if today_data else ""
    
    # Get peak hours
    peak_hours = ""
    if crowd:
        today = datetime.now().strftime("%A")
        day_data = crowd.popularity_by_day.get(today, []) if crowd.popularity_by_day else []
        if day_data:
            peak_hours_list = [str(h) for h, p in enumerate(day_data) if p > 70]
            peak_hours = ",".join(peak_hours_list)
    
    # Best time to visit
    best_time = ""
    if crowd and crowd.popularity_by_day:
        today = datetime.now().strftime("%A")
        day_data = crowd.popularity_by_day.get(today, [])
        if day_data:
            # Find minimum during reasonable hours (10am-2am)
            min_pop = 100
            best_hour = 0
            for hour in range(10, 26):
                idx = hour % 24
                if idx < len(day_data) and day_data[idx] < min_pop:
                    min_pop = day_data[idx]
                    best_hour = idx
            best_time = f"{best_hour:02d}:00"
    
    # Visit duration
    visit_duration = ""
    if crowd and crowd.time_spent:
        visit_duration = crowd.time_spent
    
    return {
        "place_id": bar.place_id,
        "name": bar.name,
        "address": bar.address,
        "lat": bar.lat,
        "lng": bar.lng,
        "rating": bar.rating,
        "review_count": bar.review_count,
        "price_level": bar.price_level,
        "phone": bar.phone or "",
        "website": bar.website or "",
        "bar_types": ",".join(bar.types) if bar.types else "",
        "opening_hours": json.dumps(bar.opening_hours) if bar.opening_hours else "",
        "estimated_capacity": capacity.estimated_capacity if capacity else "",
        "capacity_confidence": capacity.confidence if capacity else "",
        "capacity_signals": "|".join(capacity.signals_used) if capacity else "",
        "capacity_methodology": capacity.methodology if capacity else "",
        "current_popularity": crowd.current_popularity if crowd else "",
        "popularity_today": popularity_today,
        "peak_hours": peak_hours,
        "best_time_to_visit": best_time,
        "typical_visit_duration": visit_duration,
        "affluence_score": round(affluence, 1),
        "collected_at": datetime.now().isoformat()
    }


def write_csv(bars: List[Dict]):
    """Write bars to CSV file"""
    
    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"venice_bars_{timestamp}.csv"
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    print(f"[2/3] Writing CSV file...")
    
    # Define column order
    columns = [
        "place_id",
        "name",
        "address",
        "lat",
        "lng",
        "rating",
        "review_count",
        "price_level",
        "phone",
        "website",
        "bar_types",
        "opening_hours",
        "estimated_capacity",
        "capacity_confidence",
        "capacity_signals",
        "capacity_methodology",
        "current_popularity",
        "popularity_today",
        "peak_hours",
        "best_time_to_visit",
        "typical_visit_duration",
        "affluence_score",
        "collected_at"
    ]
    
    # Write CSV
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(bars)
    
    print(f"      ✓ CSV written: {filepath}")
    print(f"      ✓ {len(bars)} bars exported\n")
    
    return filepath


def print_summary(bars: List[Dict]):
    """Print summary statistics"""
    
    print(f"[3/3] Summary:")
    print(f"      Total bars: {len(bars)}")
    
    # Calculate averages
    capacities = [b['estimated_capacity'] for b in bars if b['estimated_capacity']]
    affluences = [b['affluence_score'] for b in bars if b['affluence_score']]
    ratings = [b['rating'] for b in bars if b['rating']]
    
    if capacities:
        print(f"      Avg capacity: {sum(capacities)/len(capacities):.0f} people")
    if affluences:
        print(f"      Avg affluence: {sum(affluences)/len(affluences):.1f}/100")
    if ratings:
        print(f"      Avg rating: {sum(ratings)/len(ratings):.2f}")
    
    # Capacity distribution
    print(f"\n      Capacity distribution:")
    small = len([c for c in capacities if c < 30])
    medium = len([c for c in capacities if 30 <= c < 60])
    large = len([c for c in capacities if c >= 60])
    print(f"        Small (<30): {small}")
    print(f"        Medium (30-60): {medium}")
    print(f"        Large (>60): {large}")
    
    # High affluence bars
    busy = len([a for a in affluences if a > 70])
    print(f"\n      Currently busy bars (>70%): {busy}")
    
    print("\n" + "=" * 70)
    print("DONE! Restart container to generate new CSV.")
    print("=" * 70)


def main():
    """Main entry point"""
    
    # Collect data
    bars = collect_all_bars()
    
    if not bars:
        print("ERROR: No bars collected!")
        sys.exit(1)
    
    # Write CSV
    filepath = write_csv(bars)
    
    # Print summary
    print_summary(bars)
    
    print(f"\nOutput file: {filepath}")
    print("\nTo generate a new CSV, restart the container:")
    print("  docker-compose up --force-recreate")
    print("  OR")
    print("  docker run -e GOOGLE_PLACES_API_KEY=$KEY -v $(pwd)/output:/output venice-bar-csv-generator")


if __name__ == "__main__":
    main()
