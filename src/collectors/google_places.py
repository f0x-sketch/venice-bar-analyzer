# Google Places API Collector
"""
Collects bar data from Google Places API (New)
"""

import os
import time
import requests
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import json

@dataclass
class Bar:
    place_id: str
    name: str
    address: str
    lat: float
    lng: float
    rating: Optional[float] = None
    review_count: Optional[int] = None
    price_level: Optional[int] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    opening_hours: Optional[Dict] = None
    photos: List[str] = None
    types: List[str] = None
    
    def __post_init__(self):
        if self.photos is None:
            self.photos = []
        if self.types is None:
            self.types = []


class GooglePlacesCollector:
    """Collects bar data from Google Places API"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://places.googleapis.com/v1"
        self.session = requests.Session()
        
    def search_bars_in_venice(
        self, 
        radius_meters: int = 5000,
        max_results: int = 1000
    ) -> List[Bar]:
        """
        Search for all bars in Venice area
        
        Venice center: 45.4333, 12.3378
        """
        # Venice coordinates
        venice_lat = 45.4333
        venice_lng = 12.3378
        
        bars = []
        next_page_token = None
        
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,"
                               "places.location,places.rating,places.userRatingCount,"
                               "places.priceLevel,places.nationalPhoneNumber,"
                               "places.websiteUri,places.regularOpeningHours,"
                               "places.photos,places.types,nextPageToken"
        }
        
        while len(bars) < max_results:
            payload = {
                "locationRestriction": {
                    "circle": {
                        "center": {
                            "latitude": venice_lat,
                            "longitude": venice_lng
                        },
                        "radius": radius_meters
                    }
                },
                "includedTypes": ["bar", "wine_bar", "pub", "night_club"],
                "excludedTypes": ["cafe", "restaurant"],
                "maxResultCount": 20  # API limit per request
            }
            
            if next_page_token:
                payload["pageToken"] = next_page_token
            
            response = self.session.post(
                f"{self.base_url}/places:searchNearby",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            
            for place in data.get("places", []):
                bar = self._parse_place(place)
                if bar:
                    bars.append(bar)
            
            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break
                
            # Respect rate limits
            time.sleep(2)
        
        return bars[:max_results]
    
    def get_place_details(self, place_id: str) -> Optional[Bar]:
        """Get detailed information about a specific place"""
        headers = {
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "id,displayName,formattedAddress,location,rating,"
                               "userRatingCount,priceLevel,nationalPhoneNumber,"
                               "websiteUri,regularOpeningHours,photos,types,reviews"
        }
        
        response = self.session.get(
            f"{self.base_url}/places/{place_id}",
            headers=headers
        )
        
        if response.status_code == 200:
            return self._parse_place(response.json())
        return None
    
    def _parse_place(self, place_data: Dict) -> Optional[Bar]:
        """Parse Google Places API response into Bar object"""
        try:
            location = place_data.get("location", {})
            
            # Get photo references
            photos = []
            for photo in place_data.get("photos", [])[:5]:  # Limit to 5 photos
                photo_name = photo.get("name", "")
                if photo_name:
                    photos.append(photo_name)
            
            return Bar(
                place_id=place_data.get("id", ""),
                name=place_data.get("displayName", {}).get("text", "Unknown"),
                address=place_data.get("formattedAddress", ""),
                lat=location.get("latitude", 0),
                lng=location.get("longitude", 0),
                rating=place_data.get("rating"),
                review_count=place_data.get("userRatingCount"),
                price_level=self._parse_price_level(place_data.get("priceLevel")),
                phone=place_data.get("nationalPhoneNumber"),
                website=place_data.get("websiteUri"),
                opening_hours=place_data.get("regularOpeningHours"),
                photos=photos,
                types=place_data.get("types", [])
            )
        except Exception as e:
            print(f"Error parsing place: {e}")
            return None
    
    def _parse_price_level(self, price_level_str: Optional[str]) -> Optional[int]:
        """Convert price level string to integer"""
        if not price_level_str:
            return None
        
        mapping = {
            "PRICE_LEVEL_FREE": 0,
            "PRICE_LEVEL_INEXPENSIVE": 1,
            "PRICE_LEVEL_MODERATE": 2,
            "PRICE_LEVEL_EXPENSIVE": 3,
            "PRICE_LEVEL_VERY_EXPENSIVE": 4
        }
        return mapping.get(price_level_str)
    
    def get_photo_url(self, photo_name: str, max_width: int = 400) -> str:
        """Get URL for a photo"""
        return f"{self.base_url}/{photo_name}/media?maxWidthPx={max_width}&key={self.api_key}"


# Text search for more targeted results
def search_bars_by_text(query: str = "bars in Venice Italy", api_key: str = None) -> List[Bar]:
    """Text-based search for bars"""
    if not api_key:
        api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    
    collector = GooglePlacesCollector(api_key)
    
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,"
                           "places.location,places.rating,places.userRatingCount,"
                           "places.priceLevel,places.types"
    }
    
    payload = {
        "textQuery": query,
        "maxResultCount": 20
    }
    
    response = requests.post(
        "https://places.googleapis.com/v1/places:searchText",
        headers=headers,
        json=payload
    )
    response.raise_for_status()
    data = response.json()
    
    bars = []
    for place in data.get("places", []):
        bar = collector._parse_place(place)
        if bar:
            bars.append(bar)
    
    return bars


if __name__ == "__main__":
    # Test
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    
    if not api_key:
        print("Error: GOOGLE_PLACES_API_KEY not set")
        exit(1)
    
    collector = GooglePlacesCollector(api_key)
    
    print("Searching for bars in Venice...")
    bars = collector.search_bars_in_venice(radius_meters=3000, max_results=50)
    
    print(f"Found {len(bars)} bars:")
    for bar in bars[:10]:
        print(f"  - {bar.name} ({bar.rating}⭐, {bar.review_count} reviews)")
