# Database Models
"""
SQLAlchemy models for Venice Bar Analyzer
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, 
    Text, JSON, ForeignKey, create_engine
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
import os

Base = declarative_base()


class Bar(Base):
    """Main bar entity"""
    __tablename__ = "bars"
    
    # Primary key
    id = Column(String, primary_key=True)  # Google Place ID
    
    # Basic info
    name = Column(String, nullable=False)
    address = Column(Text)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    
    # Google Places data
    rating = Column(Float)
    review_count = Column(Integer)
    price_level = Column(Integer)  # 0-4
    phone = Column(String)
    website = Column(String)
    opening_hours = Column(JSON)  # Store as JSON
    types = Column(JSON)  # List of place types
    
    # Capacity estimation
    estimated_capacity = Column(Integer)
    capacity_confidence = Column(String)  # high, medium, low
    capacity_methodology = Column(Text)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_crowd_update = Column(DateTime)
    
    # Relationships
    crowd_data = relationship("CrowdData", back_populates="bar", uselist=False)
    reviews = relationship("Review", back_populates="bar")
    photos = relationship("Photo", back_populates="bar")
    
    @property
    def affluence_score(self) -> float:
        """Calculate current affluence score"""
        if self.crowd_data and self.crowd_data.current_popularity is not None:
            return self.crowd_data.current_popularity
        return 50.0  # Default
    
    @property
    def current_busy_percent(self) -> Optional[int]:
        """Get current busy percentage"""
        if self.crowd_data:
            return self.crowd_data.current_popularity
        return None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API response"""
        return {
            "id": self.id,
            "name": self.name,
            "address": self.address,
            "coordinates": {"lat": self.lat, "lng": self.lng},
            "rating": self.rating,
            "review_count": self.review_count,
            "price_level": self.price_level,
            "estimated_capacity": self.estimated_capacity,
            "capacity_confidence": self.capacity_confidence,
            "current_affluence": self.affluence_score,
            "current_busy_percent": self.current_busy_percent,
            "avg_stay_minutes": self.crowd_data.time_spent_minutes if self.crowd_data else None,
            "peak_hours": self.crowd_data.peak_hours if self.crowd_data else [],
            "best_time_to_visit": self.crowd_data.best_time_to_visit if self.crowd_data else None,
            "types": self.types or [],
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class CrowdData(Base):
    """Crowd/popularity data from populartimes"""
    __tablename__ = "crowd_data"
    
    id = Column(Integer, primary_key=True)
    bar_id = Column(String, ForeignKey("bars.id"), nullable=False)
    
    # Live data
    current_popularity = Column(Integer)  # 0-100
    current_popularity_timestamp = Column(DateTime)
    
    # Historical patterns
    popularity_by_day = Column(JSON)  # {"Monday": [0,0,10,20...], ...}
    
    # Time metrics
    time_spent_minutes = Column(Integer)
    wait_time_minutes = Column(Integer)
    
    # Calculated fields
    peak_hours = Column(JSON)  # [20, 21, 22]
    best_time_to_visit = Column(String)  # "15:00"
    
    # Metadata
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    bar = relationship("Bar", back_populates="crowd_data")
    
    def get_popularity_for_hour(self, day: str, hour: int) -> Optional[int]:
        """Get popularity for specific day and hour"""
        if not self.popularity_by_day:
            return None
        day_data = self.popularity_by_day.get(day, [])
        if hour < len(day_data):
            return day_data[hour]
        return None


class Review(Base):
    """Individual reviews for NLP analysis"""
    __tablename__ = "reviews"
    
    id = Column(Integer, primary_key=True)
    bar_id = Column(String, ForeignKey("bars.id"), nullable=False)
    
    # Review data
    author = Column(String)
    rating = Column(Integer)
    text = Column(Text)
    time = Column(DateTime)
    
    # NLP analysis
    capacity_hints = Column(JSON)  # Extracted capacity keywords
    sentiment_score = Column(Float)
    
    # Relationship
    bar = relationship("Bar", back_populates="reviews")


class Photo(Base):
    """Venue photos"""
    __tablename__ = "photos"
    
    id = Column(Integer, primary_key=True)
    bar_id = Column(String, ForeignKey("bars.id"), nullable=False)
    
    photo_reference = Column(String)
    photo_url = Column(String)
    
    # Analysis (if using CV)
    estimated_tables = Column(Integer)
    estimated_seats = Column(Integer)
    analysis_timestamp = Column(DateTime)
    
    # Relationship
    bar = relationship("Bar", back_populates="photos")


class AnalyticsSnapshot(Base):
    """Historical analytics for trend analysis"""
    __tablename__ = "analytics_snapshots"
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Aggregate stats
    total_bars = Column(Integer)
    avg_capacity = Column(Float)
    avg_affluence = Column(Float)
    
    # By neighborhood (stored as JSON)
    neighborhood_stats = Column(JSON)
    
    # Hourly distribution
    hourly_affluence = Column(JSON)  # {"00": 15, "01": 8, ...}


# Database initialization
def init_database(database_url: str = None):
    """Initialize database and create tables"""
    if not database_url:
        database_url = os.getenv(
            "DATABASE_URL", 
            "postgresql://postgres:postgres@localhost:5432/venice_bars"
        )
    
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    
    Session = sessionmaker(bind=engine)
    return Session()


def get_db_session():
    """Get database session (for dependency injection)"""
    database_url = os.getenv(
        "DATABASE_URL", 
        "postgresql://postgres:postgres@localhost:5432/venice_bars"
    )
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        yield session
    finally:
        session.close()


if __name__ == "__main__":
    # Test database creation
    print("Initializing database...")
    session = init_database()
    print("Database tables created successfully!")
    
    # Test insert
    test_bar = Bar(
        id="test123",
        name="Test Bar",
        address="Test Address, Venice",
        lat=45.4333,
        lng=12.3378,
        rating=4.5,
        review_count=100,
        estimated_capacity=40,
        capacity_confidence="medium"
    )
    
    session.add(test_bar)
    session.commit()
    print(f"Test bar created: {test_bar.name}")
    
    # Query
    bars = session.query(Bar).all()
    print(f"Total bars in DB: {len(bars)}")
