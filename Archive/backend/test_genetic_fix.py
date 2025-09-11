#!/usr/bin/env python3
"""
Test script to validate genetic algorithm fixes
"""

import sys
import os
import pandas as pd
import json

# Add the current directory to path so we can import genetic_optimizer
sys.path.append(os.path.dirname(__file__))

from genetic_optimizer import GeneticOptimizer, GAConfig

def test_genetic_fix():
    """Test the genetic algorithm with 6-month dataset"""
    
    print("🧪 Testing Genetic Algorithm Fix...")
    
    # Load the 6-month dataset
    data_path = os.path.join(os.path.dirname(__file__), 'data')
    flights_df = pd.read_csv(os.path.join(data_path, 'flights_6month.csv'))
    crew_df = pd.read_csv(os.path.join(data_path, 'crew_6month.csv'))
    
    # Use full dataset to test complete functionality
    print(f"📊 Testing with full dataset: {len(flights_df)} flights, {len(crew_df)} crew")
    
    with open(os.path.join(data_path, 'dgca_rules.json'), 'r') as f:
        dgca_rules = json.load(f)
    
    print(f"📊 Testing with {len(flights_df)} flights, {len(crew_df)} crew")
    
    # Test configuration for quick results
    config = GAConfig(
        population_size=20,
        generations=50,
        mutation_rate=0.1,
        crossover_rate=0.8,
        max_time_seconds=10
    )
    
    # Initialize optimizer
    optimizer = GeneticOptimizer(config)
    optimizer.load_data(flights_df, crew_df, dgca_rules)
    
    # Run optimization
    result = optimizer.optimize()
    
    print(f"🔍 Results: {result.get('success', False)}")
    if result.get('success'):
        assignments = result.get('assignments', [])
        kpis = result.get('kpis', {})
        print(f"✅ Generated {len(assignments)} assignments")
        print(f"   Coverage: {kpis.get('coverage_pct', 0):.1f}%")
        print(f"   Fitness: {kpis.get('fitness_score', 0):.1f}")
    else:
        print(f"❌ Error: {result.get('error', 'Unknown error')}")
    
    return result

if __name__ == '__main__':
    test_genetic_fix()