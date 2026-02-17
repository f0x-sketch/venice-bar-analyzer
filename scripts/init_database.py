#!/usr/bin/env python3
"""
Initialize the database and create tables
"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from database.models import init_database
from dotenv import load_dotenv

def main():
    print("=" * 60)
    print("Venice Bar Analyzer - Database Initialization")
    print("=" * 60)
    
    # Load environment variables
    load_dotenv()
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("\n⚠️  Warning: DATABASE_URL not set in .env")
        print("Using default: postgresql://postgres:postgres@localhost:5432/venice_bars")
        database_url = "postgresql://postgres:postgres@localhost:5432/venice_bars"
    
    print(f"\nConnecting to: {database_url.split('@')[1] if '@' in database_url else database_url}")
    
    try:
        session = init_database(database_url)
        print("\n✅ Database initialized successfully!")
        print("\nTables created:")
        print("  - bars")
        print("  - crowd_data")
        print("  - reviews")
        print("  - photos")
        print("  - analytics_snapshots")
        
        # Test connection
        from sqlalchemy import text
        result = session.execute(text("SELECT 1"))
        print("\n✅ Database connection verified!")
        
    except Exception as e:
        print(f"\n❌ Error initializing database: {e}")
        print("\nMake sure PostgreSQL is running and accessible:")
        print("  docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:15")
        sys.exit(1)

if __name__ == "__main__":
    main()
