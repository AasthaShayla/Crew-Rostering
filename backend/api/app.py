#!/usr/bin/env python3
"""
Flask API server for Crew Rostering Optimization System
Provides endpoints for optimization and what-if scenario analysis
"""

import os
import sys
import json
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import pandas as pd
import math

# Add core module to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'core'))
# Add backend root to path so we can import genetic_optimizer.py
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from loader import load_data
from eligibility import build_eligibility
from constraints import build_model_with_constraints
from objective import add_objective, Weights
from models import Flight, Crew, Disruption, CrewSickness
from .groq_client import parse_disruptions_nl

# Import GA optimizer (with helpful diagnostics if path fails)
try:
    from genetic_optimizer import GeneticOptimizer, GAConfig
except ModuleNotFoundError as e:
    print(f"[IMPORT] Failed to import genetic_optimizer: {e}")
    print(f"[IMPORT] sys.path = {sys.path}")
    raise

app = Flask(__name__)
app.config['SECRET_KEY'] = 'crew-roster-secret-key'
# Broaden CORS to avoid local dev origin mismatches
CORS(app, resources={r"/api/*": {"origins": os.environ.get("CORS_ALLOWED_ORIGINS", "*")}})
socketio = SocketIO(app, cors_allowed_origins=os.environ.get("CORS_ALLOWED_ORIGINS", "*"))

# Final safety-net CORS headers for all /api/* responses (and preflight)
@app.after_request
def add_cors_headers(resp):
    try:
        # Only add for API routes
        if request.path.startswith('/api/'):
            resp.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
            resp.headers['Vary'] = 'Origin'
            resp.headers['Access-Control-Allow-Credentials'] = 'true'
            resp.headers['Access-Control-Allow-Headers'] = request.headers.get(
                'Access-Control-Request-Headers',
                'Content-Type, Authorization, X-Requested-With'
            )
            resp.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'
    except Exception:
        pass
    return resp

# Handle preflight OPTIONS for all /api/* endpoints
@app.route('/api/<path:subpath>', methods=['OPTIONS'])
def api_preflight(subpath):
    resp = jsonify({"success": True})
    resp.status_code = 204
    resp.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
    resp.headers['Vary'] = 'Origin'
    resp.headers['Access-Control-Allow-Credentials'] = 'true'
    resp.headers['Access-Control-Allow-Headers'] = request.headers.get(
        'Access-Control-Request-Headers',
        'Content-Type, Authorization, X-Requested-With'
    )
    resp.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'
    return resp

# Global storage for optimization jobs and results
optimization_jobs: Dict[str, Dict] = {}
current_roster: Dict[str, Any] = {}
baseline_roster: Dict[str, Any] = {}

DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'data')

def get_data_file_path(filename: str) -> str:
    """Get full path to data file"""
    return os.path.join(DATA_PATH, filename)

class OptimizationService:
    """Service class to handle optimization requests"""

    @staticmethod
    def _compute_post_roster_insights(assignments: List[Dict[str, Any]],
                                      crew_records: List[Dict[str, Any]],
                                      flights_records: List[Dict[str, Any]],
                                      dgca_rules: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute post-optimization insights:
          - Overtime breakdown by crew (weekly cap vs assigned hours)
          - Standby recommendations by day/role (based on peak concurrent requirements)
          - Discretion usage indicators (approximation based on FDP bracket, WOCL reduction, rest gaps)
        Inputs are plain dict lists so this works for both GA and OR-Tools outputs.
        """
        from collections import defaultdict
        from datetime import datetime, timedelta

        # ---- Helpers
        def parse_dt(s: str) -> datetime:
            # Handle both ISO and '%Y-%m-%d %H:%M:%S'
            try:
                return datetime.fromisoformat(s)
            except Exception:
                return datetime.strptime(s, '%Y-%m-%d %H:%M:%S')

        def day_of(dt: datetime) -> str:
            return dt.date().isoformat()

        # ---- Build crew caps map
        cap_by_crew = {}
        role_by_crew = {}
        for c in crew_records or []:
            cid = str(c.get('crew_id'))
            cap_by_crew[cid] = float(c.get('weekly_max_duty_hrs') or dgca_rules.get('weekly_max_duty_hrs_default', 65))
            role_by_crew[cid] = c.get('role')

        # ---- Overtime breakdown
        hours_by_crew = defaultdict(float)
        for a in assignments or []:
            cid = str(a.get('crew_id'))
            dur_min = int(a.get('duration_min') or 0)
            hours_by_crew[cid] += dur_min / 60.0

        overtime_by_crew = []
        total_overtime = 0.0
        for cid, hrs in hours_by_crew.items():
            cap = float(cap_by_crew.get(cid, dgca_rules.get('weekly_max_duty_hrs_default', 65)))
            ot = max(0.0, hrs - cap)
            total_overtime += ot
            overtime_by_crew.append({
                "crew_id": cid,
                "role": role_by_crew.get(cid, ""),
                "assigned_hours": round(hrs, 2),
                "weekly_cap_hours": round(cap, 2),
                "overtime_hours": round(ot, 2),
            })
        overtime_by_crew.sort(key=lambda x: x["overtime_hours"], reverse=True)

        # ---- Standby recommendations by day/role (heuristic)
        # Use flights_records with needed_captains/needed_fo/needed_cc to derive concurrency peaks.
        # When not available, fallback to assignments-based concurrency.
        def hour_key(dt: datetime) -> str:
            return dt.strftime('%Y-%m-%d %H:00')

        by_hour_req = defaultdict(lambda: {"Captain": 0, "FO": 0, "CC": 0})
        if flights_records:
            for fr in flights_records:
                try:
                    dep = parse_dt(fr.get("dep_dt"))
                    arr = parse_dt(fr.get("arr_dt"))
                except Exception:
                    continue
                cap_req = int(fr.get("needed_captains", 1) or 1)
                fo_req = int(fr.get("needed_fo", 1) or 1)
                sc_req = int(fr.get("needed_sc", 0) or 0)
                cc_req = int(fr.get("needed_cc", 2) or 2) + sc_req

                cur = dep.replace(minute=0, second=0, microsecond=0)
                end = arr.replace(minute=0, second=0, microsecond=0)
                # Count each hour touched by this flight
                while cur <= end:
                    k = hour_key(cur)
                    by_hour_req[k]["Captain"] += cap_req
                    by_hour_req[k]["FO"] += fo_req
                    by_hour_req[k]["CC"] += cc_req
                    cur += timedelta(hours=1)
        else:
            # Fallback: approximate concurrency using assignments (each assignment equals one seat)
            for a in assignments or []:
                try:
                    dep = parse_dt(a.get("dep_dt"))
                    arr = parse_dt(a.get("arr_dt"))
                except Exception:
                    continue
                role = a.get("role")
                cur = dep.replace(minute=0, second=0, microsecond=0)
                end = arr.replace(minute=0, second=0, microsecond=0)
                while cur <= end:
                    k = hour_key(cur)
                    if role in ("Captain", "First Officer", "FO"):
                        if role == "Captain":
                            by_hour_req[k]["Captain"] += 1
                        else:
                            by_hour_req[k]["FO"] += 1
                    else:
                        by_hour_req[k]["CC"] += 1
                    cur += timedelta(hours=1)

        # Aggregate per-day peaks and suggest ~10% standby rounded up (min 1 when any activity)
        by_day_peak = defaultdict(lambda: {"Captain": 0, "FO": 0, "CC": 0})
        for hk, reqs in by_hour_req.items():
            d = hk.split(' ')[0]
            for role in ("Captain", "FO", "CC"):
                by_day_peak[d][role] = max(by_day_peak[d][role], reqs[role])

        standby_by_day = []
        for day, peaks in sorted(by_day_peak.items()):
            def suggest(peak):
                if peak <= 0:
                    return 0
                return max(1, int(math.ceil(0.1 * peak)))
            standby_by_day.append({
                "day": day,
                "peaks": peaks,
                "suggested_standby": {
                    "Captain": suggest(peaks["Captain"]),
                    "FO": suggest(peaks["FO"]),
                    "CC": suggest(peaks["CC"]),
                }
            })

        # ---- Discretion (unforeseen extensions) indicators (approximation)
        # Use FDP landings bracket and WOCL reduction to flag potential discretion usage.
        # Also detect rest deficits between consecutive flights for each crew.
        # Configs
        fdp_rules = dgca_rules.get("fdp_rules", [
            {"max_flight_time_hrs": 8, "max_fdp_hrs": 12, "max_landings": 6},
            {"max_flight_time_hrs": 11, "max_fdp_hrs": 15, "max_landings": 3},
            {"max_flight_time_hrs": 14, "max_fdp_hrs": 18, "max_landings": 1},
        ])
        fdp_rules_sorted = sorted(fdp_rules, key=lambda r: float(r.get("max_flight_time_hrs", 0)))
        def allowed_landings(ft_hours: float) -> int:
            for r in fdp_rules_sorted:
                if ft_hours <= float(r.get("max_flight_time_hrs", 0)):
                    return int(r.get("max_landings", 6))
            return int(fdp_rules_sorted[-1].get("max_landings", 6))

        wocl_cfg = dgca_rules.get("wocl_window", {"start_local": "02:00", "end_local": "06:00"})
        def hm_to_min(s: str) -> int:
            h, m = [int(x) for x in s.split(":")]
            return h*60 + m
        w_start = hm_to_min(wocl_cfg.get("start_local", "02:00"))
        w_end   = hm_to_min(wocl_cfg.get("end_local", "06:00"))
        def in_wocl(tdt: datetime) -> bool:
            t = tdt.hour*60 + tdt.minute
            if w_start <= w_end:
                return w_start <= t < w_end
            return (t >= w_start) or (t < w_end)
        def overlaps_wocl(dep: datetime, arr: datetime) -> bool:
            if in_wocl(dep) or in_wocl(arr):
                return True
            cur = dep
            while cur < arr:
                if in_wocl(cur):
                    return True
                cur += timedelta(minutes=30)
            return False

        min_rest_hours = float(dgca_rules.get("min_rest_hours_between_duties", 12))
        fdp_red = dgca_rules.get("fdp_wocl_reduction", {"starts_in_wocl_factor": 1.0, "overlaps_wocl_factor": 0.5})
        comp_mult = float(dgca_rules.get("discretion", {}).get("compensatory_rest_multiplier", 2.0))

        # Group assignments per crew per day (chronological)
        by_crew = defaultdict(list)
        for a in assignments or []:
            by_crew[str(a.get("crew_id"))].append(a)
        for cid in list(by_crew.keys()):
            by_crew[cid].sort(key=lambda x: parse_dt(x["dep_dt"]))

        discretion_counters = {
            "landing_bracket_excess_events": 0,
            "wocl_reduction_overcap_events": 0,
            "rest_deficit_events": 0,
            "approx_extension_hours": 0.0,
            "approx_compensatory_rest_hours": 0.0
        }

        # Compute per crew/day aggregates
        for cid, items in by_crew.items():
            # rest deficits between consecutive flights
            for i in range(len(items)-1):
                a = items[i]; b = items[i+1]
                rest_h = (parse_dt(b["dep_dt"]) - parse_dt(a["arr_dt"])).total_seconds()/3600.0
                if rest_h < min_rest_hours - 1e-6:
                    discretion_counters["rest_deficit_events"] += 1
                    discretion_counters["approx_extension_hours"] += (min_rest_hours - rest_h)

            # group by day
            day_map = defaultdict(list)
            for a in items:
                day_map[parse_dt(a["dep_dt"]).date().isoformat()].append(a)
            for day, lst in day_map.items():
                # daily ft hours and landings
                ft_hrs = sum(int(x["duration_min"])/60.0 for x in lst)
                landings = len(lst)
                if landings > allowed_landings(ft_hrs):
                    discretion_counters["landing_bracket_excess_events"] += 1

                # WOCL-based reduction vs daily duty cap by role (approx with FT)
                role = role_by_crew.get(cid, "")
                cap_map = dgca_rules.get("daily_max_duty_hrs", {"Captain": 12, "First Officer": 12, "Cabin": 14})
                cap_key = "Cabin" if role in ("Cabin Crew", "CC") else ("First Officer" if role in ("First Officer", "FO") else "Captain")
                base_cap = float(cap_map.get(cap_key, 12))
                starts = any(in_wocl(parse_dt(x["dep_dt"])) for x in lst)
                ovlp   = any(overlaps_wocl(parse_dt(x["dep_dt"]), parse_dt(x["arr_dt"])) for x in lst)
                w_len = (w_end - w_start) if w_end >= w_start else (24*60 - (w_start - w_end))
                reduction = 0.0
                if starts:
                    reduction = max(reduction, float(fdp_red.get("starts_in_wocl_factor", 1.0)) * (w_len/60.0))
                elif ovlp:
                    reduction = max(reduction, float(fdp_red.get("overlaps_wocl_factor", 0.5)) * (w_len/60.0))
                eff_cap = max(0.0, base_cap - reduction)
                if ft_hrs > eff_cap + 1e-6:
                    discretion_counters["wocl_reduction_overcap_events"] += 1
                    discretion_counters["approx_extension_hours"] += (ft_hrs - eff_cap)

        discretion_counters["approx_compensatory_rest_hours"] = round(comp_mult * discretion_counters["approx_extension_hours"], 2)
        discretion_counters["approx_extension_hours"] = round(discretion_counters["approx_extension_hours"], 2)

        return {
            "overtime": {
                "by_crew": overtime_by_crew,
                "total_overtime_hours": round(total_overtime, 2),
            },
            "standby": {
                "policy": dgca_rules.get("standby", {}),
                "by_day": standby_by_day
            },
            "discretion": discretion_counters
        }

    @staticmethod
    def run_optimization(
        flights_path: str,
        crew_path: str,
        rules_path: str,
        prefs_path: Optional[str] = None,
        disruptions_path: Optional[str] = None,
        sickness_path: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        weights: Optional[Dict] = None,
        max_time: float = 30.0,
        use_genetic: bool = True,
        baseline_assignments: Optional[List[Dict]] = None,
        exclude_crew_ids: Optional[List[str]] = None,
        exclude_flight_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Run optimization and return results"""
        try:
            print(f"🔧 Starting optimization...")
            print(f"   Flights: {flights_path}")
            print(f"   Crew: {crew_path}")
            print(f"   Rules: {rules_path}")
            print(f"   Algorithm: {'Genetic' if use_genetic else 'OR-Tools'}")

            if use_genetic:
                # Use Genetic Algorithm for large-scale optimization
                return OptimizationService._run_genetic_optimization(
                    flights_path, crew_path, rules_path, prefs_path,
                    disruptions_path, sickness_path, start_date, end_date,
                    weights, max_time, baseline_assignments=baseline_assignments,
                    exclude_crew_ids=exclude_crew_ids,
                    exclude_flight_ids=exclude_flight_ids
                )
            else:
                # Fallback to OR-Tools for small problems
                return OptimizationService._run_ortools_optimization(
                    flights_path, crew_path, rules_path, prefs_path,
                    disruptions_path, sickness_path, start_date, end_date,
                    weights, max_time
                )

        except Exception as e:
            print(f"❌ Optimization failed: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    def _run_genetic_optimization(
        flights_path: str,
        crew_path: str,
        rules_path: str,
        prefs_path: Optional[str] = None,
        disruptions_path: Optional[str] = None,
        sickness_path: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        weights: Optional[Dict] = None,
        max_time: float = 30.0,
        baseline_assignments: Optional[List[Dict]] = None,
        exclude_crew_ids: Optional[List[str]] = None,
        exclude_flight_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Run genetic algorithm optimization"""
        print("🧬 Using Genetic Algorithm for optimization...")

        # Load data with date filtering for GA
        print("📂 Loading data...")
        flights_df = pd.read_csv(flights_path)
        crew_df = pd.read_csv(crew_path)
        
        # Filter flights by date range if provided (GA doesn't have native filtering)
        if start_date or end_date:
            flights_df['dep_dt'] = pd.to_datetime(flights_df['dep_dt'])
            start_dt = pd.to_datetime(start_date) if start_date else None
            end_dt = pd.to_datetime(end_date) if end_date else None
            
            mask = pd.Series([True] * len(flights_df))
            if start_dt:
                mask &= flights_df['dep_dt'] >= start_dt
            if end_dt:
                mask &= flights_df['dep_dt'] <= end_dt
            
            flights_df = flights_df[mask].reset_index(drop=True)
            print(f"📅 Filtered to {len(flights_df)} flights in date range")

        # Apply crew sickness (filter out sick crew)
        try:
            if sickness_path and os.path.exists(sickness_path):
                sick_df = pd.read_csv(sickness_path)
                if 'crew_id' in sick_df.columns and not sick_df.empty:
                    sick_ids = set(sick_df['crew_id'].astype(str).tolist())
                    before = len(crew_df)
                    crew_df = crew_df[~crew_df['crew_id'].astype(str).isin(sick_ids)].reset_index(drop=True)
                    print(f"🩺 Applied crew sickness: removed {before - len(crew_df)} crew")
        except Exception as e:
            print(f"⚠️  Failed to apply crew sickness: {e}")

        # Apply flight disruptions (delay or cancellation)
        try:
            if disruptions_path and os.path.exists(disruptions_path):
                dis_df = pd.read_csv(disruptions_path)
                if 'flight_id' in dis_df.columns and not dis_df.empty:
                    flights_df = flights_df.copy()
                    # Normalize datetime columns
                    flights_df['dep_dt'] = pd.to_datetime(flights_df['dep_dt'])
                    flights_df['arr_dt'] = pd.to_datetime(flights_df['arr_dt'])
                    cancelled = 0
                    delayed = 0
                    for _, row in dis_df.iterrows():
                        fid = str(row.get('flight_id', ''))
                        dtype = (str(row.get('disruption_type') or row.get('type') or '')).lower()
                        if not fid:
                            continue
                        mask = flights_df['flight_id'].astype(str) == fid
                        if dtype == 'cancellation':
                            cancelled += mask.sum()
                            flights_df = flights_df[~mask]
                        elif dtype == 'delay':
                            dm = int(row.get('delay_minutes', 0) or 0)
                            if dm != 0 and mask.any():
                                flights_df.loc[mask, 'dep_dt'] = flights_df.loc[mask, 'dep_dt'] + pd.to_timedelta(dm, unit='m')
                                flights_df.loc[mask, 'arr_dt'] = flights_df.loc[mask, 'arr_dt'] + pd.to_timedelta(dm, unit='m')
                                delayed += mask.sum()
                    # Cast back to string format needed by optimizer
                    flights_df['dep_dt'] = flights_df['dep_dt'].dt.strftime('%Y-%m-%d %H:%M:%S')
                    flights_df['arr_dt'] = flights_df['arr_dt'].dt.strftime('%Y-%m-%d %H:%M:%S')
                    print(f"⚠️  Applied disruptions: cancelled={cancelled}, delayed={delayed}")
        except Exception as e:
            print(f"⚠️  Failed to apply flight disruptions: {e}")

        with open(rules_path, 'r') as f:
            dgca_rules = json.load(f)

        prefs_df = None
        if prefs_path and os.path.exists(prefs_path):
            prefs_df = pd.read_csv(prefs_path)

        print(f"✅ Data loaded: {len(flights_df)} flights, {len(crew_df)} crew")

        # Configure genetic algorithm (allow stability knob via weights.w_stability)
        w_stability =  int((weights or {}).get('w_stability', 1200))
        ga_config = GAConfig(
            population_size=50,  # Smaller population for faster convergence
            generations=100,     # Reasonable number of generations
            mutation_rate=0.1,
            crossover_rate=0.8,
            max_time_seconds=max_time,
            w_stability=w_stability
        )

        # Initialize and run genetic algorithm
        optimizer = GeneticOptimizer(ga_config)
        optimizer.load_data(flights_df, crew_df, dgca_rules, prefs_df)
        # Set objective weights from frontend sliders
        try:
            optimizer.set_weights(weights or {})
        except Exception as e:
            print(f"⚠️  Failed to set GA weights: {e}")

        # Apply baseline/stability hints (to reduce unnecessary changes)
        try:
            optimizer.set_baseline(
                baseline_assignments=baseline_assignments or [],
                exclude_crew=set(exclude_crew_ids or []),
                exclude_flights=set(exclude_flight_ids or [])
            )
            print(f"🧭 Baseline loaded: {len(baseline_assignments or [])} assignments, "
                  f"exclude_crew={len(exclude_crew_ids or [])}, exclude_flights={len(exclude_flight_ids or [])}")
        except Exception as e:
            print(f"⚠️  Failed to set baseline in GA: {e}")

        print("🚀 Starting genetic algorithm optimization...")
        result = optimizer.optimize()

        # Attach post-roster insights (standby recommendations, discretion indicators, overtime breakdown)
        try:
            flights_list = result.get("flights", [])
            crew_list = result.get("crew", [])
            insights = OptimizationService._compute_post_roster_insights(
                assignments=result.get("assignments", []),
                crew_records=crew_list,
                flights_records=flights_list,
                dgca_rules=dgca_rules
            )
            result["insights"] = insights
            # Sync KPI total overtime from computed insights
            if "kpis" in result:
                result["kpis"]["total_overtime_hours"] = float(insights["overtime"]["total_overtime_hours"])
        except Exception as e:
            print(f"⚠️  Failed to attach insights (GA): {e}")

        return result

    @staticmethod
    def _run_ortools_optimization(
        flights_path: str,
        crew_path: str,
        rules_path: str,
        prefs_path: Optional[str] = None,
        disruptions_path: Optional[str] = None,
        sickness_path: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        weights: Optional[Dict] = None,
        max_time: float = 30.0
    ) -> Dict[str, Any]:
        """Run OR-Tools optimization (fallback for small problems)"""
        print("🔧 Using OR-Tools for optimization...")

        # Load data
        print("📂 Loading data...")
        data = load_data(
            flights_csv=flights_path,
            crew_csv=crew_path,
            rules_json=rules_path,
            prefs_csv=prefs_path,
            disruptions_csv=disruptions_path,
            sickness_csv=sickness_path,
            start_date=start_date,
            end_date=end_date,
        )
        print(f"✅ Data loaded: {len(data.flights)} flights, {len(data.crew)} crew")

        # Build eligibility
        print("🔍 Building eligibility...")
        elig = build_eligibility(data)
        print(f"✅ Eligibility built: {len(elig.eligible)} assignments")

        # Build model with constraints
        print("🏗️ Building constraint model...")
        artifacts = build_model_with_constraints(bundle=data, elig=elig)
        print(f"✅ Model built with {len(artifacts.x)} decision variables")

        # Add objective function
        print("🎯 Adding objective function...")
        w = Weights()
        if weights:
            w = Weights(**{**w.__dict__, **weights})
        add_objective(bundle=data, elig=elig, art=artifacts, weights=w)
        print(f"✅ Objective function added with weights: OT={w.w_ot}, Fair={w.w_fair}, Pref={w.w_pref}")

        # Solve
        print("⚡ Starting OR-Tools solver...")
        from ortools.sat.python import cp_model
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(max_time)
        solver.parameters.num_search_workers = 4

        status_code = solver.Solve(artifacts.model)
        status = solver.StatusName(status_code)
        print(f"🏁 Solver finished: {status}")

        # Extract results (same as before)
        assignments = []
        for (c_id, f_id, role, s_idx), var in artifacts.x.items():
            if solver.Value(var) == 1:
                f = data.flights_by_id[f_id]
                assignments.append({
                    "crew_id": c_id,
                    "role": role,
                    "flight_id": f_id,
                    "dep_airport": f.dep_airport,
                    "arr_airport": f.arr_airport,
                    "dep_dt": f.dep_dt.isoformat(),
                    "arr_dt": f.arr_dt.isoformat(),
                    "aircraft_type": f.aircraft_type,
                    "duration_min": int((f.arr_dt - f.dep_dt).total_seconds() // 60),
                })

        # Calculate KPIs
        total_slots = len(artifacts.role_slots)
        covered_slots = len(assignments)
        coverage_pct = round(100.0 * covered_slots / max(1, total_slots), 2)

        kpis = {
            "status": status,
            "weights": w.__dict__,
            "time_limit_sec": max_time,
            "total_role_slots": int(total_slots),
            "covered_slots": int(covered_slots),
            "coverage_pct": float(coverage_pct),
            "avg_hours": 0.0,
            "total_overtime_hours": 0.0,
            "days_optimized": data.operating_days,
        }

        # Convert flight objects to JSON-serializable dicts
        flights_data = []
        for f in data.flights:
            flights_data.append({
                "flight_id": f.flight_id,
                "dep_airport": f.dep_airport,
                "arr_airport": f.arr_airport,
                "dep_dt": f.dep_dt.isoformat(),
                "arr_dt": f.arr_dt.isoformat(),
                "aircraft_type": f.aircraft_type,
                "needed_captains": f.needed_captains,
                "needed_fo": f.needed_fo,
                "needed_sc": getattr(f, 'needed_sc', 0),  # Support new senior crew field
                "needed_cc": f.needed_cc,
            })

        # Convert crew objects to JSON-serializable dicts
        crew_data = []
        for c in data.crew:
            crew_data.append({
                "crew_id": c.crew_id,
                "name": c.name,
                "role": c.role,
                "base": c.base,
                "qualified_types": c.qualified_types,
                "weekly_max_duty_hrs": c.weekly_max_duty_hrs,
                "leave_status": c.leave_status,
            })

        result = {
            "success": True,
            "assignments": assignments,
            "kpis": kpis,
            "flights": flights_data,
            "crew": crew_data,
            "operating_days": data.operating_days
        }

        # Attach post-roster insights (standby recommendations, discretion indicators, overtime breakdown)
        try:
            # Recompute overtime-by-crew from assignments (more informative than aggregate)
            with open(rules_path, 'r') as f:
                dgca_rules = json.load(f)
            insights = OptimizationService._compute_post_roster_insights(
                assignments=result.get("assignments", []),
                crew_records=result.get("crew", []),
                flights_records=result.get("flights", []),
                dgca_rules=dgca_rules
            )
            result["insights"] = insights
            # Sync KPI total overtime from computed insights
            if "kpis" in result:
                result["kpis"]["total_overtime_hours"] = float(insights["overtime"]["total_overtime_hours"])
        except Exception as e:
            print(f"⚠️  Failed to attach insights (OR-Tools): {e}")

        return result

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

@app.route('/api/data/flights', methods=['GET'])
def get_flights():
    """Get all flights data"""
    try:
        # Try 6-month data first, fallback to large dataset
        path = get_data_file_path('flights_6month.csv')
        if not os.path.exists(path):
            path = get_data_file_path('flights_large.csv')
        exists = os.path.exists(path)
        print(f"[DATA] GET /api/data/flights -> path={path}, exists={exists}")
        flights_df = pd.read_csv(path)
        flights = flights_df.to_dict('records')
        print(f"[DATA] Flights loaded: {len(flights)}")
        return jsonify({"success": True, "flights": flights})
    except Exception as e:
        print(f"[DATA] Flights load error: {e}")
        return jsonify({"success": False, "error": f"Failed to load flights: {e}"}), 500

@app.route('/api/data/crew', methods=['GET'])
def get_crew():
    """Get all crew data"""
    try:
        # Try 6-month data first, fallback to large dataset
        path = get_data_file_path('crew_6month.csv')
        if not os.path.exists(path):
            path = get_data_file_path('crew_large.csv')
        exists = os.path.exists(path)
        print(f"[DATA] GET /api/data/crew -> path={path}, exists={exists}")
        crew_df = pd.read_csv(path)
        crew = crew_df.to_dict('records')
        print(f"[DATA] Crew loaded: {len(crew)}")
        return jsonify({"success": True, "crew": crew})
    except Exception as e:
        print(f"[DATA] Crew load error: {e}")
        return jsonify({"success": False, "error": f"Failed to load crew: {e}"}), 500

@app.route('/api/disruptions/parse', methods=['POST'])
def parse_disruptions():
    """Parse natural language into structured disruptions (LLM-assisted with fallback)."""
    try:
        data = request.get_json() or {}
        text = (data.get('text') or '').strip()
        if not text:
            return jsonify({"success": False, "error": "Missing 'text' in request body"}), 400

        # Load current flights and crew (6-month preferred, fallback to large)
        flights_path = get_data_file_path('flights_6month.csv')
        if not os.path.exists(flights_path):
            flights_path = get_data_file_path('flights_large.csv')
        crew_path = get_data_file_path('crew_6month.csv')
        if not os.path.exists(crew_path):
            crew_path = get_data_file_path('crew_large.csv')

        flights_df = pd.read_csv(flights_path)
        crew_df = pd.read_csv(crew_path)
        flights = flights_df.to_dict('records')
        crew = crew_df.to_dict('records')

        result = parse_disruptions_nl(text, crew, flights)
        # result schema:
        # {
        #   "success": bool,
        #   "flight_disruptions": [{flight_id,type,delay_minutes,note}],
        #   "crew_sickness": [{crew_id,sick_date,note}],
        #   "error": None | str
        # }
        return jsonify(result), (200 if result.get("success") else 500)

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/optimize', methods=['POST'])
def optimize():
    """Run initial optimization"""
    print("🚀 API /optimize called")
    global current_roster, baseline_roster
    
    job_id = str(uuid.uuid4())
    optimization_jobs[job_id] = {
        "status": "running",
        "created_at": datetime.now().isoformat(),
        "progress": 0
    }
    
    # Emit progress update via WebSocket
    socketio.emit('optimization_progress', {
        'job_id': job_id,
        'status': 'running',
        'progress': 0
    })
    
    try:
        # Get request parameters
        print("📝 Getting request parameters...")
        data = request.get_json() or {}
        weights = data.get('weights', {"w_ot": 100, "w_fair": 10, "w_pref": 1, "w_base": 50, "w_continuity": 75})
        max_time = data.get('max_time', 30)  # Default 30 seconds for quick results
        start_date = data.get('start_date')  # Date range from frontend
        end_date = data.get('end_date')
        print(f"   Weights: {weights}")
        print(f"   Max time: {max_time}")
        print(f"   Date range: {start_date} to {end_date}")
        
        # Use 6-month dataset for genetic algorithm optimization
        flights_path = get_data_file_path('flights_6month.csv')
        crew_path = get_data_file_path('crew_6month.csv')
        rules_path = get_data_file_path('dgca_rules.json')
        prefs_path = get_data_file_path('crew_preferences_6month.csv')
        sickness_path = get_data_file_path('crew_sickness_6month.csv')
        
        # Fallback to large dataset if 6-month data doesn't exist
        if not os.path.exists(flights_path):
            flights_path = get_data_file_path('flights_large.csv')
        if not os.path.exists(crew_path):
            crew_path = get_data_file_path('crew_large.csv')
        if not os.path.exists(prefs_path):
            prefs_path = get_data_file_path('crew_preferences_large.csv')
        if not os.path.exists(sickness_path):
            sickness_path = get_data_file_path('crew_sickness.csv')
        
        print(f"📂 Using optimized dataset:")
        print(f"   Flights: {flights_path} (exists: {os.path.exists(flights_path)})")
        print(f"   Crew: {crew_path} (exists: {os.path.exists(crew_path)})")
        
        # Run optimization with selected dataset
        print("🔧 Starting optimization service...")
        result = OptimizationService.run_optimization(
            flights_path=flights_path,
            crew_path=crew_path,
            rules_path=rules_path,
            prefs_path=prefs_path,
            disruptions_path=get_data_file_path('disruptions.csv'),  # Use original for now
            sickness_path=sickness_path,
            start_date=start_date,  # Use date range from frontend
            end_date=end_date,
            weights=weights,
            max_time=max_time,
            use_genetic=True,  # Use genetic algorithm by default
            baseline_assignments=None,
            exclude_crew_ids=None,
            exclude_flight_ids=None
        )

        # Automatic fallback to OR-Tools if GA fails
        if not result.get("success"):
            print(f"⚠️  Genetic optimizer failed: {result.get('error')}")
            print("🔁 Falling back to OR-Tools solver...")
            result_fallback = OptimizationService.run_optimization(
                flights_path=flights_path,
                crew_path=crew_path,
                rules_path=rules_path,
                prefs_path=prefs_path,
                disruptions_path=get_data_file_path('disruptions.csv'),
                sickness_path=sickness_path,
                start_date=start_date,
                end_date=end_date,
                weights=weights,
                max_time=max_time,
                use_genetic=False,  # OR-Tools fallback
                baseline_assignments=None,
                exclude_crew_ids=None,
                exclude_flight_ids=None
            )
            result = result_fallback
        
        if result["success"]:
            # Store as both current and baseline
            current_roster = result.copy()
            baseline_roster = result.copy()
            
            optimization_jobs[job_id] = {
                "status": "completed",
                "created_at": optimization_jobs[job_id]["created_at"],
                "completed_at": datetime.now().isoformat(),
                "progress": 100,
                "result": result
            }
            
            # Emit completion via WebSocket
            socketio.emit('optimization_progress', {
                'job_id': job_id,
                'status': 'completed',
                'progress': 100,
                'result': result
            })
            
            return jsonify({
                "success": True,
                "job_id": job_id,
                "result": result
            })
        else:
            optimization_jobs[job_id]["status"] = "failed"
            optimization_jobs[job_id]["error"] = result.get("error", "Unknown error")
            
            socketio.emit('optimization_progress', {
                'job_id': job_id,
                'status': 'failed',
                'error': result.get("error", "Unknown error")
            })
            
            return jsonify({
                "success": False,
                "job_id": job_id,
                "error": result.get("error", "Unknown error")
            }), 500
            
    except Exception as e:
        print(f"❌ API optimization error: {e}")
        import traceback
        traceback.print_exc()
        
        optimization_jobs[job_id]["status"] = "failed"
        optimization_jobs[job_id]["error"] = str(e)
        
        socketio.emit('optimization_progress', {
            'job_id': job_id,
            'status': 'failed',
            'error': str(e)
        })
        
        return jsonify({
            "success": False,
            "job_id": job_id,
            "error": str(e)
        }), 500

@app.route('/api/reoptimize', methods=['POST'])
def reoptimize():
    """Run reoptimization with disruptions for what-if scenarios"""
    global current_roster
    
    if not baseline_roster:
        return jsonify({
            "success": False,
            "error": "No baseline optimization found. Run initial optimization first."
        }), 400
    
    job_id = str(uuid.uuid4())
    optimization_jobs[job_id] = {
        "status": "running",
        "created_at": datetime.now().isoformat(),
        "progress": 0,
        "type": "reoptimization"
    }

    # Predefine temp paths so we can clean them up in finally
    temp_disruptions_path = None
    temp_sickness_path = None
    
    try:
        # Get disruptions from request
        data = request.get_json() or {}
        flight_disruptions = data.get('flight_disruptions', [])  # [{flight_id, type, delay_minutes}]
        crew_sickness = data.get('crew_sickness', [])  # [{crew_id, sick_date}]
        
        import tempfile
        import contextlib
        print(f"🔧 Starting what-if reoptimization...")

        # Create temporary CSV for disruptions (Windows-safe)
        if flight_disruptions:
            disruptions_df = pd.DataFrame(flight_disruptions)
            # Add required columns that might be missing
            if 'date' not in disruptions_df.columns:
                disruptions_df['date'] = '2025-09-08'
            if 'dep_airport' not in disruptions_df.columns:
                disruptions_df['dep_airport'] = 'N/A'
            if 'arr_airport' not in disruptions_df.columns:
                disruptions_df['arr_airport'] = 'N/A'
            if 'dep_dt' not in disruptions_df.columns:
                disruptions_df['dep_dt'] = '2025-09-08 00:00:00'
            if 'arr_dt' not in disruptions_df.columns:
                disruptions_df['arr_dt'] = '2025-09-08 01:00:00'
            if 'aircraft_type' not in disruptions_df.columns:
                disruptions_df['aircraft_type'] = 'A320'

            # Make the temp file, close the handle immediately, then write by path
            tf = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='')
            temp_disruptions_path = tf.name
            tf.close()
            disruptions_df.to_csv(temp_disruptions_path, index=False)

        # Create temporary CSV for sickness (Windows-safe)
        if crew_sickness:
            sickness_df = pd.DataFrame(crew_sickness)
            if 'note' not in sickness_df.columns:
                sickness_df['note'] = 'What-if scenario sickness'
            tf2 = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='')
            temp_sickness_path = tf2.name
            tf2.close()
            sickness_df.to_csv(temp_sickness_path, index=False)

        # Build stability hints
        baseline_assignments = baseline_roster.get("assignments", [])
        exclude_crew_ids = [c.get('crew_id') for c in crew_sickness if c.get('crew_id')] if crew_sickness else []
        exclude_flight_ids = [d.get('flight_id') for d in flight_disruptions if d.get('flight_id')] if flight_disruptions else []

        # Run optimization with disruptions using 6-month data
        flights_path = get_data_file_path('flights_6month.csv')
        crew_path = get_data_file_path('crew_6month.csv')
        prefs_path = get_data_file_path('crew_preferences_6month.csv')
        base_sickness_path = get_data_file_path('crew_sickness_6month.csv')
        
        # Fallback to large dataset if 6-month data doesn't exist
        if not os.path.exists(flights_path):
            flights_path = get_data_file_path('flights_large.csv')
        if not os.path.exists(crew_path):
            crew_path = get_data_file_path('crew_large.csv')
        if not os.path.exists(prefs_path):
            prefs_path = get_data_file_path('crew_preferences_large.csv')
        if not os.path.exists(base_sickness_path):
            base_sickness_path = get_data_file_path('crew_sickness.csv')
        
        result = OptimizationService.run_optimization(
            flights_path=flights_path,
            crew_path=crew_path,
            rules_path=get_data_file_path('dgca_rules.json'),
            prefs_path=prefs_path,
            disruptions_path=temp_disruptions_path if temp_disruptions_path else None,
            sickness_path=temp_sickness_path if temp_sickness_path else base_sickness_path,
            start_date=data.get('start_date'),  # Support date range from frontend
            end_date=data.get('end_date'),
            weights=data.get('weights', {"w_ot": 100, "w_fair": 10, "w_pref": 1, "w_base": 50, "w_continuity": 75}),
            max_time=data.get('max_time', 30),
            use_genetic=True,
            baseline_assignments=baseline_assignments,
            exclude_crew_ids=exclude_crew_ids,
            exclude_flight_ids=exclude_flight_ids
        )
        # Automatic fallback to OR-Tools if GA fails
        if not result.get("success"):
            print(f"⚠️  Genetic re-optimizer failed: {result.get('error')}")
            print("🔁 Falling back to OR-Tools solver for reoptimization...")
            result_fallback = OptimizationService.run_optimization(
                flights_path=flights_path,
                crew_path=crew_path,
                rules_path=get_data_file_path('dgca_rules.json'),
                prefs_path=prefs_path,
                disruptions_path=temp_disruptions_path if temp_disruptions_path else None,
                sickness_path=temp_sickness_path if temp_sickness_path else base_sickness_path,
                start_date=data.get('start_date'),
                end_date=data.get('end_date'),
                weights=data.get('weights', {"w_ot": 100, "w_fair": 10, "w_pref": 1, "w_base": 50, "w_continuity": 75}),
                max_time=data.get('max_time', 30),
                use_genetic=False,  # OR-Tools fallback
                baseline_assignments=baseline_assignments,
                exclude_crew_ids=exclude_crew_ids,
                exclude_flight_ids=exclude_flight_ids
            )
            result = result_fallback
        # Automatic fallback to OR-Tools if GA fails
        if not result.get("success"):
            print(f"⚠️  Genetic re-optimizer failed: {result.get('error')}")
            print("🔁 Falling back to OR-Tools solver for reoptimization...")
            result_fallback = OptimizationService.run_optimization(
                flights_path=flights_path,
                crew_path=crew_path,
                rules_path=get_data_file_path('dgca_rules.json'),
                prefs_path=prefs_path,
                disruptions_path=temp_disruptions_path if temp_disruptions_path else None,
                sickness_path=temp_sickness_path if temp_sickness_path else base_sickness_path,
                start_date=data.get('start_date'),
                end_date=data.get('end_date'),
                weights=data.get('weights', {"w_ot": 100, "w_fair": 10, "w_pref": 1, "w_base": 50, "w_continuity": 75}),
                max_time=data.get('max_time', 30),
                use_genetic=False,  # OR-Tools fallback
                baseline_assignments=baseline_assignments,
                exclude_crew_ids=exclude_crew_ids,
                exclude_flight_ids=exclude_flight_ids
            )
            result = result_fallback

        if result["success"]:
            current_roster = result.copy()
            changes = calculate_roster_changes(baseline_roster, current_roster)

            optimization_jobs[job_id] = {
                "status": "completed",
                "created_at": optimization_jobs[job_id]["created_at"],
                "completed_at": datetime.now().isoformat(),
                "progress": 100,
                "result": result,
                "changes": changes,
                "type": "reoptimization"
            }

            socketio.emit('reoptimization_complete', {
                'job_id': job_id,
                'before': baseline_roster,
                'after': current_roster,
                'changes': changes
            })

            return jsonify({
                "success": True,
                "job_id": job_id,
                "before": baseline_roster,
                "after": current_roster,
                "changes": changes
            })
        else:
            return jsonify({
                "success": False,
                "error": result.get("error", "Unknown error")
            }), 500

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    finally:
        # Best-effort cleanup without crashing the response
        import contextlib
        if temp_disruptions_path:
            with contextlib.suppress(FileNotFoundError, PermissionError):
                os.unlink(temp_disruptions_path)
        if temp_sickness_path:
            with contextlib.suppress(FileNotFoundError, PermissionError):
                os.unlink(temp_sickness_path)


def calculate_roster_changes(before: Dict, after: Dict) -> Dict:
    """Calculate changes between two roster assignments"""
    if not before.get("assignments") or not after.get("assignments"):
        return {"crew_changes": [], "flight_changes": [], "summary": {}}
    
    before_assignments = {
        (a["crew_id"], a["flight_id"]): a for a in before["assignments"]
    }
    after_assignments = {
        (a["crew_id"], a["flight_id"]): a for a in after["assignments"]
    }
    
    crew_changes = []
    flight_changes = []
    
    # Find crew that lost assignments
    for key, assignment in before_assignments.items():
        if key not in after_assignments:
            crew_changes.append({
                "type": "removed",
                "crew_id": assignment["crew_id"],
                "flight_id": assignment["flight_id"],
                "role": assignment["role"],
                "flight_details": f"{assignment['dep_airport']}-{assignment['arr_airport']} {assignment['dep_dt']}"
            })
    
    # Find crew that gained assignments  
    for key, assignment in after_assignments.items():
        if key not in before_assignments:
            crew_changes.append({
                "type": "added",
                "crew_id": assignment["crew_id"],
                "flight_id": assignment["flight_id"],
                "role": assignment["role"],
                "flight_details": f"{assignment['dep_airport']}-{assignment['arr_airport']} {assignment['dep_dt']}"
            })
    
    # Calculate summary
    summary = {
        "total_changes": len(crew_changes),
        "assignments_removed": len([c for c in crew_changes if c["type"] == "removed"]),
        "assignments_added": len([c for c in crew_changes if c["type"] == "added"]),
        "coverage_before": before.get("kpis", {}).get("coverage_pct", 0),
        "coverage_after": after.get("kpis", {}).get("coverage_pct", 0)
    }
    
    return {
        "crew_changes": crew_changes,
        "flight_changes": flight_changes,
        "summary": summary
    }

@app.route('/api/jobs/<job_id>', methods=['GET'])
def get_job_status(job_id: str):
    """Get optimization job status"""
    if job_id not in optimization_jobs:
        return jsonify({"success": False, "error": "Job not found"}), 404
    
    return jsonify({
        "success": True,
        "job": optimization_jobs[job_id]
    })

@app.route('/api/roster/current', methods=['GET'])
def get_current_roster():
    """Get current roster assignments"""
    if not current_roster:
        return jsonify({
            "success": False,
            "error": "No current roster available. Run optimization first."
        }), 404
    
    return jsonify({
        "success": True,
        "roster": current_roster
    })

@app.route('/api/roster/baseline', methods=['GET'])
def get_baseline_roster():
    """Get baseline roster assignments"""
    if not baseline_roster:
        return jsonify({
            "success": False,
            "error": "No baseline roster available. Run initial optimization first."
        }), 404
    
    return jsonify({
        "success": True,
        "roster": baseline_roster
    })

# ---- Weather-based delay prediction (Open-Meteo + deterministic fallback) ----
import hashlib
import urllib.request
import urllib.parse

# Minimal airport coordinates map (extend as needed)
AIRPORT_COORDS = {
    "DEL": (28.5562, 77.1000),  # Indira Gandhi Intl, Delhi
    "BOM": (19.0896, 72.8656),  # Chhatrapati Shivaji, Mumbai
    "BLR": (13.1989, 77.7063),  # Kempegowda, Bengaluru
    "HYD": (17.2403, 78.4294),  # Rajiv Gandhi, Hyderabad
    "CCU": (22.6547, 88.4467),  # Netaji Subhas Chandra Bose, Kolkata
    "MAA": (12.9941, 80.1709),  # Chennai
    "PNQ": (18.5793, 73.9089),  # Pune
    "GOI": (15.3800, 73.8310),  # Goa (Dabolim)
    "GOX": (15.7239, 73.7614),  # Mopa, North Goa
    "AMD": (23.0772, 72.6347),  # Ahmedabad
    "COK": (10.1518, 76.4019),  # Kochi
    "TRV": (8.4821, 76.9207),   # Trivandrum
    "LKO": (26.7606, 80.8893),  # Lucknow
    "PAT": (25.5913, 85.0870),  # Patna
    "BBI": (20.2520, 85.8178),  # Bhubaneswar
    "NAG": (21.0922, 79.0472),  # Nagpur
    "GAU": (26.1061, 91.5859),  # Guwahati
    "SXR": (33.9871, 74.7743),  # Srinagar
    "IXC": (30.6735, 76.7885),  # Chandigarh
    "JAI": (26.8242, 75.8122),  # Jaipur
    "BHO": (23.2875, 77.3374),  # Bhopal
    "BDQ": (22.3362, 73.2263),  # Vadodara
    "RPR": (21.1804, 81.7388),  # Raipur
    "VNS": (25.4524, 82.8593),  # Varanasi
    "PAT": (25.5913, 85.0870),  # Patna
}

def _load_flights_df_all():
    """Load flights dataframe (6-month preferred, else large)."""
    try:
        path = get_data_file_path('flights_6month.csv')
        if not os.path.exists(path):
            path = get_data_file_path('flights_large.csv')
        flights_df = pd.read_csv(path)
        # Normalize datetime columns to pandas datetime
        flights_df['dep_dt'] = pd.to_datetime(flights_df['dep_dt'])
        flights_df['arr_dt'] = pd.to_datetime(flights_df['arr_dt'])
        return flights_df
    except Exception as e:
        print(f"[WEATHER] Failed to load flights CSV: {e}")
        raise

def _date_only_str(dt) -> str:
    return pd.to_datetime(dt).date().isoformat()

def _date_range(start_date: str, end_date: str):
    s = pd.to_datetime(start_date).date()
    e = pd.to_datetime(end_date).date()
    cur = s
    from datetime import timedelta as _td
    while cur <= e:
        yield cur.isoformat()
        cur += _td(days=1)

def _safe_http_json(url: str) -> Optional[Dict[str, Any]]:
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            if resp.status != 200:
                return None
            data = resp.read().decode('utf-8')
            return json.loads(data)
    except Exception as e:
        print(f"[WEATHER] HTTP error for {url}: {e}")
        return None

def _open_meteo_series(lat: float, lon: float, start_date: str, end_date: str) -> Optional[Dict[str, Dict[str, float]]]:
    """
    Fetch daily precipitation_probability_max and wind_speed_10m_max for a date range.
    Returns dict keyed by 'YYYY-MM-DD' -> {'precip': int, 'wind': float}
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "precipitation_probability_max,wind_speed_10m_max",
        "timezone": "auto",
        "start_date": start_date,
        "end_date": end_date,
    }
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)
    j = _safe_http_json(url)
    if not j or "daily" not in j:
        return None
    days = j["daily"].get("time", [])
    prec = j["daily"].get("precipitation_probability_max", []) or []
    wind = j["daily"].get("wind_speed_10m_max", []) or []
    out = {}
    for i, d in enumerate(days):
        p = int(prec[i]) if i < len(prec) and prec[i] is not None else 0
        w = float(wind[i]) if i < len(wind) and wind[i] is not None else 0.0
        out[d] = {"precip": p, "wind": w}
    return out

def _risk_from_weather(precip_prob: int, wind_max: float) -> Dict[str, Any]:
    """
    Heuristic mapping to risk level and predicted delay minutes.
    """
    # Simple thresholds tuned for airline operations
    if precip_prob >= 70 or wind_max >= 40:
        return {"level": "high", "predicted_delay_min": 45}
    if precip_prob >= 40 or wind_max >= 30:
        return {"level": "medium", "predicted_delay_min": 20}
    if precip_prob >= 20 or wind_max >= 20:
        return {"level": "low", "predicted_delay_min": 0}
    return {"level": "none", "predicted_delay_min": 0}

def _dummy_risk_for(airport: str, date_str: str) -> Dict[str, Any]:
    """
    Deterministic fallback risk using hash of (airport,date).
    Produces pseudo precip% and wind values -> risk mapping.
    """
    seed = hashlib.sha256(f"{airport}|{date_str}".encode("utf-8")).hexdigest()
    # Convert hex chunks to ints
    precip = int(seed[0:2], 16) % 100          # 0..99
    wind = (int(seed[2:4], 16) % 55) + 5       # 5..59 km/h
    return {
        "precip": precip,
        "wind": wind,
        **_risk_from_weather(precip, wind)
    }

def _build_airport_set_by_day(flights_df: pd.DataFrame, start_date: str, end_date: str) -> Dict[str, set]:
    by_day_airports = {d: set() for d in _date_range(start_date, end_date)}
    # Filter flights in range
    mask = (flights_df['dep_dt'].dt.date >= pd.to_datetime(start_date).date()) & \
           (flights_df['dep_dt'].dt.date <= pd.to_datetime(end_date).date())
    subset = flights_df[mask]
    for _, r in subset.iterrows():
        d = _date_only_str(r['dep_dt'])
        dep = str(r.get('dep_airport') or '').upper()
        arr = str(r.get('arr_airport') or '').upper()
        if dep:
            by_day_airports[d].add(dep)
        if arr:
            by_day_airports[d].add(arr)
    return by_day_airports

def _build_flights_by_day(flights_df: pd.DataFrame, start_date: str, end_date: str) -> Dict[str, list]:
    by_day = {d: [] for d in _date_range(start_date, end_date)}
    mask = (flights_df['dep_dt'].dt.date >= pd.to_datetime(start_date).date()) & \
           (flights_df['dep_dt'].dt.date <= pd.to_datetime(end_date).date())
    subset = flights_df[mask]
    for _, r in subset.iterrows():
        d = _date_only_str(r['dep_dt'])
        by_day[d].append({
            "flight_id": str(r.get("flight_id")),
            "dep_airport": str(r.get("dep_airport")),
            "arr_airport": str(r.get("arr_airport")),
            "dep_dt": pd.to_datetime(r.get("dep_dt")).isoformat(),
            "arr_dt": pd.to_datetime(r.get("arr_dt")).isoformat(),
            "aircraft_type": r.get("aircraft_type"),
        })
    return by_day

def _collect_open_meteo_for_airports(airports: set, start_date: str, end_date: str) -> Dict[str, Dict[str, Dict[str, float]]]:
    """
    For each airport, fetch a daily weather series. Result:
      airport -> date -> {"precip": int, "wind": float}
    Unknown airports will be missing and should use dummy fallback per day.
    """
    out = {}
    for ap in airports:
        coords = AIRPORT_COORDS.get(ap)
        if not coords:
            continue
        lat, lon = coords
        series = _open_meteo_series(lat, lon, start_date, end_date)
        if series:
            out[ap] = series
    return out

def _compute_day_prediction(day: str, flights_of_day: list, airport_weather_series: Dict[str, Dict[str, Dict[str, float]]]) -> Dict[str, Any]:
    # Build per-airport risk for this day
    airport_risks = []
    risk_by_airport = {}
    all_airports = set()
    for f in flights_of_day:
        if f["dep_airport"]:
            all_airports.add(f["dep_airport"].upper())
        if f["arr_airport"]:
            all_airports.add(f["arr_airport"].upper())

    for ap in sorted(all_airports):
        # Prefer API series else dummy
        series = airport_weather_series.get(ap, {})
        metrics = series.get(day)
        if metrics:
            risk_info = _risk_from_weather(int(metrics.get("precip", 0)), float(metrics.get("wind", 0.0)))
            airport_risks.append({
                "airport": ap,
                "precip_probability_max": int(metrics.get("precip", 0)),
                "wind_speed_10m_max": float(metrics.get("wind", 0.0)),
                "risk_level": risk_info["level"],
                "predicted_delay_min": risk_info["predicted_delay_min"]
            })
            risk_by_airport[ap] = risk_info
        else:
            d = _dummy_risk_for(ap, day)
            airport_risks.append({
                "airport": ap,
                "precip_probability_max": int(d["precip"]),
                "wind_speed_10m_max": float(d["wind"]),
                "risk_level": d["level"],
                "predicted_delay_min": d["predicted_delay_min"]
            })
            risk_by_airport[ap] = {"level": d["level"], "predicted_delay_min": d["predicted_delay_min"]}

    # Determine affected flights by airport risk
    affected = []
    for f in flights_of_day:
        dep_r = risk_by_airport.get((f["dep_airport"] or "").upper(), {"level": "none", "predicted_delay_min": 0})
        arr_r = risk_by_airport.get((f["arr_airport"] or "").upper(), {"level": "none", "predicted_delay_min": 0})
        # Order of severity
        levels = {"none": 0, "low": 1, "medium": 2, "high": 3}
        # Choose dominant impact
        side = "DEP" if levels.get(dep_r["level"], 0) >= levels.get(arr_r["level"], 0) else "ARR"
        chosen = dep_r if side == "DEP" else arr_r
        if levels.get(chosen["level"], 0) >= 2:  # medium or high
            affected.append({
                **f,
                "risk_level": chosen["level"],
                "predicted_delay_minutes": chosen["predicted_delay_min"],
                "reason": f"Weather risk at {side} airport ({'dep' if side=='DEP' else 'arr'})"
            })

    # High-risk airport list (medium/high)
    high_risk_airports = [x["airport"] for x in airport_risks if x["risk_level"] in ("medium", "high")]
    return {
        "date": day,
        "airports": airport_risks,
        "affected_flights": affected,
        "affected_count": len(affected),
        "high_risk_airports": high_risk_airports
    }

@app.route('/api/weather/summary', methods=['GET'])
def weather_summary():
    """
    Summary across a date range:
      GET /api/weather/summary?start=YYYY-MM-DD&end=YYYY-MM-DD
    Returns per-day affected flight counts and high-risk airports.
    """
    try:
        start = request.args.get('start')
        end = request.args.get('end')
        # Default to current month if not provided
        if not start or not end:
            today = datetime.now().date()
            start = today.replace(day=1).isoformat()
            # end = last day of month
            from calendar import monthrange
            last_day = monthrange(today.year, today.month)[1]
            end = today.replace(day=last_day).isoformat()

        flights_df = _load_flights_df_all()
        by_day_airports = _build_airport_set_by_day(flights_df, start, end)
        by_day_flights = _build_flights_by_day(flights_df, start, end)

        # Union of airports across range for efficient API calls
        union_airports = set()
        for s in by_day_airports.values():
            union_airports |= s

        airport_series = _collect_open_meteo_for_airports(union_airports, start, end)

        days_out = []
        for d in _date_range(start, end):
            pred = _compute_day_prediction(d, by_day_flights.get(d, []), airport_series)
            days_out.append({
                "date": d,
                "affected_flights": pred["affected_count"],
                "high_risk_airports": pred["high_risk_airports"]
            })

        return jsonify({
            "success": True,
            "start": start,
            "end": end,
            "days": days_out
        })
    except Exception as e:
        print(f"[WEATHER] summary error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/weather/day', methods=['GET'])
def weather_day():
    """
    Detailed prediction for a single day:
      GET /api/weather/day?date=YYYY-MM-DD
    Returns airports risk metrics and list of affected flights with predicted delays.
    """
    try:
        day = request.args.get('date')
        if not day:
            return jsonify({"success": False, "error": "Missing 'date' parameter"}), 400

        flights_df = _load_flights_df_all()
        s = day; e = day
        # Build flights and airports for the day
        by_day_flights = _build_flights_by_day(flights_df, s, e)
        by_day_airports = _build_airport_set_by_day(flights_df, s, e)

        airports = by_day_airports.get(day, set())
        airport_series = _collect_open_meteo_for_airports(airports, s, e)

        pred = _compute_day_prediction(day, by_day_flights.get(day, []), airport_series)
        return jsonify({
            "success": True,
            "date": day,
            "airports": pred["airports"],
            "affected_flights": pred["affected_flights"]
        })
    except Exception as e:
        print(f"[WEATHER] day error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    print('Client connected')
    emit('connected', {'data': 'Connected to crew roster server'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    print('Client disconnected')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    debug = os.environ.get('DEBUG', 'True').lower() == 'true'
    
    print(f"Starting Crew Rostering API server on port {port}")
    print(f"Data path: {DATA_PATH}")
    
    # Allow Werkzeug in dev for Flask-SocketIO
    socketio.run(app, host='0.0.0.0', port=port, debug=debug, allow_unsafe_werkzeug=True)