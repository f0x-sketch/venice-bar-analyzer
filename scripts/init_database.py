#!/usr/bin/env python3
"""
Initialize database and create tables
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from database.models import init_database

def main():
    print("Initializing Venice Bar Analyzer database...")
    
    session = init_database()
    
    print("✓ Database tables created successfully!")
    print("\nYou can now run data collection:")
    print("  python scripts/collect_venues.py")
    print("\nOr start the API server:")
    print("  uvicorn api.main:app --reload")

if __name__ == "__main__":
    main()
