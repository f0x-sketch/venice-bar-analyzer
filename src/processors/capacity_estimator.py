# Capacity Estimator
"""
Estimates bar capacity using multiple signals since no API provides actual capacity
"""

import re
from typing import List, Optional, Dict
from dataclasses import dataclass


@dataclass
class CapacityEstimate:
    place_id: str
    estimated_capacity: int
    confidence: str  # high, medium, low
    signals_used: List[str]
    methodology: str


class CapacityEstimator:
    """
    Estimates venue capacity using multiple heuristics:
    1. Review text analysis (NLP)
    2. Photo metadata
    3. Category/type heuristics
    4. Price level correlation
    5. Review volume proxy
    """
    
    # Base capacity by venue type
    CATEGORY_BASELINES = {
        "wine_bar": 25,
        "cocktail_bar": 35,
        "pub": 60,
        "night_club": 150,
        "lounge": 40,
        "beer_bar": 50,
        "tapas_bar": 35,
        "sports_bar": 80,
        "hotel_bar": 50,
        "rooftop_bar": 45,
        "dive_bar": 30,
        "speakeasy": 25,
        "default": 35
    }
    
    # Keywords indicating size in reviews
    SIZE_KEYWORDS = {
        "tiny": 15, "very small": 15, "cramped": 20,
        "small": 25, "cozy": 30, "intimate": 30,
        "medium": 45, "moderate": 45, "average": 45,
        "large": 70, "spacious": 75, "big": 75,
        "huge": 120, "massive": 150, "enormous": 200
    }
    
    # Capacity mention patterns
    CAPACITY_PATTERNS = [
        r"(\d+)\s*(?:seats?|places?|spots?|tables?)",
        r"(?:fits?|holds?|capacity\s+(?:of|for)?)\s+(\d+)",
        r"(?:\d+)\s*(?:person|people|pax|guests?)\s*(?:max|maximum|capacity)"
    ]

    def __init__(self):
        self.signals = []
    
    def estimate_capacity(
        self,
        place_id: str,
        name: str,
        types: List[str],
        reviews: List[Dict],
        price_level: Optional[int] = None,
        review_count: int = 0,
        rating: Optional[float] = None,
        photos_count: int = 0
    ) -> CapacityEstimate:
        """
        Estimate capacity using multiple signals
        
        Args:
            place_id: Google Place ID
            name: Venue name
            types: List of place types
            reviews: List of review objects with 'text' field
            price_level: 0-4 price level
            review_count: Total number of reviews
            rating: Average rating
            photos_count: Number of photos
            
        Returns:
            CapacityEstimate with estimate and confidence
        """
        estimates = []
        signals_used = []
        
        # Signal 1: Review text analysis
        review_estimate = self._estimate_from_reviews(reviews)
        if review_estimate:
            estimates.append(review_estimate)
            signals_used.append("review_text_analysis")
        
        # Signal 2: Category baseline
        category_estimate = self._estimate_from_category(types)
        if category_estimate:
            estimates.append(category_estimate)
            signals_used.append("category_baseline")
        
        # Signal 3: Price level adjustment
        price_adjustment = self._adjustment_from_price(price_level)
        
        # Signal 4: Review volume proxy (popular places tend to be larger)
        volume_adjustment = self._adjustment_from_review_volume(review_count)
        
        # Signal 5: Photo count proxy
        photo_adjustment = self._adjustment_from_photos(photos_count)
        
        # Combine estimates
        if estimates:
            # Weighted average
            if len(estimates) == 1:
                base_estimate = estimates[0]
            else:
                # Weight review-based higher if available
                weights = [0.6 if "review" in s else 0.4 for s in signals_used]
                base_estimate = sum(e * w for e, w in zip(estimates, weights)) / sum(weights)
        else:
            # Fallback to default
            base_estimate = self.CATEGORY_BASELINES["default"]
            signals_used.append("default_fallback")
        
        # Apply adjustments
        final_estimate = int(base_estimate + price_adjustment + volume_adjustment + photo_adjustment)
        
        # Ensure reasonable bounds
        final_estimate = max(10, min(500, final_estimate))
        
        # Determine confidence
        confidence = self._calculate_confidence(signals_used, reviews, review_count)
        
        return CapacityEstimate(
            place_id=place_id,
            estimated_capacity=final_estimate,
            confidence=confidence,
            signals_used=signals_used,
            methodology=self._generate_methodology(signals_used, final_estimate)
        )
    
    def _estimate_from_reviews(self, reviews: List[Dict]) -> Optional[int]:
        """Extract capacity hints from review text"""
        if not reviews:
            return None
        
        size_scores = []
        explicit_capacities = []
        
        for review in reviews:
            text = review.get("text", "").lower()
            if not text:
                continue
            
            # Check for explicit capacity mentions
            for pattern in self.CAPACITY_PATTERNS:
                matches = re.findall(pattern, text)
                for match in matches:
                    try:
                        capacity = int(match)
                        if 5 <= capacity <= 500:  # Reasonable range
                            explicit_capacities.append(capacity)
                    except:
                        pass
            
            # Check for size keywords
            for keyword, capacity in self.SIZE_KEYWORDS.items():
                if keyword in text:
                    size_scores.append(capacity)
        
        # Prioritize explicit mentions
        if explicit_capacities:
            return int(sum(explicit_capacities) / len(explicit_capacities))
        
        # Use keyword-based estimate
        if size_scores:
            return int(sum(size_scores) / len(size_scores))
        
        return None
    
    def _estimate_from_category(self, types: List[str]) -> Optional[int]:
        """Get baseline capacity from venue type"""
        if not types:
            return None
        
        # Map Google types to our categories
        type_mapping = {
            "wine_bar": "wine_bar",
            "bar": "cocktail_bar",
            "pub": "pub",
            "night_club": "night_club",
            "lounge": "lounge",
            "sports_bar": "sports_bar"
        }
        
        for t in types:
            t_clean = t.replace("_", "_")  # Normalize
            if t_clean in type_mapping:
                return self.CATEGORY_BASELINES.get(type_mapping[t_clean])
            if t_clean in self.CATEGORY_BASELINES:
                return self.CATEGORY_BASELINES[t_clean]
        
        return self.CATEGORY_BASELINES["default"]
    
    def _adjustment_from_price(self, price_level: Optional[int]) -> int:
        """
        Adjust capacity based on price level
        Higher price = usually larger/more upscale
        """
        if price_level is None:
            return 0
        
        # Price level adjustments
        adjustments = {
            0: -5,   # Free - probably small
            1: -5,   # Inexpensive - likely smaller
            2: 0,    # Moderate - baseline
            3: 10,   # Expensive - larger venue
            4: 20    # Very expensive - likely spacious
        }
        
        return adjustments.get(price_level, 0)
    
    def _adjustment_from_review_volume(self, review_count: int) -> int:
        """
        Popular venues tend to be larger
        """
        if review_count > 1000:
            return 15
        elif review_count > 500:
            return 10
        elif review_count > 100:
            return 5
        elif review_count < 10:
            return -10  # Very new/small
        return 0
    
    def _adjustment_from_photos(self, photos_count: int) -> int:
        """
        More photos might indicate larger space to show
        """
        if photos_count > 20:
            return 10
        elif photos_count > 10:
            return 5
        return 0
    
    def _calculate_confidence(
        self, 
        signals_used: List[str], 
        reviews: List[Dict],
        review_count: int
    ) -> str:
        """Determine confidence level based on data quality"""
        score = 0
        
        # More signals = higher confidence
        score += len(signals_used) * 20
        
        # Review-based signals are strong
        if "review_text_analysis" in signals_used:
            score += 30
        
        # More reviews = more reliable
        if review_count > 100:
            score += 20
        elif review_count > 20:
            score += 10
        
        # Map score to confidence
        if score >= 70:
            return "high"
        elif score >= 40:
            return "medium"
        return "low"
    
    def _generate_methodology(self, signals_used: List[str], estimate: int) -> str:
        """Generate human-readable methodology description"""
        parts = []
        
        if "review_text_analysis" in signals_used:
            parts.append("extracted explicit capacity mentions and size keywords from reviews")
        
        if "category_baseline" in signals_used:
            parts.append("applied category-based baseline capacity")
        
        if "default_fallback" in signals_used:
            parts.append("used default baseline (limited data available)")
        
        methodology = f"Estimated {estimate} people capacity based on: " + "; ".join(parts)
        methodology += ". Adjusted for price level, popularity, and available photos."
        
        return methodology


# Advanced: Photo-based estimation (requires ML)
class PhotoCapacityEstimator:
    """
    Estimate capacity by analyzing venue photos
    Requires computer vision model (optional enhancement)
    """
    
    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        if model_path:
            # Load CV model (e.g., YOLO, Faster R-CNN)
            # self.model = load_model(model_path)
            pass
    
    def estimate_from_photo(self, photo_url: str) -> Optional[int]:
        """
        Analyze photo to count tables/seats
        
        This is a placeholder - would require:
        1. Downloading photo
        2. Running object detection (tables, chairs, people)
        3. Estimating capacity from detected furniture
        """
        if not self.model:
            return None
        
        # Placeholder implementation
        # In reality, would use something like:
        # - detectron2 for table/chair detection
        # - Custom trained model for venue capacity
        
        return None


if __name__ == "__main__":
    # Test
    estimator = CapacityEstimator()
    
    # Mock test data
    test_reviews = [
        {"text": "Great little bar, very cozy with about 20 seats"},
        {"text": "Intimate atmosphere, perfect for dates"},
        {"text": "Small place but amazing cocktails"}
    ]
    
    result = estimator.estimate_capacity(
        place_id="test123",
        name="Test Wine Bar",
        types=["wine_bar", "bar"],
        reviews=test_reviews,
        price_level=3,
        review_count=150,
        rating=4.5,
        photos_count=12
    )
    
    print(f"Estimated Capacity: {result.estimated_capacity}")
    print(f"Confidence: {result.confidence}")
    print(f"Signals: {result.signals_used}")
    print(f"Methodology: {result.methodology}")
