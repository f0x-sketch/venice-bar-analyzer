# Venice Bar Analyzer

> Real-time bar capacity, affluence, and dwell time analysis for Venice, Italy

## Overview

Multi-source data collection system that aggregates bar information from Google Places, populartimes scraping, and Foursquare to provide actionable insights about Venice's bar scene.

## Architecture

```
venice-bar-analyzer/
├── src/
│   ├── collectors/
│   │   ├── google_places.py      # Google Places API integration
│   │   ├── populartimes_scraper.py # Crowd data scraping
│   │   └── foursquare_api.py     # Foursquare check-in data
│   ├── processors/
│   │   ├── capacity_estimator.py # ML-based capacity estimation
│   │   ├── affluence_scorer.py   # Busy-ness scoring algorithm
│   │   └── data_normalizer.py    # Cross-source data merging
│   ├── database/
│   │   ├── models.py             # SQLAlchemy models
│   │   └── migrations/           # Alembic migrations
│   ├── api/
│   │   ├── main.py               # FastAPI application
│   │   └── routes/
│   │       ├── bars.py           # Bar listing endpoints
│   │       ├── analytics.py      # Analytics endpoints
│   │       └── heatmap.py        # Heatmap data endpoints
│   └── utils/
│       ├── config.py             # Configuration management
│       └── geo.py                # Geo-spatial utilities
├── scripts/
│   ├── init_database.py          # Database initialization
│   ├── collect_venues.py         # One-time venue collection
│   └── update_metrics.py         # Scheduled metrics update
├── notebooks/
│   └── capacity_analysis.ipynb   # Capacity estimation research
├── tests/
│   └── test_collectors.py
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── data/
│   └── raw/                      # Raw collected data
├── .env.example
├── requirements.txt
└── README.md
```

## Data Sources

### 1. Google Places API (New)
**Used for:**
- Discovering all bars in Venice
- Basic venue info (name, address, phone, website)
- Photos and reviews
- Rating and review count
- Opening hours

**Limitations:**
- Does NOT provide Popular Times data
- Does NOT provide live occupancy
- Capacity not directly available

### 2. populartimes Library
**Used for:**
- Live busy-ness percentage
- Popular times by hour/day
- Typical visit duration
- Hourly foot traffic estimates

**Method:**
- Scrapes Google Maps public data
- No API key required for basic usage
- Rate limiting applies

### 3. Foursquare Places API
**Used for:**
- Additional venue metadata
- Check-in counts (popularity proxy)
- User tips and reviews
- Category verification

**Limitations:**
- Free tier: 500 calls/day
- Limited crowd data

## Key Metrics

### Capacity Estimation
Since no API provides actual capacity, we estimate using:

1. **Photo Analysis** (optional ML)
   - Count visible tables/seats in photos
   - Estimate standing room

2. **Review Text Analysis**
   - NLP extraction of mentions like "small", "cozy", "spacious", "40 seats"
   - Keyword matching for capacity hints

3. **Category Heuristics**
   - Wine bar: 20-40 capacity
   - Cocktail bar: 30-60 capacity
   - Pub: 50-100 capacity
   - Adjust based on rating/review volume

4. **Cross-validation**
   - Compare Google photos vs Foursquare photos
   - Weight by data confidence

### Affluence Score (0-100)
Composite score based on:
- **Current busy-ness %** (populartimes): 40% weight
- **Peak hour density** (populartimes): 30% weight
- **Review velocity** (Google): 15% weight
- **Check-in frequency** (Foursquare): 15% weight

### Stay Duration
Direct from populartimes:
- "Typically people spend 45 min here"
- Used to calculate turnover rate

## API Endpoints

### GET /bars
List all bars with filters and sorting.

```json
{
  "bars": [
    {
      "id": "ChIJ...",
      "name": "Harry's Bar",
      "address": "Calle Vallaresso, 1323, 30124 Venezia VE",
      "capacity_estimate": 45,
      "current_affluence": 78,
      "avg_stay_minutes": 65,
      "rating": 4.2,
      "price_level": 4,
      "coordinates": {"lat": 45.4333, "lng": 12.3378},
      "current_busy_percent": 85,
      "peak_hours": ["20:00", "21:00", "22:00"],
      "best_time_to_visit": "15:00"
    }
  ]
}
```

Query params:
- `sort=capacity|affluence|rating`
- `order=asc|desc`
- `min_capacity=20`
- `max_affluence=50` (for quieter spots)
- `lat/lng/radius` (geo filter)

### GET /bars/{id}/analytics
Detailed analytics for a specific bar.

### GET /heatmap
Get heatmap data for Venice bar scene.

```json
{
  "hourly_data": [
    {"hour": 0, "avg_affluence": 15},
    {"hour": 1, "avg_affluence": 8},
    ...
  ],
  "neighborhoods": {
    "San Marco": {"avg_capacity": 35, "avg_affluence": 72},
    "Cannaregio": {"avg_capacity": 28, "avg_affluence": 58}
  }
}
```

### GET /recommendations
Smart recommendations based on preferences.

Query params:
- `vibe=quiet|lively|trendy`
- `capacity=min|medium|max`
- `time=now|lunch|aperitivo|dinner|late`

## Data Collection Strategy

### Initial Collection (One-time)
```python
# 1. Search all bars in Venice
# Define Venice bounding box
venice_bbox = {
    "north": 45.444,
    "south": 45.425,
    "east": 12.360,
    "west": 12.310
}

# Paginate through Google Places
# Filter by type: "bar", "wine_bar", "pub"
# Store all venue IDs
```

### Scheduled Updates (Every 15 minutes)
```python
# Update live metrics from populartimes
# Refresh Foursquare check-in counts (daily)
# Update Google review counts (daily)
```

## Setup

### 1. Clone and Install
```bash
git clone https://github.com/YOUR_REPO/venice-bar-analyzer.git
cd venice-bar-analyzer
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your API keys
```

Required keys:
- `GOOGLE_PLACES_API_KEY` - From Google Cloud Console
- `FOURSQUARE_API_KEY` - From Foursquare Developer
- `DATABASE_URL` - PostgreSQL connection string

### 3. Initialize Database
```bash
python scripts/init_database.py
```

### 4. Collect Initial Data
```bash
python scripts/collect_venues.py
```

### 5. Run API Server
```bash
cd src/api
uvicorn main:app --reload
```

## Deployment

### Docker
```bash
docker-compose up -d
```

### Environment Variables
```env
# APIs
GOOGLE_PLACES_API_KEY=your_key_here
FOURSQUARE_API_KEY=your_key_here

# Database
DATABASE_URL=postgresql://user:pass@localhost/venice_bars

# Collection Settings
COLLECTION_RADIUS_METERS=5000
UPDATE_INTERVAL_MINUTES=15
VENICE_CENTER_LAT=45.4333
VENICE_CENTER_LNG=12.3378

# Rate Limiting (important for populartimes)
REQUEST_DELAY_SECONDS=2
MAX_RETRIES=3
```

## Usage Examples

### Find quiet bars for a relaxed drink
```bash
curl "http://localhost:8000/bars?sort=affluence&order=asc&max_affluence=30"
```

### Find high-capacity venues for groups
```bash
curl "http://localhost:8000/bars?sort=capacity&order=desc&min_capacity=50"
```

### Get current best time to go out
```bash
curl "http://localhost:8000/heatmap"
```

### Bar recommendation for right now
```bash
curl "http://localhost:8000/recommendations?time=now&vibe=lively"
```

## Capacity Estimation Details

Since no API provides actual capacity, we use a multi-factor estimation:

```python
# Pseudocode for capacity estimation
def estimate_capacity(venue_data):
    signals = []
    
    # Signal 1: Review text mentions
    review_signals = analyze_reviews(venue_data['reviews'])
    if 'small' in review_signals: signals.append(25)
    if 'cozy' in review_signals: signals.append(30)
    if 'spacious' in review_signals: signals.append(60)
    
    # Signal 2: Photo table count (if ML enabled)
    photo_estimate = estimate_from_photos(venue_data['photos'])
    if photo_estimate: signals.append(photo_estimate)
    
    # Signal 3: Category baseline
    category_baseline = get_category_baseline(venue_data['type'])
    signals.append(category_baseline)
    
    # Signal 4: Price level adjustment
    price_adjustment = venue_data['price_level'] * 10  # Higher price = larger venue
    
    # Weighted average
    return weighted_average(signals) + price_adjustment
```

## Rate Limiting & Ethics

### API Limits
- **Google Places**: 100 requests/day (free), $5/1000 beyond
- **Foursquare**: 500 calls/day (free tier)
- **populartimes**: No hard limit but be respectful (2s delay)

### Best Practices
- Cache aggressively
- Respect robots.txt for scraping
- Don't overwhelm small business servers
- Update frequencies: Live (15min), Daily (reviews), Weekly (photos)

## Future Enhancements

1. **ML Capacity Estimation**
   - Train model on labeled venue photos
   - Computer vision for table counting

2. **Predictive Analytics**
   - Forecast busy-ness based on weather, events, holidays
   - Historical trend analysis

3. **User Contribution**
   - Crowd-sourced capacity validation
   - Real-time occupancy reports

4. **Expansion**
   - Other Venetian neighborhoods
   - Other Italian cities
   - Restaurant/cafe variants

## License

MIT License - See LICENSE file

## Contributing

1. Fork the repository
2. Create feature branch
3. Submit pull request

## Disclaimer

Capacity estimates are algorithmic approximations, not official venue data. Always verify with venues for large groups or special events.
