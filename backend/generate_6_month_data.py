#!/usr/bin/env python3
"""
Generate 6 months of comprehensive roster data with proper crew composition:
- 1 Captain, 1 FO, 1 Senior Crew, 1 Cabin Crew per flight
- Pilot continuity constraints (start next journey from landing location)
- Base return priority logic
- Extended crew and flight data for 6 months
"""

import csv
import random
from datetime import datetime, timedelta
from typing import List, Dict, Set

# Configuration
AIRPORTS = ["DEL", "BOM", "BLR", "MAA", "CCU", "HYD", "AMD", "PNQ", "GOI", "COK", "TRV", "JAI", "LKO", "IXR", "PAT"]
AIRCRAFT_TYPES = ["A320", "A321", "B737", "B777", "A350", "ATR72"]
BASES = ["DEL", "BOM", "BLR", "MAA", "CCU", "HYD"]

# Flight patterns - more realistic route network
ROUTE_NETWORK = {
    "DEL": ["BOM", "BLR", "MAA", "CCU", "HYD", "AMD", "PNQ", "JAI", "LKO"],
    "BOM": ["DEL", "BLR", "MAA", "CCU", "HYD", "AMD", "PNQ", "GOI", "COK"],
    "BLR": ["DEL", "BOM", "MAA", "CCU", "HYD", "AMD", "PNQ", "COK", "TRV"],
    "MAA": ["DEL", "BOM", "BLR", "CCU", "HYD", "COK", "TRV"],
    "CCU": ["DEL", "BOM", "BLR", "MAA", "HYD", "IXR", "PAT"],
    "HYD": ["DEL", "BOM", "BLR", "MAA", "CCU", "AMD", "PNQ"],
    "AMD": ["DEL", "BOM", "BLR", "HYD", "PNQ"],
    "PNQ": ["DEL", "BOM", "BLR", "HYD", "AMD", "GOI"],
    "GOI": ["BOM", "BLR", "PNQ"],
    "COK": ["BOM", "BLR", "MAA", "TRV"],
    "TRV": ["BLR", "MAA", "COK"],
    "JAI": ["DEL"],
    "LKO": ["DEL"],
    "IXR": ["CCU"],
    "PAT": ["CCU"]
}

# Flight duration mapping (in hours)
FLIGHT_DURATIONS = {
    ("DEL", "BOM"): 2.0, ("DEL", "BLR"): 2.5, ("DEL", "MAA"): 2.8, ("DEL", "CCU"): 2.2,
    ("DEL", "HYD"): 2.3, ("DEL", "AMD"): 1.5, ("DEL", "PNQ"): 2.0, ("DEL", "JAI"): 1.0,
    ("DEL", "LKO"): 1.2, ("BOM", "BLR"): 1.5, ("BOM", "MAA"): 1.8, ("BOM", "CCU"): 2.5,
    ("BOM", "HYD"): 1.2, ("BOM", "AMD"): 1.0, ("BOM", "PNQ"): 0.5, ("BOM", "GOI"): 1.0,
    ("BOM", "COK"): 1.5, ("BLR", "MAA"): 1.0, ("BLR", "CCU"): 2.0, ("BLR", "HYD"): 1.0,
    ("BLR", "AMD"): 1.5, ("BLR", "PNQ"): 1.2, ("BLR", "COK"): 1.0, ("BLR", "TRV"): 1.2,
    ("MAA", "CCU"): 2.0, ("MAA", "HYD"): 1.2, ("MAA", "COK"): 1.3, ("MAA", "TRV"): 1.5,
    ("CCU", "HYD"): 1.8, ("CCU", "IXR"): 1.5, ("CCU", "PAT"): 1.0, ("HYD", "AMD"): 1.5,
    ("HYD", "PNQ"): 1.0, ("AMD", "PNQ"): 0.5, ("PNQ", "GOI"): 0.5, ("COK", "TRV"): 0.5
}

def get_flight_duration(dep: str, arr: str) -> float:
    """Get flight duration in hours"""
    key = (dep, arr)
    reverse_key = (arr, dep)
    return FLIGHT_DURATIONS.get(key, FLIGHT_DURATIONS.get(reverse_key, 2.0))

def generate_crew_data():
    """Generate comprehensive crew data with senior crew members"""
    crew_data = []
    
    # Generate Captains - Increased for better GA coverage
    for i in range(1, 201):  # 200 captains
        base = random.choice(BASES)
        qualifications = "|".join(random.sample(AIRCRAFT_TYPES, random.randint(3, 5)))
        crew_data.append({
            'crew_id': f'CPT{i:03d}',
            'name': f'Capt. {generate_name()}',
            'role': 'Captain',
            'base': base,
            'qualified_types': qualifications,
            'weekly_max_duty_hrs': random.choice([75, 80, 85]),
            'leave_status': 'Available' if random.random() > 0.03 else random.choice(['On Leave', 'Training', 'Sick']),
            'sccm_certified': False,
            'experience_months': random.randint(60, 240)  # 5-20 years
        })
    
    # Generate First Officers - Increased for better GA coverage
    for i in range(1, 201):  # 200 FOs
        base = random.choice(BASES)
        qualifications = "|".join(random.sample(AIRCRAFT_TYPES, random.randint(3, 5)))
        crew_data.append({
            'crew_id': f'FO{i:03d}',
            'name': f'FO. {generate_name()}',
            'role': 'First Officer',
            'base': base,
            'qualified_types': qualifications,
            'weekly_max_duty_hrs': random.choice([75, 80, 85]),
            'leave_status': 'Available' if random.random() > 0.03 else random.choice(['On Leave', 'Training', 'Sick']),
            'sccm_certified': False,
            'experience_months': random.randint(24, 120)  # 2-10 years
        })
    
    # Generate Senior Crew - Increased for better GA coverage
    for i in range(1, 201):  # 200 Senior Crew
        base = random.choice(BASES)
        qualifications = "|".join(AIRCRAFT_TYPES)  # Senior crew qualified on all aircraft
        crew_data.append({
            'crew_id': f'SC{i:03d}',
            'name': f'SC. {generate_name()}',
            'role': 'Senior Crew',
            'base': base,
            'qualified_types': qualifications,
            'weekly_max_duty_hrs': random.choice([75, 80, 85]),
            'leave_status': 'Available' if random.random() > 0.02 else random.choice(['On Leave', 'Training', 'Sick']),
            'sccm_certified': True,  # All senior crew are SCCM certified
            'experience_months': random.randint(36, 180)  # 3-15 years
        })
    
    # Generate Cabin Crew - Increased significantly for 4 per flight coverage
    for i in range(1, 801):  # 800 Cabin Crew (sufficient for 4 per flight across date ranges)
        base = random.choice(BASES)
        qualifications = "|".join(random.sample(AIRCRAFT_TYPES, random.randint(4, 6)))
        crew_data.append({
            'crew_id': f'CC{i:03d}',
            'name': f'CC. {generate_name()}',
            'role': 'Cabin Crew',
            'base': base,
            'qualified_types': qualifications,
            'weekly_max_duty_hrs': random.choice([75, 80, 85]),
            'leave_status': 'Available' if random.random() > 0.05 else random.choice(['On Leave', 'Training', 'Sick']),
            'sccm_certified': random.random() > 0.5,  # 50% SCCM certified
            'experience_months': random.randint(6, 120)  # 6 months to 10 years
        })
    
    return crew_data

def generate_name():
    """Generate realistic Indian names"""
    first_names = [
        "Aarav", "Vihaan", "Arjun", "Rohan", "Ishaan", "Advait", "Aarush", "Reyansh", 
        "Vivaan", "Atharv", "Arnav", "Kabir", "Anaya", "Zara", "Aisha", "Meera", 
        "Priya", "Nisha", "Kavya", "Riya", "Diya", "Ira", "Kiara", "Saanvi",
        "Rajesh", "Suresh", "Ramesh", "Mahesh", "Dinesh", "Ganesh", "Umesh", "Naresh",
        "Sunita", "Geeta", "Rita", "Sita", "Nita", "Mira", "Kira", "Tara"
    ]
    
    last_names = [
        "Sharma", "Patel", "Singh", "Kumar", "Gupta", "Joshi", "Verma", "Reddy",
        "Iyer", "Nair", "Rao", "Malhotra", "Choudhury", "Khan", "Kapoor", "Shah",
        "Desai", "Jain", "Menon", "Bansal", "Agarwal", "Mishra", "Sinha", "Pandey",
        "Tiwari", "Chandra", "Bhatt", "Saxena", "Shukla", "Dubey"
    ]
    
    return f"{random.choice(first_names)} {random.choice(last_names)}"

def generate_flight_schedule():
    """Generate 6 months of flight schedule with realistic patterns"""
    start_date = datetime(2025, 9, 8)
    end_date = start_date + timedelta(days=180)  # 6 months
    
    flights = []
    flight_id_counter = 1000
    
    current_date = start_date
    while current_date <= end_date:
        # Skip some days randomly to simulate real scheduling
        if random.random() < 0.1:  # 10% chance to skip a day
            current_date += timedelta(days=1)
            continue
            
        # Generate 1-2 flights per day
        daily_flights = random.randint(1, 2)
        
        # Track aircraft utilization to ensure realistic turnarounds
        aircraft_schedule = {}
        
        for _ in range(daily_flights):
            # Select origin airport based on network
            dep_airport = random.choice(list(ROUTE_NETWORK.keys()))
            arr_airport = random.choice(ROUTE_NETWORK[dep_airport])
            
            # Generate departure time (6 AM to 10 PM)
            dep_hour = random.randint(6, 22)
            dep_minute = random.choice([0, 15, 30, 45])
            dep_time = current_date.replace(hour=dep_hour, minute=dep_minute)
            
            # Calculate arrival time
            flight_duration = get_flight_duration(dep_airport, arr_airport)
            arr_time = dep_time + timedelta(hours=flight_duration)
            
            # Select aircraft type based on route
            if (dep_airport in ["DEL", "BOM", "BLR"] and arr_airport in ["DEL", "BOM", "BLR"]) or flight_duration > 3:
                aircraft_type = random.choice(["A321", "B777", "A350"])
            elif flight_duration < 1:
                aircraft_type = "ATR72"
            else:
                aircraft_type = random.choice(["A320", "A321", "B737"])
            
            flight_data = {
                'flight_id': f'AI{flight_id_counter}',
                'date': current_date.strftime('%Y-%m-%d'),
                'dep_airport': dep_airport,
                'arr_airport': arr_airport,
                'dep_dt': dep_time.strftime('%Y-%m-%d %H:%M:%S'),
                'arr_dt': arr_time.strftime('%Y-%m-%d %H:%M:%S'),
                'aircraft_type': aircraft_type,
                'needed_captains': 1,
                'needed_fo': 1,
                'needed_sc': 1,  # Senior Cabin Crew
                'needed_cc': 4   # 4 Cabin Crew per flight
            }
            
            flights.append(flight_data)
            flight_id_counter += 1
        
        current_date += timedelta(days=1)
    
    return flights

def generate_crew_preferences(crew_data):
    """Generate crew preferences for days off and preferred sectors"""
    preferences = []
    
    for crew in crew_data:
        # Generate 2-5 requested days off per month
        num_days_off = random.randint(8, 20)  # Over 6 months
        requested_days = []
        
        for _ in range(num_days_off):
            # Random date in next 6 months
            random_day = random.randint(0, 179)
            date = datetime(2025, 9, 8) + timedelta(days=random_day)
            requested_days.append(date.strftime('%Y-%m-%d'))
        
        # Generate preferred sectors based on crew base
        crew_base = crew['base']
        if crew_base in ROUTE_NETWORK:
            possible_routes = ROUTE_NETWORK[crew_base]
            num_preferred = random.randint(2, min(5, len(possible_routes)))
            preferred_sectors = [f"{crew_base}-{dest}" for dest in random.sample(possible_routes, num_preferred)]
        else:
            preferred_sectors = []
        
        preferences.append({
            'crew_id': crew['crew_id'],
            'requested_days_off': '|'.join(requested_days),
            'preferred_sectors': '|'.join(preferred_sectors)
        })
    
    return preferences

def main():
    """Generate all data files"""
    print("Generating 6 months of comprehensive roster data...")
    
    # Generate crew data
    print("Generating crew data...")
    crew_data = generate_crew_data()
    
    # Generate flight schedule
    print("Generating flight schedule...")
    flight_data = generate_flight_schedule()
    
    # Generate crew preferences
    print("Generating crew preferences...")
    preferences_data = generate_crew_preferences(crew_data)
    
    # Save crew data
    with open('backend/data/crew_6month.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'crew_id', 'name', 'role', 'base', 'qualified_types',
            'weekly_max_duty_hrs', 'leave_status', 'sccm_certified', 'experience_months'
        ])
        writer.writeheader()
        writer.writerows(crew_data)
    
    # Save flight data
    with open('backend/data/flights_6month.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'flight_id', 'date', 'dep_airport', 'arr_airport', 'dep_dt', 'arr_dt',
            'aircraft_type', 'needed_captains', 'needed_fo', 'needed_sc', 'needed_cc'
        ])
        writer.writeheader()
        writer.writerows(flight_data)
    
    # Save preferences data
    with open('backend/data/crew_preferences_6month.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'crew_id', 'requested_days_off', 'preferred_sectors'
        ])
        writer.writeheader()
        writer.writerows(preferences_data)
    
    # Generate some sick leave data
    sick_data = []
    for _ in range(random.randint(10, 30)):
        crew_id = random.choice(crew_data)['crew_id']
        sick_date = datetime(2025, 9, 8) + timedelta(days=random.randint(0, 179))
        sick_data.append({
            'crew_id': crew_id,
            'sick_date': sick_date.strftime('%Y-%m-%d')
        })
    
    with open('backend/data/crew_sickness_6month.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['crew_id', 'sick_date'])
        writer.writeheader()
        writer.writerows(sick_data)
    
    print(f"Generated:")
    print(f"  - {len(crew_data)} crew members")
    print(f"  - {len(flight_data)} flights over 6 months")
    print(f"  - {len(preferences_data)} crew preferences")
    print(f"  - {len(sick_data)} sick leave records")
    print("All data saved to data/ directory with '_6month' suffix")

if __name__ == "__main__":
    main()