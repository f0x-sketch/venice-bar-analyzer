# Venice Bar CSV Generator

> One-shot Docker container that generates a CSV file with all Venice bars, capacity estimates, and affluence data

## Quick Start

```bash
# 1. Set your Google Places API key
export GOOGLE_PLACES_API_KEY=your_key_here

# 2. Run the container
docker run -e GOOGLE_PLACES_API_KEY=$GOOGLE_PLACES_API_KEY \
  -v $(pwd)/output:/output \
  venice-bar-csv-generator

# 3. Find your CSV in ./output/venice_bars_YYYYMMDD_HHMMSS.csv
```

## CSV Output Columns

| Column | Description |
|--------|-------------|
| `place_id` | Google Place ID |
| `name` | Bar name |
| `address` | Full address |
| `lat` | Latitude |
| `lng` | Longitude |
| `rating` | Google rating (1-5) |
| `review_count` | Number of reviews |
| `price_level` | Price level ($ to $$$$) |
| `phone` | Phone number |
| `website` | Website URL |
| `bar_types` | Types (wine_bar, pub, etc.) |
| `estimated_capacity` | **Estimated capacity (people)** |
| `capacity_confidence` | Confidence level (high/medium/low) |
| `capacity_signals` | What signals were used |
| `capacity_methodology` | How capacity was calculated |
| `current_popularity` | **Live busy-ness % (0-100)** |
| `popularity_today` | Hourly popularity for today |
| `peak_hours` | Peak hours (e.g., "20,21,22") |
| `best_time_to_visit` | Best time to go |
| `typical_visit_duration` | How long people stay |
| `affluence_score` | **Overall affluence score (0-100)** |
| `collected_at` | Timestamp of data collection |

## Capacity Estimation

Uses NLP on review text to extract capacity hints:
- **Explicit mentions**: "40 seats", "fits 50 people"
- **Size keywords**: tiny(15), small(25), cozy(30), medium(45), large(70), huge(120)
- **Category baselines**: Wine bar(25), Cocktail bar(35), Pub(60), Night club(150)
- **Price adjustment**: Higher price = larger venue
- **Review volume**: Popular places tend to be larger

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_PLACES_API_KEY` | **Yes** | - | Google Places API key |
| `COLLECTION_RADIUS` | No | 3000 | Search radius in meters |
| `MAX_RESULTS` | No | 200 | Maximum bars to collect |
| `REQUEST_DELAY` | No | 2 | Seconds between API calls |

## Build & Run

```bash
# Build
docker build -t venice-bar-csv-generator -f docker/Dockerfile .

# Run (produces CSV and exits)
docker run -e GOOGLE_PLACES_API_KEY=$KEY -v $(pwd)/output:/output venice-bar-csv-generator

# Generate new CSV (restart container)
docker run --rm -e GOOGLE_PLACES_API_KEY=$KEY -v $(pwd)/output:/output venice-bar-csv-generator
```

## Docker Compose

```bash
# Set your API key
export GOOGLE_PLACES_API_KEY=your_key_here

# Run once
docker-compose up

# Generate new CSV
docker-compose up --force-recreate
```

## License

MIT
