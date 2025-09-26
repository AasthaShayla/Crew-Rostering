#!/usr/bin/env python3
"""
Genetic Algorithm Optimizer for Crew Rostering
Scalable solution for large-scale optimization problems
"""

import random
import numpy as np
from typing import List, Dict, Tuple, Set, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import defaultdict
import pandas as pd
import json
import time

@dataclass
class GAConfig:
    """Genetic Algorithm Configuration"""
    population_size: int = 100
    generations: int = 200
    mutation_rate: float = 0.1
    crossover_rate: float = 0.8
    elite_size: int = 5
    tournament_size: int = 5
    max_time_seconds: int = 300
    w_stability: int = 300

@dataclass
class Flight:
    """Flight data structure"""
    flight_id: str
    dep_dt: datetime
    arr_dt: datetime
    dep_airport: str
    arr_airport: str
    aircraft_type: str
    needed_captains: int
    needed_fo: int
    needed_sc: int = 0
    needed_cc: int = 0

@dataclass
class Crew:
    """Crew data structure"""
    crew_id: str
    name: str
    role: str
    base: str
    qualified_types: List[str]
    weekly_max_duty_hrs: int
    available: bool = True
    # Extended fields (DGCA composition rules)
    sccm_certified: bool = False
    experience_months: int = 0

@dataclass
class Assignment:
    """Crew assignment to flight"""
    crew_id: str
    flight_id: str
    role: str

class GeneticOptimizer:
    """Genetic Algorithm for Crew Rostering Optimization"""

    def __init__(self, config: GAConfig = None):
        self.config = config or GAConfig()
        self.flights: List[Flight] = []
        self.crew: List[Crew] = []
        self.dgca_rules: Dict = {}
        self.crew_preferences: Dict = {}

        # Fitness tracking
        self.best_fitness = float('-inf')
        self.best_solution = None
        self.generation_stats = []

        # Stability control
        self.w_stability = self.config.w_stability
        self.baseline_pairs: Set[Tuple[str, str, str]] = set()  # (crew_id, flight_id, role)
        self.exclude_crew: Set[str] = set()
        self.exclude_flights: Set[str] = set()

        # Frontend-controlled objective weights (defaults align with UI)
        self.w_ot: float = 100.0     # overtime penalty weight
        self.w_fair: float = 10.0    # fairness weight (bonus)
        self.w_pref: float = 1.0     # preference penalty weight
        self.w_base: float = 50.0    # base return penalty weight
        self.w_continuity: float = 75.0  # continuity violation penalty weight

    def _parse_qualified_types(self, qualified_types_str) -> List[str]:
        """Parse qualified types handling both pipe (|) and comma (,) separators"""
        if pd.isna(qualified_types_str):
            return []
        
        qualified_str = str(qualified_types_str).strip()
        if not qualified_str:
            return []
        
        # Handle both pipe and comma separators
        if '|' in qualified_str:
            types = [t.strip() for t in qualified_str.split('|') if t.strip()]
        else:
            types = [t.strip() for t in qualified_str.split(',') if t.strip()]
        
        return types

    def load_data(self, flights_df: pd.DataFrame, crew_df: pd.DataFrame,
                  dgca_rules: Dict, crew_preferences: pd.DataFrame = None):
        """Load optimization data"""
        print("📂 Loading data for genetic algorithm...")

        # Load flights
        self.flights = []
        for _, row in flights_df.iterrows():
            flight = Flight(
                flight_id=row['flight_id'],
                dep_dt=datetime.strptime(row['dep_dt'], '%Y-%m-%d %H:%M:%S'),
                arr_dt=datetime.strptime(row['arr_dt'], '%Y-%m-%d %H:%M:%S'),
                dep_airport=row['dep_airport'],
                arr_airport=row['arr_airport'],
                aircraft_type=row['aircraft_type'],
                needed_captains=int(row['needed_captains']),
                needed_fo=int(row['needed_fo']),
                needed_sc=int(row.get('needed_sc', 0)),
                needed_cc=int(row['needed_cc'])
            )
            self.flights.append(flight)

        # Load crew
        self.crew = []
        for _, row in crew_df.iterrows():
            # Extended fields parsing with safe defaults
            sccm_val = row.get('sccm_certified', False)
            if isinstance(sccm_val, str):
                sccm_norm = sccm_val.strip().lower() in ("1", "true", "t", "yes", "y")
            else:
                try:
                    sccm_norm = bool(int(sccm_val))
                except Exception:
                    sccm_norm = bool(sccm_val)
            exp_val = row.get('experience_months', 0)
            try:
                exp_months = int(exp_val) if pd.notna(exp_val) else 0
            except Exception:
                exp_months = 0

            crew_member = Crew(
                crew_id=row['crew_id'],
                name=row['name'],
                role=row['role'],
                base=row['base'],
                qualified_types=self._parse_qualified_types(row['qualified_types']),
                weekly_max_duty_hrs=int(row['weekly_max_duty_hrs']),
                available=row['leave_status'] == 'Available',
                sccm_certified=sccm_norm,
                experience_months=exp_months
            )
            self.crew.append(crew_member)

        self.dgca_rules = dgca_rules

        # Load preferences if available
        if crew_preferences is not None:
            self.crew_preferences = {}
            for _, row in crew_preferences.iterrows():
                # Handle NaN values from empty CSV cells
                days_off_str = row['requested_days_off']
                sectors_str = row['preferred_sectors']

                days_off = set()
                if pd.notna(days_off_str) and isinstance(days_off_str, str) and days_off_str.strip():
                    days_off = set(days_off_str.split(','))

                preferred_sectors = set()
                if pd.notna(sectors_str) and isinstance(sectors_str, str) and sectors_str.strip():
                    preferred_sectors = set(sectors_str.split(','))

                self.crew_preferences[row['crew_id']] = {
                    'days_off': days_off,
                    'preferred_sectors': preferred_sectors
                }

        print(f"✅ Loaded {len(self.flights)} flights, {len(self.crew)} crew members")

        # Build quick lookup maps
        self.flights_by_id = {f.flight_id: f for f in self.flights}
        self.crew_by_id = {c.crew_id: c for c in self.crew}

    def set_weights(self, weights: Dict[str, float]) -> None:
        """Set optimization weights from frontend sliders."""
        try:
            if weights is None:
                return
            if 'w_ot' in weights:
                self.w_ot = float(weights['w_ot'])
            if 'w_fair' in weights:
                self.w_fair = float(weights['w_fair'])
            if 'w_pref' in weights:
                self.w_pref = float(weights['w_pref'])
            if 'w_base' in weights:
                self.w_base = float(weights['w_base'])
            if 'w_continuity' in weights:
                self.w_continuity = float(weights['w_continuity'])
        except Exception as e:
            print(f"⚠️  Failed to set weights: {e} (using defaults w_ot={self.w_ot}, w_fair={self.w_fair}, w_pref={self.w_pref}, w_base={self.w_base}, w_continuity={self.w_continuity})")

    def set_baseline(self, baseline_assignments: List[Dict], exclude_crew: Set[str], exclude_flights: Set[str]) -> None:
        """Set baseline assignments and exclusions for stability-aware optimization."""
        self.exclude_crew = set(exclude_crew or [])
        self.exclude_flights = set(exclude_flights or [])
        pairs: Set[Tuple[str, str, str]] = set()
        for a in baseline_assignments or []:
            c_id = a.get("crew_id")
            f_id = a.get("flight_id")
            role = a.get("role")
            if not c_id or not f_id or not role:
                continue
            if c_id in self.exclude_crew or f_id in self.exclude_flights:
                continue
            pairs.add((c_id, f_id, role))
        self.baseline_pairs = pairs

    def _build_seed_from_baseline(self) -> List['Assignment']:
        """Construct a seed solution from the baseline keeping as many assignments as feasible."""
        seed: List[Assignment] = []
        used_crew: Set[str] = set()
        for (c_id, f_id, role) in self.baseline_pairs:
            if c_id in used_crew:
                continue
            crew = self.crew_by_id.get(c_id)
            flight = self.flights_by_id.get(f_id)
            if not crew or not flight or not crew.available:
                continue
            if role != crew.role:
                continue
            if flight.aircraft_type not in crew.qualified_types:
                continue
            if not self._check_basic_constraints(crew, flight):
                continue
            seed.append(Assignment(c_id, f_id, role))
            used_crew.add(c_id)
        return seed

    def _calculate_stability_bonus(self, solution: List['Assignment']) -> float:
        """Compute fraction of baseline assignments preserved in the given solution."""
        if not self.baseline_pairs:
            return 0.0
        sol_pairs = {(a.crew_id, a.flight_id, a.role) for a in solution}
        kept = len(sol_pairs & self.baseline_pairs)
        return kept / max(1, len(self.baseline_pairs))

    def create_initial_population(self) -> List[List[Assignment]]:
        """Create initial population of solutions"""
        print("🧬 Creating initial population...")

        population = []
        
        # Seed population with baseline-based solution if available
        if self.baseline_pairs:
            try:
                seed = self._build_seed_from_baseline()
                seed = self._repair_solution_continuity(seed)
                population.append(seed)
            except Exception as e:
                print(f"⚠️  Failed to build baseline seed: {e}")

        while len(population) < self.config.population_size:
            solution = self.create_random_solution()
            population.append(solution)

        return population

    def create_random_solution(self) -> List[Assignment]:
        """Create a random feasible solution with relaxed constraints for GA"""
        solution = []
    
        # Group crew by role - handle various role name formats
        captains = [c for c in self.crew if c.role in ('Captain', 'CPT') and c.available]
        first_officers = [c for c in self.crew if c.role in ('First Officer', 'FO') and c.available]
        senior_crew = [c for c in self.crew if c.role in ('Senior Crew', 'Senior Cabin', 'SC') and c.available]
        cabin_crew = [c for c in self.crew if c.role in ('Cabin Crew', 'CC') and c.available]
        
        # Debug output for first solution
        if not hasattr(self, '_debug_printed'):
            print(f"   Crew available: Captains={len(captains)}, FO={len(first_officers)}, SC={len(senior_crew)}, CC={len(cabin_crew)}")
            # Debug qualified types for first few crew members
            if captains:
                print(f"   Sample Captain qualified_types: {captains[0].qualified_types}")
            if cabin_crew:
                print(f"   Sample CC qualified_types: {cabin_crew[0].qualified_types}")
            self._debug_printed = True
    
        assignments_count = 0
        for flight in self.flights:
            # Assign captains - relaxed constraints for GA
            for _ in range(flight.needed_captains):
                eligible_captains = [c for c in captains if flight.aircraft_type in c.qualified_types]
                if eligible_captains:
                    captain = random.choice(eligible_captains)
                    solution.append(Assignment(captain.crew_id, flight.flight_id, 'Captain'))
                    assignments_count += 1
                else:
                    # Debug: why no eligible captains?
                    if not hasattr(self, '_captain_debug_printed'):
                        print(f"   No eligible captains for {flight.aircraft_type} flight {flight.flight_id}")
                        if captains:
                            print(f"   Available captains qualified for: {[c.qualified_types for c in captains[:3]]}")
                        self._captain_debug_printed = True
    
            # Assign first officers - relaxed constraints for GA
            for _ in range(flight.needed_fo):
                eligible_fo = [c for c in first_officers if flight.aircraft_type in c.qualified_types]
                if eligible_fo:
                    fo = random.choice(eligible_fo)
                    solution.append(Assignment(fo.crew_id, flight.flight_id, 'First Officer'))
                    assignments_count += 1
    
            # Assign senior cabin crew - relaxed constraints for GA
            for _ in range(getattr(flight, 'needed_sc', 0)):
                eligible_sc = [c for c in senior_crew if flight.aircraft_type in c.qualified_types]
                if eligible_sc:
                    sc = random.choice(eligible_sc)
                    solution.append(Assignment(sc.crew_id, flight.flight_id, 'Senior Crew'))
                    assignments_count += 1
    
            # Assign cabin crew - relaxed constraints for GA
            for _ in range(flight.needed_cc):
                eligible_cc = [c for c in cabin_crew if flight.aircraft_type in c.qualified_types]
                if eligible_cc:
                    cc = random.choice(eligible_cc)
                    solution.append(Assignment(cc.crew_id, flight.flight_id, 'Cabin Crew'))
                    assignments_count += 1
        
        # Debug output for first solution
        if not hasattr(self, '_solution_debug_printed'):
            print(f"   Generated {assignments_count} assignments for {len(self.flights)} flights")
            self._solution_debug_printed = True
    
        # Enforce location continuity by repairing invalid sequences
        solution = self._repair_solution_continuity(solution)
        return solution

    def _check_basic_constraints(self, crew: Crew, flight: Flight) -> bool:
        """Check basic eligibility constraints"""
        # Qualification check
        if flight.aircraft_type not in crew.qualified_types:
            return False

        # Base proximity (simplified - crew can work flights from their base or nearby)
        # In real implementation, you'd check actual distance/logistics
        return True

    def evaluate_fitness(self, solution: List[Assignment]) -> float:
        """Evaluate solution fitness"""
        if not solution:
            return float('-inf')

        try:
            # Calculate various fitness components
            coverage_score = self._calculate_coverage_score(solution)
            
            # For initial debugging, focus primarily on coverage
            if coverage_score <= 0:
                return float('-inf')
            
            # Simplified fitness calculation for GA success
            overtime_penalty = self._calculate_overtime_penalty(solution)
            fairness_score = self._calculate_fairness_score(solution)
            
            # Calculate continuity and base return penalties (simplified)
            continuity_penalty, base_return_penalty = self._calculate_continuity_and_base_penalties(solution)

            # Stability bonus w.r.t. baseline
            stability_bonus = self._calculate_stability_bonus(solution)

            # Simplified weighted fitness function focusing on coverage
            fitness = (
                1000 * coverage_score                        # Coverage is most important
                - 0.1 * self.w_ot * overtime_penalty         # Reduced overtime penalty
                + 0.1 * self.w_fair * fairness_score         # Reduced fairness bonus
                - 0.01 * self.w_continuity * continuity_penalty  # Light continuity penalty
                - 0.01 * self.w_base * base_return_penalty    # Light base return penalty
                + self.w_stability * stability_bonus         # Reward keeping prior assignments
            )

            return max(fitness, 0.1)  # Ensure positive fitness for valid solutions
            
        except Exception as e:
            # Debug output for fitness calculation errors
            print(f"⚠️  Fitness calculation error for solution with {len(solution)} assignments: {e}")
            import traceback
            traceback.print_exc()
            return float('-inf')

    def _calculate_coverage_score(self, solution: List[Assignment]) -> float:
        """Calculate flight coverage score (0-1)"""
        total_required_positions = sum(
            f.needed_captains + f.needed_fo + getattr(f, 'needed_sc', 0) + f.needed_cc
            for f in self.flights
        )

        covered_positions = len(solution)
        return min(1.0, covered_positions / total_required_positions)

    def _calculate_overtime_penalty(self, solution: List[Assignment]) -> float:
        """Calculate overtime penalty"""
        crew_hours = {}
        for assignment in solution:
            crew = next(c for c in self.crew if c.crew_id == assignment.crew_id)
            flight = next(f for f in self.flights if f.flight_id == assignment.flight_id)

            flight_hours = (flight.arr_dt - flight.dep_dt).total_seconds() / 3600
            crew_hours[assignment.crew_id] = crew_hours.get(assignment.crew_id, 0) + flight_hours

        overtime = 0
        for crew_id, hours in crew_hours.items():
            crew = next(c for c in self.crew if c.crew_id == crew_id)
            if hours > crew.weekly_max_duty_hrs:
                overtime += hours - crew.weekly_max_duty_hrs

        return overtime

    def _calculate_fairness_score(self, solution: List[Assignment]) -> float:
        """Calculate fairness score (how evenly work is distributed)"""
        crew_hours = {}
        for assignment in solution:
            crew = next(c for c in self.crew if c.crew_id == assignment.crew_id)
            flight = next(f for f in self.flights if f.flight_id == assignment.flight_id)

            flight_hours = (flight.arr_dt - flight.dep_dt).total_seconds() / 3600
            crew_hours[assignment.crew_id] = crew_hours.get(assignment.crew_id, 0) + flight_hours

        if not crew_hours:
            return 0

        hours_list = list(crew_hours.values())
        mean_hours = np.mean(hours_list)
        std_hours = np.std(hours_list)

        # Fairness score: lower standard deviation is better
        if mean_hours == 0:
            return 1.0
        else:
            # Normalize fairness score (0-1, higher is better)
            return max(0, 1.0 - (std_hours / mean_hours))

    def _calculate_preference_penalty(self, solution: List[Assignment]) -> float:
        """Calculate preference violation penalty"""
        penalty = 0

        for assignment in solution:
            if assignment.crew_id in self.crew_preferences:
                prefs = self.crew_preferences[assignment.crew_id]
                flight = next(f for f in self.flights if f.flight_id == assignment.flight_id)

                # Day-off violation
                flight_date = flight.dep_dt.strftime('%Y-%m-%d')
                if flight_date in prefs['days_off']:
                    penalty += 10  # High penalty for working on day off

                # Preferred sector bonus (negative penalty = bonus)
                sector = f"{flight.dep_airport}-{flight.arr_airport}"
                if sector in prefs['preferred_sectors']:
                    penalty -= 1  # Small bonus for preferred sector

        return penalty

    def _repair_solution_continuity(self, solution: List[Assignment]) -> List[Assignment]:
        """
        Hard-repair operator: enforce location continuity for ALL crew.
        If a crew has multiple flights, we keep a time-ordered sequence where
        each next flight's departure matches the previous flight's arrival.
        Any violating assignment is dropped.
        """
        if not solution:
            return solution
        
        # Map (crew, flight) -> assignments (could be 1 per role-seat)
        by_cf: Dict[Tuple[str, str], List[Assignment]] = defaultdict(list)
        for a in solution:
            by_cf[(a.crew_id, a.flight_id)].append(a)
        
        # Build per-crew unique flights with datetime for ordering
        flights_for_crew: Dict[str, List[Flight]] = defaultdict(list)
        seen: Set[Tuple[str, str]] = set()
        for a in solution:
            key = (a.crew_id, a.flight_id)
            if key in seen:
                continue
            seen.add(key)
            f = self.flights_by_id.get(a.flight_id)
            if f:
                flights_for_crew[a.crew_id].append(f)
        
        kept_pairs: Set[Tuple[str, str]] = set()
        for crew_id, flist in flights_for_crew.items():
            flist.sort(key=lambda f: f.dep_dt)
            last_arr: Optional[str] = None
            for f in flist:
                # Allow any first flight; enforce continuity for subsequent ones
                if last_arr is None or f.dep_airport == last_arr:
                    kept_pairs.add((crew_id, f.flight_id))
                    last_arr = f.arr_airport
                else:
                    # Skip this flight for this crew due to continuity break
                    continue
        
        # Rebuild repaired solution keeping only continuous pairs
        repaired: List[Assignment] = []
        for (cid, fid), assigns in by_cf.items():
            if (cid, fid) in kept_pairs:
                repaired.extend(assigns)
        return repaired

    def _calculate_continuity_and_base_penalties(self, solution: List[Assignment]) -> Tuple[float, float]:
        """Calculate continuity and base return penalties separately for weighted fitness"""
        continuity_penalty = 0
        base_return_penalty = 0
        
        # Build crew schedules
        crew_schedules: Dict[str, List[Flight]] = {}
        for assignment in solution:
            crew_id = assignment.crew_id
            flight = self.flights_by_id.get(assignment.flight_id)
            if flight:
                crew_schedules.setdefault(crew_id, []).append(flight)
        
        # Sort each crew's assignments
        for crew_id, flights in crew_schedules.items():
            flights.sort(key=lambda f: f.dep_dt)
        
        # Continuity violations (heavy penalty per violation to strongly enforce location continuity)
        for crew_id, flights in crew_schedules.items():
            for i in range(1, len(flights)):
                if flights[i-1].arr_airport != flights[i].dep_airport:
                    continuity_penalty += 100  # Heavy penalty per violation
        
        # Base return violations (end day away from base)
        for crew_id, flights in crew_schedules.items():
            crew = self.crew_by_id.get(crew_id)
            if not crew:
                continue
            crew_base = crew.base
            
            daily_groups = {}
            for f in flights:
                day = f.dep_dt.date().isoformat()
                daily_groups.setdefault(day, []).append(f)
            
            for day, day_flights in daily_groups.items():
                if day_flights:
                    last_flight = max(day_flights, key=lambda f: f.arr_dt)
                    if last_flight.arr_airport != crew_base:
                        base_return_penalty += 1  # Penalty per day ended away
        
        return continuity_penalty, base_return_penalty

    def _calculate_constraint_penalty(self, solution: List[Assignment]) -> float:
        """Calculate other hard constraint violations (rest, FDP, WOCL, etc.)"""
        penalty = 0
        
        # Build crew schedules for rest and FDP analysis
        crew_schedules: Dict[str, List[Flight]] = {}
        for assignment in solution:
            crew_id = assignment.crew_id
            flight = self.flights_by_id.get(assignment.flight_id)
            if flight:
                crew_schedules.setdefault(crew_id, []).append(flight)
        
        # Sort each crew's assignments
        for crew_id, flights in crew_schedules.items():
            flights.sort(key=lambda f: f.dep_dt)
        
        # ---------------- Rest requirements ----------------
        min_rest_hours = float(self.dgca_rules.get('min_rest_hours_between_duties', 12))
        for crew_id, flights in crew_schedules.items():
            for i in range(1, len(flights)):
                rest_time = (flights[i].dep_dt - flights[i-1].arr_dt).total_seconds() / 3600
                if rest_time < min_rest_hours:
                    penalty += 100  # Heavy penalty for rest violation

        # ---------------- Composition: SCCM required for flights with cabin crew ----------------
        assgn_by_flight: Dict[str, List[Assignment]] = {}
        for a in solution:
            assgn_by_flight.setdefault(a.flight_id, []).append(a)

        # SCCM config
        comp = self.dgca_rules.get("composition", {}) or {}
        cabin_cfg = comp.get("cabin", {}) if isinstance(comp, dict) else {}
        sccm_cfg = cabin_cfg.get("sccm", {}) if isinstance(cabin_cfg, dict) else {}
        exp_min = int(sccm_cfg.get("experience_min_months", 12)) if isinstance(sccm_cfg, dict) else 12
        ulh_thr = float(self.dgca_rules.get("ulh_ft_threshold_hours", 11.0))

        for flt in self.flights:
            cc_needed = int(flt.needed_cc) + int(getattr(flt, 'needed_sc', 0))
            if cc_needed <= 1:
                continue
            cc_assigned = [a for a in assgn_by_flight.get(flt.flight_id, []) if a.role in ('Cabin Crew', 'Senior Crew')]
            if len(cc_assigned) < cc_needed:
                penalty += 200 * (cc_needed - len(cc_assigned))
                continue
            # SCCM requirement: at least 2 for flights with 5+ cabin crew
            required_sccm = 2 if cc_needed >= 5 else 1
            sccm_count = 0
            for a in cc_assigned:
                cobj = self.crew_by_id.get(a.crew_id)
                if cobj and cobj.sccm_certified and cobj.experience_months >= exp_min:
                    sccm_count += 1
            if sccm_count < required_sccm:
                penalty += 200 * (required_sccm - sccm_count)

        # ---------------- FDP and other constraints (simplified for GA) ----------------
        # For GA, use simplified FDP checks
        for crew_id, flights in crew_schedules.items():
            # Daily landings limit
            day_map = defaultdict(list)
            for f in flights:
                day = f.dep_dt.date().isoformat()
                day_map[day].append(f)
            
            for day, day_flights in day_map.items():
                if len(day_flights) > 4:  # Simplified: max 4 landings per day
                    penalty += 50 * (len(day_flights) - 4)

        # ---------------- Cumulative limits (simplified) ----------------
        for crew_id, flights in crew_schedules.items():
            total_hours = sum((f.arr_dt - f.dep_dt).total_seconds() / 3600 for f in flights)
            if total_hours > 100:  # Weekly cap approximation
                penalty += 10 * (total_hours - 100)

        return penalty

    def tournament_selection(self, population: List[List[Assignment]],
                           fitness_scores: List[float]) -> List[Assignment]:
        """Tournament selection"""
        selected = []

        for _ in range(self.config.tournament_size):
            idx = random.randint(0, len(population) - 1)
            selected.append((population[idx], fitness_scores[idx]))

        # Return the best from tournament
        return max(selected, key=lambda x: x[1])[0]

    def crossover(self, parent1: List[Assignment], parent2: List[Assignment]) -> Tuple[List[Assignment], List[Assignment]]:
        """Crossover operation"""
        if random.random() > self.config.crossover_rate:
            return parent1.copy(), parent2.copy()

        # Single point crossover
        if len(parent1) > 1 and len(parent2) > 1:
            point = random.randint(1, min(len(parent1), len(parent2)) - 1)

            child1 = parent1[:point] + parent2[point:]
            child2 = parent2[:point] + parent1[point:]
        else:
            child1, child2 = parent1.copy(), parent2.copy()

        return child1, child2

    def mutate(self, solution: List[Assignment]) -> List[Assignment]:
        """Mutation operation"""
        mutated = solution.copy()

        for i in range(len(mutated)):
            if random.random() < self.config.mutation_rate:
                # Randomly change crew assignment for this position
                assignment = mutated[i]
                flight = next(f for f in self.flights if f.flight_id == assignment.flight_id)

                # Find alternative crew for same role
                available_crew = [c for c in self.crew
                                if c.role == assignment.role
                                and c.available
                                and flight.aircraft_type in c.qualified_types
                                and c.crew_id != assignment.crew_id]

                if available_crew:
                    new_crew = random.choice(available_crew)
                    mutated[i] = Assignment(new_crew.crew_id, assignment.flight_id, assignment.role)

        # Repair to enforce location continuity hard-constraint
        mutated = self._repair_solution_continuity(mutated)
        return mutated

    def optimize(self) -> Dict:
        """Run genetic algorithm optimization"""
        print("🚀 Starting Genetic Algorithm Optimization")
        print(f"   Population: {self.config.population_size}")
        print(f"   Generations: {self.config.generations}")
        print(f"   Flights: {len(self.flights)}, Crew: {len(self.crew)}")

        start_time = time.time()

        # Initialize population
        population = self.create_initial_population()
        
        # Validate population has valid solutions
        valid_solutions = [sol for sol in population if sol]
        if not valid_solutions:
            print("❌ No valid solutions generated in initial population!")
            return {"success": False, "error": "Failed to generate any valid assignments"}
        
        fitness_scores = [self.evaluate_fitness(sol) for sol in population]
        
        # Check if we have any valid fitness scores
        valid_fitness = [f for f in fitness_scores if f > float('-inf')]
        if not valid_fitness:
            print("❌ No valid fitness scores calculated!")
            return {"success": False, "error": "Failed to calculate valid fitness scores"}

        # Track best solution
        best_idx = np.argmax(fitness_scores)
        self.best_solution = population[best_idx]
        self.best_fitness = fitness_scores[best_idx]

        print(f"   Initial Best Fitness: {self.best_fitness:.1f}")
        print(f"   Valid solutions in population: {len(valid_solutions)}")
        for generation in range(self.config.generations):
            if time.time() - start_time > self.config.max_time_seconds:
                print("⏰ Time limit reached")
                break

            # Create new population
            new_population = []

            # Elitism - keep best solutions
            elite_indices = np.argsort(fitness_scores)[-self.config.elite_size:]
            for idx in elite_indices:
                new_population.append(population[idx])

            # Generate rest of population
            while len(new_population) < self.config.population_size:
                # Selection
                parent1 = self.tournament_selection(population, fitness_scores)
                parent2 = self.tournament_selection(population, fitness_scores)

                # Crossover
                child1, child2 = self.crossover(parent1, parent2)

                # Mutation
                child1 = self.mutate(child1)
                child2 = self.mutate(child2)

                new_population.extend([child1, child2])

            # Trim to population size
            population = new_population[:self.config.population_size]
            fitness_scores = [self.evaluate_fitness(sol) for sol in population]

            # Update best solution
            current_best_idx = np.argmax(fitness_scores)
            current_best_fitness = fitness_scores[current_best_idx]

            if current_best_fitness > self.best_fitness:
                self.best_fitness = current_best_fitness
                self.best_solution = population[current_best_idx]

            # Progress reporting
            if generation % 20 == 0:
                print(f"   Gen {generation}: Best Fitness = {self.best_fitness:.1f}")

        elapsed_time = time.time() - start_time
        print(f"   Optimization completed in {elapsed_time:.1f} seconds")
        
        # Final validation
        if not self.best_solution:
            print("❌ No best solution found after optimization!")
            return {"success": False, "error": "No solution found after optimization"}
            
        print(f"   Final solution has {len(self.best_solution)} assignments")
        return self.format_results()

    def format_results(self) -> Dict:
        """Format optimization results"""
        if not self.best_solution:
            return {"success": False, "error": "No solution found"}

        # Convert assignments to API format
        assignments = []
        for assignment in self.best_solution:
            flight = next(f for f in self.flights if f.flight_id == assignment.flight_id)
            crew = next(c for c in self.crew if c.crew_id == assignment.crew_id)

            assignments.append({
                "crew_id": assignment.crew_id,
                "role": assignment.role,
                "flight_id": assignment.flight_id,
                "dep_airport": flight.dep_airport,
                "arr_airport": flight.arr_airport,
                "dep_dt": flight.dep_dt.isoformat(),
                "arr_dt": flight.arr_dt.isoformat(),
                "aircraft_type": flight.aircraft_type,
                "duration_min": int((flight.arr_dt - flight.dep_dt).total_seconds() // 60),
            })

        # Calculate KPIs
        total_slots = sum(
            f.needed_captains + f.needed_fo + getattr(f, 'needed_sc', 0) + f.needed_cc
            for f in self.flights
        )
        covered_slots = len(assignments)
        coverage_pct = round(100.0 * covered_slots / max(1, total_slots), 2)

        # Calculate crew utilization
        crew_hours = {}
        for assignment in self.best_solution:
            flight = next(f for f in self.flights if f.flight_id == assignment.flight_id)
            flight_hours = (flight.arr_dt - flight.dep_dt).total_seconds() / 3600
            crew_hours[assignment.crew_id] = crew_hours.get(assignment.crew_id, 0) + flight_hours

        if crew_hours:
            avg_hours = sum(crew_hours.values()) / len(crew_hours)
            total_overtime = sum(max(0, hours - next(c for c in self.crew if c.crew_id == crew_id).weekly_max_duty_hrs)
                               for crew_id, hours in crew_hours.items())
        else:
            avg_hours = 0
            total_overtime = 0

        return {
            "success": True,
            "assignments": assignments,
            "kpis": {
                "status": "OPTIMAL" if coverage_pct >= 95 else "FEASIBLE",
                "weights": {
                    "w_ot": self.w_ot, "w_fair": self.w_fair, "w_pref": self.w_pref,
                    "w_base": self.w_base, "w_continuity": self.w_continuity, "w_stability": self.w_stability
                },
                "time_limit_sec": self.config.max_time_seconds,
                "total_role_slots": total_slots,
                "covered_slots": covered_slots,
                "coverage_pct": coverage_pct,
                "avg_hours": float(avg_hours),
                "total_overtime_hours": float(total_overtime),
                "days_optimized": 7,
                "fitness_score": float(self.best_fitness)
            },
            "flights": [{
                "flight_id": f.flight_id,
                "dep_airport": f.dep_airport,
                "arr_airport": f.arr_airport,
                "dep_dt": f.dep_dt.isoformat(),
                "arr_dt": f.arr_dt.isoformat(),
                "aircraft_type": f.aircraft_type,
                "needed_captains": f.needed_captains,
                "needed_fo": f.needed_fo,
                "needed_sc": getattr(f, 'needed_sc', 0),
                "needed_cc": f.needed_cc,
            } for f in self.flights],
            "crew": [{
                "crew_id": c.crew_id,
                "name": c.name,
                "role": c.role,
                "base": c.base,
                "qualified_types": c.qualified_types,
                "weekly_max_duty_hrs": c.weekly_max_duty_hrs,
                "leave_status": "Available" if c.available else "Unavailable",
            } for c in self.crew],
            "operating_days": [
                "2025-09-08", "2025-09-09", "2025-09-10", "2025-09-11",
                "2025-09-12", "2025-09-13", "2025-09-14"
            ]
        }