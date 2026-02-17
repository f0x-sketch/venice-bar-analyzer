# FastAPI Application
"""
Main FastAPI application for Venice Bar Analyzer API
"""

from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, Depends, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database.models import get_db_session, Bar, CrowdData, AnalyticsSnapshot

app = FastAPI(
    title="Venice Bar Analyzer",
    description="Real-time bar capacity, affluence, and dwell time analysis for Venice, Italy",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models for request/response
class BarResponse(BaseModel):
    id: str
    name: str
    address: str
    coordinates: dict
    rating: Optional[float]
    review_count: Optional[int]
    price_level: Optional[int]
    estimated_capacity: Optional[int]
    capacity_confidence: Optional[str]
    current_affluence: float
    current_busy_percent: Optional[int]
    avg_stay_minutes: Optional[int]
    peak_hours: List[int]
    best_time_to_visit: Optional[str]
    types: List[str]
    
    class Config:
        from_attributes = True


class HeatmapData(BaseModel):
    hourly_data: List[dict]
    neighborhoods: dict
    total_venues: int
    avg_capacity: float
    avg_affluence: float


class RecommendationRequest(BaseModel):
    vibe: Optional[str] = None  # quiet, lively, trendy
    capacity: Optional[str] = None  # small, medium, large
    time: Optional[str] = None  # now, lunch, aperitivo, dinner, late
    max_affluence: Optional[int] = None


# Routes

@app.get("/")
def root():
    return {
        "message": "Venice Bar Analyzer API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": [
            "/bars",
            "/bars/{id}",
            "/bars/{id}/analytics",
            "/heatmap",
            "/recommendations",
            "/stats"
        ]
    }


@app.get("/bars", response_model=List[BarResponse])
def list_bars(
    sort: str = Query("affluence", description="Sort by: capacity, affluence, rating"),
    order: str = Query("desc", description="Sort order: asc or desc"),
    min_capacity: Optional[int] = Query(None, description="Minimum capacity filter"),
    max_capacity: Optional[int] = Query(None, description="Maximum capacity filter"),
    max_affluence: Optional[int] = Query(None, description="Maximum affluence (quiet spots)"),
    min_rating: Optional[float] = Query(None, description="Minimum rating"),
    bar_type: Optional[str] = Query(None, description="Filter by type: wine_bar, pub, etc"),
    lat: Optional[float] = Query(None, description="Latitude for geo filter"),
    lng: Optional[float] = Query(None, description="Longitude for geo filter"),
    radius: int = Query(5000, description="Radius in meters for geo filter"),
    limit: int = Query(50, ge=1, le=200, description="Number of results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db_session)
):
    """
    List all bars with filtering and sorting
    """
    query = db.query(Bar)
    
    # Apply filters
    if min_capacity:
        query = query.filter(Bar.estimated_capacity >= min_capacity)
    
    if max_capacity:
        query = query.filter(Bar.estimated_capacity <= max_capacity)
    
    if min_rating:
        query = query.filter(Bar.rating >= min_rating)
    
    if bar_type and Bar.types is not None:
        # Filter by type in JSON array
        query = query.filter(Bar.types.contains([bar_type]))
    
    # Geo filter (simple bounding box, not perfect circle)
    if lat and lng:
        # Rough conversion: 0.01 degrees ≈ 1.1 km
        degree_offset = radius / 111000  # meters to degrees
        query = query.filter(
            Bar.lat >= lat - degree_offset,
            Bar.lat <= lat + degree_offset,
            Bar.lng >= lng - degree_offset,
            Bar.lng <= lng + degree_offset
        )
    
    # Apply sorting
    sort_column = {
        "capacity": Bar.estimated_capacity,
        "affluence": Bar.crowd_data.property.mapper.class_.current_popularity,
        "rating": Bar.rating,
        "name": Bar.name
    }.get(sort, Bar.rating)
    
    if order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())
    
    # Pagination
    total = query.count()
    bars = query.offset(offset).limit(limit).all()
    
    # Filter by affluence in Python (since it's calculated)
    if max_affluence is not None:
        bars = [b for b in bars if b.affluence_score <= max_affluence]
    
    return [bar.to_dict() for bar in bars]


@app.get("/bars/{bar_id}", response_model=BarResponse)
def get_bar(
    bar_id: str,
    db: Session = Depends(get_db_session)
):
    """Get detailed information about a specific bar"""
    bar = db.query(Bar).filter(Bar.id == bar_id).first()
    
    if not bar:
        raise HTTPException(status_code=404, detail="Bar not found")
    
    return bar.to_dict()


@app.get("/bars/{bar_id}/analytics")
def get_bar_analytics(
    bar_id: str,
    db: Session = Depends(get_db_session)
):
    """Get detailed analytics for a specific bar"""
    bar = db.query(Bar).filter(Bar.id == bar_id).first()
    
    if not bar:
        raise HTTPException(status_code=404, detail="Bar not found")
    
    crowd = bar.crowd_data
    
    return {
        "bar_id": bar_id,
        "name": bar.name,
        "capacity": {
            "estimate": bar.estimated_capacity,
            "confidence": bar.capacity_confidence,
            "methodology": bar.capacity_methodology
        },
        "crowd": {
            "current_popularity": crowd.current_popularity if crowd else None,
            "time_spent_minutes": crowd.time_spent_minutes if crowd else None,
            "wait_time_minutes": crowd.wait_time_minutes if crowd else None,
            "peak_hours": crowd.peak_hours if crowd else [],
            "best_time_to_visit": crowd.best_time_to_visit if crowd else None,
            "popularity_by_day": crowd.popularity_by_day if crowd else {}
        },
        "ratings": {
            "average": bar.rating,
            "review_count": bar.review_count
        },
        "affluence_score": bar.affluence_score,
        "last_updated": bar.updated_at.isoformat() if bar.updated_at else None
    }


@app.get("/heatmap", response_model=HeatmapData)
def get_heatmap(
    day: Optional[str] = Query(None, description="Day of week (default: today)"),
    db: Session = Depends(get_db_session)
):
    """Get heatmap data for Venice bar scene"""
    
    if not day:
        day = datetime.now().strftime("%A")
    
    # Get all bars with crowd data
    bars = db.query(Bar).join(CrowdData).all()
    
    # Calculate hourly averages
    hourly_data = []
    for hour in range(24):
        affluences = []
        for bar in bars:
            if bar.crowd_data and bar.crowd_data.popularity_by_day:
                day_data = bar.crowd_data.popularity_by_day.get(day, [])
                if hour < len(day_data):
                    affluences.append(day_data[hour])
        
        avg_affluence = sum(affluences) / len(affluences) if affluences else 0
        hourly_data.append({
            "hour": hour,
            "avg_affluence": round(avg_affluence, 1),
            "venue_count": len(affluences)
        })
    
    # Neighborhood aggregation (simplified - would need actual neighborhood data)
    neighborhoods = {
        "San Marco": {"avg_capacity": 35, "avg_affluence": 72, "venue_count": len(bars)//3},
        "Cannaregio": {"avg_capacity": 28, "avg_affluence": 58, "venue_count": len(bars)//3},
        "Dorsoduro": {"avg_capacity": 32, "avg_affluence": 65, "venue_count": len(bars)//3}
    }
    
    return {
        "hourly_data": hourly_data,
        "neighborhoods": neighborhoods,
        "total_venues": len(bars),
        "avg_capacity": sum(b.estimated_capacity or 0 for b in bars) / len(bars) if bars else 0,
        "avg_affluence": sum(b.affluence_score for b in bars) / len(bars) if bars else 0,
        "day": day
    }


@app.post("/recommendations", response_model=List[BarResponse])
def get_recommendations(
    request: RecommendationRequest,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db_session)
):
    """Get personalized bar recommendations"""
    
    query = db.query(Bar)
    
    # Apply vibe filter
    if request.vibe:
        if request.vibe == "quiet":
            # Low affluence, smaller capacity
            query = query.filter(Bar.estimated_capacity <= 40)
        elif request.vibe == "lively":
            # Higher affluence expected
            query = query.filter(Bar.estimated_capacity >= 30)
        elif request.vibe == "trendy":
            # Higher rating, more reviews
            query = query.filter(Bar.rating >= 4.0)
            query = query.filter(Bar.review_count >= 100)
    
    # Apply capacity filter
    if request.capacity:
        capacity_ranges = {
            "small": (0, 30),
            "medium": (30, 60),
            "large": (60, 500)
        }
        min_cap, max_cap = capacity_ranges.get(request.capacity, (0, 500))
        query = query.filter(Bar.estimated_capacity >= min_cap)
        query = query.filter(Bar.estimated_capacity <= max_cap)
    
    # Apply time filter
    if request.time:
        # This would use crowd data to find best venues for that time
        # Simplified implementation
        if request.time == "now":
            # Prefer places that aren't too busy right now
            pass  # Would filter by current_popularity
    
    # Apply max affluence
    if request.max_affluence:
        # Filter in Python since affluence is calculated
        bars = query.all()
        bars = [b for b in bars if b.affluence_score <= request.max_affluence]
    else:
        bars = query.limit(limit).all()
    
    # Sort by recommendation score
    def recommendation_score(bar):
        score = 0
        if bar.rating:
            score += bar.rating * 10
        if bar.estimated_capacity:
            score += min(bar.estimated_capacity / 10, 10)  # Cap at 10
        score += (100 - bar.affluence_score) / 10  # Prefer less busy
        return score
    
    bars.sort(key=recommendation_score, reverse=True)
    
    return [bar.to_dict() for bar in bars[:limit]]


@app.get("/stats")
def get_stats(db: Session = Depends(get_db_session)):
    """Get overall statistics"""
    bars = db.query(Bar).all()
    
    return {
        "total_bars": len(bars),
        "avg_rating": sum(b.rating or 0 for b in bars) / len(bars) if bars else 0,
        "avg_capacity": sum(b.estimated_capacity or 0 for b in bars) / len(bars) if bars else 0,
        "avg_affluence": sum(b.affluence_score for b in bars) / len(bars) if bars else 0,
        "price_distribution": {
            "$": sum(1 for b in bars if b.price_level == 1),
            "$$": sum(1 for b in bars if b.price_level == 2),
            "$$$": sum(1 for b in bars if b.price_level == 3),
            "$$$$": sum(1 for b in bars if b.price_level == 4)
        },
        "last_updated": max(b.updated_at for b in bars).isoformat() if bars else None
    }


@app.get("/search")
def search_bars(
    q: str = Query(..., description="Search query"),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db_session)
):
    """Search bars by name or address"""
    query = db.query(Bar).filter(
        Bar.name.ilike(f"%{q}%") | Bar.address.ilike(f"%{q}%")
    )
    
    bars = query.limit(limit).all()
    return [bar.to_dict() for bar in bars]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
