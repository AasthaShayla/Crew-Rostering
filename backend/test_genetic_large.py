#!/usr/bin/env python3
"""
Test script for genetic algorithm with large dataset
"""

import pandas as pd
import json
import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

from genetic_optimizer import GeneticOptimizer, GAConfig

def test_genetic_large_dataset():
    """Test genetic algorithm with large dataset"""
    print("🚀 Testing Genetic Algorithm with Large Dataset")
    print("=" * 50)

    try:
        # Load large dataset
        print("📂 Loading large dataset...")
        flights_df = pd.read_csv('data/flights_large.csv')
        crew_df = pd.read_csv('data/crew_large.csv')

        with open('data/dgca_rules.json', 'r') as f:
            dgca_rules = json.load(f)

        prefs_df = pd.read_csv('data/crew_preferences_large.csv')

        print(f"✅ Loaded {len(flights_df)} flights, {len(crew_df)} crew members")

        # Configure genetic algorithm for large dataset
        ga_config = GAConfig(
            population_size=30,  # Smaller population for testing
            generations=50,      # Fewer generations for testing
            mutation_rate=0.15,
            crossover_rate=0.85,
            max_time_seconds=60  # 1 minute limit for testing
        )

        # Initialize and run genetic algorithm
        optimizer = GeneticOptimizer(ga_config)
        optimizer.load_data(flights_df, crew_df, dgca_rules, prefs_df)

        print("🧬 Starting genetic algorithm optimization...")
        result = optimizer.optimize()

        if result["success"]:
            print("✅ SUCCESS! Genetic algorithm completed successfully")
            print(f"   Coverage: {result['kpis']['coverage_pct']:.1f}%")
            print(f"   Assignments: {len(result['assignments'])}")
            print(f"   Fitness Score: {result['kpis']['fitness_score']:.1f}")

            # Show sample assignments
            print("\n📋 Sample Assignments:")
            for i, assignment in enumerate(result['assignments'][:5]):
                print(f"   {assignment['crew_id']} → {assignment['flight_id']} ({assignment['role']})")

            return True
        else:
            print("❌ Genetic algorithm failed")
            print(f"   Error: {result.get('error', 'Unknown error')}")
            return False

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_genetic_large_dataset()
    if success:
        print("\n🎉 Genetic Algorithm Test PASSED!")
        print("   Ready for production use with large datasets")
    else:
        print("\n💥 Genetic Algorithm Test FAILED!")
        print("   Check the implementation and data files")