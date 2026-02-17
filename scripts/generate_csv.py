#!/usr/bin/env python3
"""
Venice Bar CSV Generator
One-shot script: collects bar data, calculates metrics, outputs CSV, exits
"""
import os
import sys
import csv
import time
import json
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from dotenv import load_dotenv
load_dotenv()

from collectors.google_places import GooglePlacesCollector
from collectors.populartimes_scraper import PopulartimesCollector, calculate_affluence_score
from processors.capacity_estimator import CapacityEstimator

# Venice center coordinates
VENICE_LAT = 45.4333
VENICE_LNG = 12.3378

def collect_bars_to_csv():
    """Main function: collect all bars and write to CSV"""
    
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key:
        print("ERROR: GOOGLE_PLACES_API_KEY not set")
        print("Set it as environment variable or in .env file")
        sys.exit(1)
    
    # Configuration
    radius = int(os.getenv("COLLECTION_RADIUS", 3000))
    max_results = int(os.getenv("MAX_RESULTS", 200))
    output_dir = os.getenv("OUTPUT_DIR", "/output")
    request_delay = int(os.getenv("REQUEST_DELAY", 2))
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Timestamp for filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"venice_bars_{timestamp}.csv"
    csv_path = os.path.join(output_dir, csv_filename)
    
    print("=" * 70)
    print("VENICE BAR CSV GENERATOR")
    print("=" * 70)
    print(f"Output: {csv_path}")
    print(f"Radius: {radius}m from Venice center ({VENICE_LAT}, {VENICE_LNG})")
    print(f"Max results: {max_results}")
    print()
    
    # Initialize collectors
    print("Initializing collectors...")
    google_collector = GooglePlacesCollector(api_key)
    crowd_collector = PopulartimesCollector(api_key)
    capacity_estimator = CapacityEstimator()
    
    # Step 1: Collect bars from Google Places
    print(f"\n[1/3] Searching for bars within {radius}m...")
    bars = google_collector.search_bars_in_venice(
        radius_meters=radius,
        max_results=max_results
    )
    print(f"Found {len(bars)} bars")
    
    if not bars:
        print("No bars found!")
        sys.exit(1)
    
    # Step 2: Process each bar and collect crowd data
    print(f"\n[2/3] Collecting crowd data and calculating metrics...")
    
    rows = []
    for i, bar in enumerate(bars, 1):
        print(f"  [{i}/{len(bars)}] {bar.name}")
        
        try:
            # Get crowd data with rate limiting
            time.sleep(request_delay)
            crowd_data = crowd_collector.get_crowd_data(bar.place_id)
            
            # Estimate capacity from available data
            # Note: We don't have full reviews here, so using basic signals
            capacity_estimate = capacity_estimator.estimate_capacity(
                place_id=bar.place_id,
                name=bar.name,
                types=bar.types,
                reviews=[],  # Would need separate API call for full reviews
                price_level=bar.price_level,
                review_count=bar.review_count or 0,
                rating=bar.rating,
                photos_count=len(bar.photos)
            )
            
            # Calculate affluence score
            affluence = calculate_affluence_score(crowd_data) if crowd_data else 50.0
            
            # Get today's popularity data
            today = datetime.now().strftime("%A")
            popularity_today = ""
            peak_hours = ""
            best_time = ""
            visit_duration = ""
            current_pop = ""
            
            if crowd_data:
                current_pop = crowd_data.current_popularity or ""
                
                if crowd_data.popularity_by_day and today in crowd_data.popularity_by_day:
                    popularity_today = ",".join(map(str, crowd_data.popularity_by_day[today]))
                
                peak_hours = ",".join(map(str, crowd_data.get_peak_hours(today))) if hasattr(crowd_data, 'get_peak_hours') else ""
                best_time = crowd_data.get_best_time_to_visit(today) if hasattr(crowd_data, 'get_best_time_to_visit') else ""
                visit_duration = crowd_data.time_spent or ""
            
            # Create CSV row
            row = {
                "place_id": bar.place_id,
                "name": bar.name,
                "address": bar.address,
                "lat": bar.lat,
                "lng": bar.lng,
                "rating": bar.rating if bar.rating else "",
                "review_count": bar.review_count if bar.review_count else "",
                "price_level": bar.price_level if bar.price_level else "",
                "phone": bar.phone if bar.phone else "",
                "website": bar.website if bar.website else "",
                "bar_types": "|".join(bar.types) if bar.types else "",
                "opening_hours": json.dumps(bar.opening_hours) if bar.opening_hours else "",
                "estimated_capacity": capacity_estimate.estimated_capacity,
                "capacity_confidence": capacity_estimate.confidence,
                "capacity_signals": "|".join(capacity_estimate.signals_used),
                "capacity_methodology": capacity_estimate.methodology,
                "current_popularity": current_pop,
                "popularity_today": popularity_today,
                "peak_hours": peak_hours,
                "best_time_to_visit": best_time,
                "typical_visit_duration": visit_duration,
                "affluence_score": round(affluence, 1),
                "collected_at": datetime.now().isoformat()
            }
            rows.append(row)
            
        except Exception as e:
            print(f"    ERROR: {e}")
            # Still add basic info even if crowd data fails
            row = {
                "place_id": bar.place_id,
                "name": bar.name,
                "address": bar.address,
                "lat": bar.lat,
                "lng": bar.lng,
                "rating": bar.rating if bar.rating else "",
                "review_count": bar.review_count if bar.review_count else "",
                "price_level": bar.price_level if bar.price_level else "",
                "phone": bar.phone if bar.phone else "",
                "website": bar.website if bar.website else "",
                "bar_types": "|".join(bar.types) if bar.types else "",
                "opening_hours": json.dumps(bar.opening_hours) if bar.opening_hours else "",
                "estimated_capacity": "",
                "capacity_confidence": "error",
                "capacity_signals": "",
                "capacity_methodology": str(e),
                "current_popularity": "",
                "popularity_today": "",
                "peak_hours": "",
                "best_time_to_visit": "",
                "typical_visit_duration": "",
                "affluence_score": "",
                "collected_at": datetime.now().isoformat()
            }
            rows.append(row)
    
    # Step 3: Write CSV
    print(f"\n[3/3] Writing CSV file...")
    
    fieldnames = [
        "place_id", "name", "address", "lat", "lng",
        "rating", "review_count", "price_level", "phone", "website",
        "bar_types", "opening_hours",
        "estimated_capacity", "capacity_confidence", "capacity_signals", "capacity_methodology",
        "current_popularity", "popularity_today", "peak_hours", "best_time_to_visit", "typical_visit_duration",
        "affluence_score", "collected_at"
    ]
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    # Summary
    print("\n" + "=" * 70)
    print("COMPLETE!")
    print("=" * 70)
    print(f"CSV file: {csv_path}")
    print(f"Total bars: {len(rows)}")
    print(f"With crowd data: {sum(1 for r in rows if r['current_popularity'] != '')}")
    print(f"Avg capacity: {sum(int(r['estimated_capacity']) for r in rows if r['estimated_capacity']) / sum(1 for r in rows if r['estimated_capacity']):.0f}")
    print(f"Avg affluence: {sum(r['affluence_score'] for r in rows if r['affluence_score'] != '') / sum(1 for r in rows if r['affluence_score'] != ''):.1f}")
    print()
    print("Container will now exit. Run again to generate new CSV.")

if __name__ == "__main__":
    collect_bars_to_csv()
