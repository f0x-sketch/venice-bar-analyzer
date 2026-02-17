# Populartimes Scraper
"""
Scrapes crowd/popularity data from Google Maps using populartimes library
"""

import time
import json
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import populartimes

@dataclass
class CrowdData:
    place_id: str
    name: str
    current_popularity: Optional[int]  # 0-100, live busy-ness
    popularity_by_day: Dict[str, List[int]]  # Hourly data for each day
    time_spent: Optional[str]  # "45 min" typical visit duration
    wait_time: Optional[int]  # Minutes wait time if applicable
    
    def get_current_busy_percent(self) -> Optional[int]:
        """Get current busy percentage (0-100)"""
        return self.current_popularity
    
    def get_peak_hours(self, day: str = None) -> List[int]:
        """Get peak hours (0-23) for a given day"""
        if day is None:
            day = datetime.now().strftime("%A")  # Current day name
        
        day_data = self.popularity_by_day.get(day, [])
        if not day_data:
            return []
        
        # Find hours with >70% popularity
        return [hour for hour, pop in enumerate(day_data) if pop > 70]
    
    def get_best_time_to_visit(self, day: str = None) -> Optional[str]:
        """Find the least busy time slot"""
        if day is None:
            day = datetime.now().strftime("%A")
        
        day_data = self.popularity_by_day.get(day, [])
        if not day_data:
            return None
        
        # Find minimum popularity during opening hours (assume 10am-2am)
        min_pop = 100
        best_hour = 0
        for hour in range(10, 26):  # 10am to 2am next day
            idx = hour % 24
            if idx < len(day_data) and day_data[idx] < min_pop:
                min_pop = day_data[idx]
                best_hour = idx
        
        return f"{best_hour:02d}:00"


class PopulartimesCollector:
    """
    Collects crowd/popularity data using populartimes library
    
    Note: This scrapes Google Maps public data. Respect rate limits.
    """
    
    def __init__(self, api_key: str = None):
        """
        Initialize collector
        
        Args:
            api_key: Google Places API key (optional, helps with some queries)
        """
        self.api_key = api_key
        self.request_delay = 2  # Seconds between requests
        
    def get_crowd_data(
        self, 
        place_id: str, 
        max_retries: int = 3
    ) -> Optional[CrowdData]:
        """
        Get crowd data for a specific venue
        
        Args:
            place_id: Google Place ID
            max_retries: Number of retry attempts
            
        Returns:
            CrowdData object or None if not available
        """
        for attempt in range(max_retries):
            try:
                # populartimes.get returns detailed crowd data
                data = populartimes.get_id(self.api_key, place_id)
                
                if not data:
                    return None
                
                return self._parse_crowd_data(place_id, data)
                
            except Exception as e:
                print(f"Attempt {attempt + 1} failed for {place_id}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(5)  # Wait longer between retries
                else:
                    return None
            
            time.sleep(self.request_delay)
    
    def search_venues_with_crowd(
        self,
        query: str = "bars",
        lat: float = 45.4333,
        lng: float = 12.3378,
        radius: int = 3000
    ) -> List[CrowdData]:
        """
        Search for venues and get crowd data
        
        Args:
            query: Search term (e.g., "bars", "pubs")
            lat: Latitude
            lng: Longitude  
            radius: Search radius in meters
            
        Returns:
            List of CrowdData objects
        """
        try:
            # populartimes.get searches and returns data with crowd info
            results = populartimes.get(
                self.api_key,
                [query],
                (lat - 0.05, lng - 0.05),  # SW corner
                (lat + 0.05, lng + 0.05),  # NE corner
                n_threads=4,  # Parallel requests
                radius=radius
            )
            
            crowd_data_list = []
            for venue_data in results:
                place_id = venue_data.get("place_id", "")
                crowd_data = self._parse_crowd_data(place_id, venue_data)
                if crowd_data:
                    crowd_data_list.append(crowd_data)
                
                time.sleep(self.request_delay)
            
            return crowd_data_list
            
        except Exception as e:
            print(f"Error searching venues: {e}")
            return []
    
    def _parse_crowd_data(
        self, 
        place_id: str, 
        data: Dict
    ) -> Optional[CrowdData]:
        """Parse populartimes response into CrowdData object"""
        try:
            # Extract popularity by day
            popularity_by_day = {}
            
            # Current popularity (live data)
            current_pop = data.get("current_popularity")
            
            # Time spent
            time_spent = None
            time_spent_data = data.get("time_spent")
            if time_spent_data and len(time_spent_data) >= 2:
                time_spent = f"{time_spent_data[0]}-{time_spent_data[1]} min"
            
            # Parse popularity by day
            populartimes_data = data.get("populartimes", [])
            for day_data in populartimes_data:
                day_name = day_data.get("name", "")
                hours = day_data.get("data", [])
                if day_name and hours:
                    popularity_by_day[day_name] = hours
            
            # If no populartimes data, try to infer from current_popularity
            if not popularity_by_day and current_pop is not None:
                # Create dummy data based on current popularity
                today = datetime.now().strftime("%A")
                popularity_by_day[today] = [current_pop] * 24
            
            return CrowdData(
                place_id=place_id,
                name=data.get("name", "Unknown"),
                current_popularity=current_pop,
                popularity_by_day=popularity_by_day,
                time_spent=time_spent,
                wait_time=data.get("wait_time")
            )
            
        except Exception as e:
            print(f"Error parsing crowd data for {place_id}: {e}")
            return None
    
    def batch_update_crowd_data(
        self, 
        place_ids: List[str],
        db_session = None
    ) -> Dict[str, CrowdData]:
        """
        Update crowd data for multiple venues
        
        Args:
            place_ids: List of Google Place IDs
            db_session: Optional database session to save results
            
        Returns:
            Dictionary mapping place_id to CrowdData
        """
        results = {}
        
        for i, place_id in enumerate(place_ids):
            print(f"Updating {i+1}/{len(place_ids)}: {place_id}")
            
            crowd_data = self.get_crowd_data(place_id)
            if crowd_data:
                results[place_id] = crowd_data
                
                # Save to database if provided
                if db_session:
                    self._save_to_db(crowd_data, db_session)
            
            # Respect rate limits
            time.sleep(self.request_delay)
        
        return results
    
    def _save_to_db(self, crowd_data: CrowdData, db_session):
        """Save crowd data to database"""
        # Implementation depends on your database models
        # This is a placeholder
        pass


# Helper functions
def estimate_visit_duration(time_spent_str: str) -> Optional[int]:
    """
    Parse time spent string into minutes
    
    Args:
        time_spent_str: Like "45 min" or "30-60 min"
        
    Returns:
        Average minutes or None
    """
    if not time_spent_str:
        return None
    
    try:
        # Handle ranges like "30-60 min"
        if "-" in time_spent_str:
            parts = time_spent_str.replace(" min", "").split("-")
            return (int(parts[0]) + int(parts[1])) // 2
        
        # Handle single values like "45 min"
        return int(time_spent_str.replace(" min", ""))
    except:
        return None


def calculate_affluence_score(crowd_data: CrowdData) -> float:
    """
    Calculate overall affluence score (0-100)
    
    Factors:
    - Current popularity (40%)
    - Average peak popularity (30%)
    - Review/tip velocity proxy (30%)
    """
    if not crowd_data:
        return 0.0
    
    # Current popularity (if available)
    current = crowd_data.current_popularity or 50
    
    # Calculate average peak popularity across all days
    peak_scores = []
    for day, hours in crowd_data.popularity_by_day.items():
        if hours:
            peak_scores.append(max(hours))
    
    avg_peak = sum(peak_scores) / len(peak_scores) if peak_scores else 50
    
    # Weighted score
    score = (current * 0.4) + (avg_peak * 0.6)
    
    return min(100, max(0, score))


if __name__ == "__main__":
    # Test
    from dotenv import load_dotenv
    import os
    
    load_dotenv()
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    
    collector = PopulartimesCollector(api_key)
    
    # Test with a known Venice bar (replace with actual place_id)
    test_place_id = "ChIJrTLjx9CxfkcR0l9xRPmxhAE"  # Example
    
    print(f"Fetching crowd data for {test_place_id}...")
    crowd_data = collector.get_crowd_data(test_place_id)
    
    if crowd_data:
        print(f"\nName: {crowd_data.name}")
        print(f"Current busy: {crowd_data.current_popularity}%")
        print(f"Typical stay: {crowd_data.time_spent}")
        print(f"Peak hours today: {crowd_data.get_peak_hours()}")
        print(f"Best time to visit: {crowd_data.get_best_time_to_visit()}")
        print(f"Affluence score: {calculate_affluence_score(crowd_data):.1f}/100")
    else:
        print("No crowd data available")
