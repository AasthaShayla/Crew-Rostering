#!/usr/bin/env python3
"""
Generate large-scale dataset for Crew Rostering Optimization System
Creates 80+ flights and 100+ crew members for genetic algorithm testing
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

def generate_large_flights(num_flights=100):
    """Generate large flight dataset"""
    print(f"🛫 Generating {num_flights} flights...")

    # Indian airports with realistic connections
    airports = [
        'DEL', 'BOM', 'BLR', 'MAA', 'CCU', 'HYD', 'AMD', 'GOI', 'COK', 'IXC',
        'IXJ', 'IXA', 'PAT', 'VTZ', 'IDR', 'JAI', 'LKO', 'VNS', 'SXR', 'IXB'
    ]

    aircraft_types = ['A320', 'A321', 'B737', 'B777', 'A350']

    flights = []
    base_date = datetime(2025, 9, 8)  # Start from tomorrow

    for i in range(num_flights):
        # Random departure airport
        dep_airport = random.choice(airports)

        # Choose arrival airport (different from departure)
        arr_airport = random.choice([a for a in airports if a != dep_airport])

        # Random flight date within next 7 days
        flight_date = base_date + timedelta(days=random.randint(0, 6))

        # Random departure time between 6 AM and 10 PM
        dep_hour = random.randint(6, 22)
        dep_minute = random.choice([0, 15, 30, 45])
        dep_dt = flight_date.replace(hour=dep_hour, minute=dep_minute)

        # Random flight duration (1-4 hours)
        duration_hours = random.randint(1, 4)
        duration_minutes = random.randint(0, 59)
        arr_dt = dep_dt + timedelta(hours=duration_hours, minutes=duration_minutes)

        # Aircraft type
        aircraft_type = random.choice(aircraft_types)

        # Crew requirements based on aircraft type
        if aircraft_type in ['A320', 'A321', 'B737']:
            needed_captains = 1
            needed_fo = 1
            needed_cc = 2
        elif aircraft_type == 'B777':
            needed_captains = 1
            needed_fo = 1
            needed_cc = 4
        else:  # A350
            needed_captains = 1
            needed_fo = 1
            needed_cc = 3

        flight = {
            'flight_id': f'AI{i+1000:04d}',
            'date': flight_date.strftime('%Y-%m-%d'),
            'dep_airport': dep_airport,
            'arr_airport': arr_airport,
            'dep_dt': dep_dt.strftime('%Y-%m-%d %H:%M:%S'),
            'arr_dt': arr_dt.strftime('%Y-%m-%d %H:%M:%S'),
            'aircraft_type': aircraft_type,
            'needed_captains': needed_captains,
            'needed_fo': needed_fo,
            'needed_cc': needed_cc
        }

        flights.append(flight)

    # Sort by departure time
    flights.sort(key=lambda x: x['dep_dt'])

    return pd.DataFrame(flights)

def generate_large_crew(num_crew=120):
    """Generate large crew dataset"""
    print(f"👥 Generating {num_crew} crew members...")

    roles = ['Captain', 'First Officer', 'Cabin Crew']
    bases = ['DEL', 'BOM', 'BLR', 'MAA', 'CCU', 'HYD']
    aircraft_qualifications = ['A320', 'A321', 'B737', 'B777', 'A350']

    crew = []

    for i in range(num_crew):
        role = random.choice(roles)

        # Base assignment (weighted towards major hubs)
        base_weights = [0.3, 0.25, 0.15, 0.15, 0.08, 0.07]  # DEL, BOM, BLR, MAA, CCU, HYD
        base = random.choices(bases, weights=base_weights)[0]

        # Qualifications based on role
        if role == 'Captain':
            # Captains qualified on multiple types
            num_qualifications = random.randint(2, 5)
            qualified_types = random.sample(aircraft_qualifications, num_qualifications)
        elif role == 'First Officer':
            # FOs qualified on 2-4 types
            num_qualifications = random.randint(2, 4)
            qualified_types = random.sample(aircraft_qualifications, num_qualifications)
        else:  # Cabin Crew
            # CC qualified on all types (they're flexible)
            qualified_types = aircraft_qualifications.copy()

        qualified_types_str = ','.join(qualified_types)

        # Weekly max duty hours (DGCA compliant)
        if role == 'Captain':
            weekly_max = random.randint(70, 85)
        elif role == 'First Officer':
            weekly_max = random.randint(70, 85)
        else:  # Cabin Crew
            weekly_max = random.randint(75, 90)

        crew_member = {
            'crew_id': f'{role[:3].upper()}{i+1:03d}',
            'name': f'{role} {i+1}',
            'role': role,
            'base': base,
            'qualified_types': qualified_types_str,
            'weekly_max_duty_hrs': weekly_max,
            'leave_status': 'Available'
        }

        crew.append(crew_member)

    return pd.DataFrame(crew)

def generate_crew_preferences(crew_df):
    """Generate crew preferences"""
    print("📅 Generating crew preferences...")

    preferences = []

    for _, crew in crew_df.iterrows():
        crew_id = crew['crew_id']

        # Random day-off requests (0-2 days off per week)
        days_off = random.randint(0, 2)
        requested_days_off = []

        if days_off > 0:
            # Choose random days within next week
            base_date = datetime(2025, 9, 8)
            available_days = [(base_date + timedelta(days=i)).strftime('%Y-%m-%d')
                            for i in range(7)]
            requested_days_off = random.sample(available_days, days_off)

        # Preferred sectors (some crew prefer certain routes)
        preferred_sectors = []
        if random.random() < 0.3:  # 30% have preferences
            airports = ['DEL', 'BOM', 'BLR', 'MAA', 'CCU', 'HYD']
            num_prefs = random.randint(1, 3)
            preferred_combinations = []
            for _ in range(num_prefs):
                dep = random.choice(airports)
                arr = random.choice([a for a in airports if a != dep])
                preferred_combinations.append(f"{dep}-{arr}")
            preferred_sectors = preferred_combinations

        pref = {
            'crew_id': crew_id,
            'requested_days_off': ','.join(requested_days_off) if requested_days_off else '',
            'preferred_sectors': ','.join(preferred_sectors) if preferred_sectors else ''
        }

        preferences.append(pref)

    return pd.DataFrame(preferences)

def main():
    """Generate all large-scale datasets"""
    print("🚀 Generating Large-Scale Crew Rostering Dataset")
    print("=" * 50)

    # Generate flights
    flights_df = generate_large_flights(100)
    print(f"✅ Generated {len(flights_df)} flights")

    # Generate crew
    crew_df = generate_large_crew(120)
    print(f"✅ Generated {len(crew_df)} crew members")

    # Generate preferences
    prefs_df = generate_crew_preferences(crew_df)
    print(f"✅ Generated preferences for {len(prefs_df)} crew members")

    # Save to CSV files
    flights_df.to_csv('backend/data/flights_large.csv', index=False)
    crew_df.to_csv('backend/data/crew_large.csv', index=False)
    prefs_df.to_csv('backend/data/crew_preferences_large.csv', index=False)

    print("\n📊 Dataset Summary:")
    print(f"   Flights: {len(flights_df)}")
    print(f"   Crew: {len(crew_df)}")
    print(f"   Captains: {len(crew_df[crew_df['role'] == 'Captain'])}")
    print(f"   First Officers: {len(crew_df[crew_df['role'] == 'First Officer'])}")
    print(f"   Cabin Crew: {len(crew_df[crew_df['role'] == 'Cabin Crew'])}")

    print("\n💾 Files saved:")
    print("   backend/data/flights_large.csv")
    print("   backend/data/crew_large.csv")
    print("   backend/data/crew_preferences_large.csv")

    print("\n🎯 Ready for genetic algorithm optimization!")

if __name__ == "__main__":
    main()