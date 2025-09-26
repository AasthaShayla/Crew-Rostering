# loader.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple, Optional
from datetime import datetime
import json
import pandas as pd

from models import (
    Flight, Crew, CrewPreference, Disruption, CrewSickness, Rules, role_key
)


# ---------- Public container returned to the solver ----------

@dataclass
class DataBundle:
    flights: List[Flight]
    crew: List[Crew]
    prefs: Dict[str, CrewPreference]        # by crew_id
    rules: Rules
    # Useful derived structures for later (constraints/objective):
    flights_by_id: Dict[str, Flight]
    crew_by_id: Dict[str, Crew]
    # Sickness map: crew_id -> set("YYYY-MM-DD")
    sickness_days: Dict[str, Set[str]]
    # Distinct operating days present in the filtered flight set
    operating_days: List[str]               # e.g., ["2025-09-08", ...]


# ---------- Internal helpers ----------

def _parse_dt(s: str) -> datetime:
    # Expecting ISO-like strings: "YYYY-MM-DD HH:MM:SS"
    return pd.to_datetime(s).to_pydatetime()

def _rules_from_json(d: dict) -> Rules:
    # Convert time windows to minute tuples
    ndw_start = d.get("night_duty_window", {}).get("start_local", "22:00")
    ndw_end   = d.get("night_duty_window", {}).get("end_local", "05:00")
    wocl_start = d.get("wocl_window", {}).get("start_local", "02:00")
    wocl_end   = d.get("wocl_window", {}).get("end_local", "06:00")
    def hm_to_min(hhmm: str) -> int:
        h, m = [int(x) for x in hhmm.split(":")]
        return h*60 + m
    night_tuple = (hm_to_min(ndw_start), hm_to_min(ndw_end))
    wocl_tuple  = (hm_to_min(wocl_start), hm_to_min(wocl_end))

    # Defaults for extended schema (kept lightweight for POC)
    default_fdp_rules = [
        {"max_flight_time_hrs": 8,  "max_fdp_hrs": 12, "max_landings": 6},
        {"max_flight_time_hrs": 11, "max_fdp_hrs": 15, "max_landings": 3},
        {"max_flight_time_hrs": 14, "max_fdp_hrs": 18, "max_landings": 1},
        {"max_flight_time_hrs": 22, "max_fdp_hrs": 22, "max_landings": 1, "ulr": True}
    ]
    default_fdp_wocl = {"starts_in_wocl_factor": 1.0, "overlaps_wocl_factor": 0.5}
    default_ft_limits = {"hours_7_days": 40, "hours_28_days": 115, "hours_90_days": 300, "hours_365_days": 1000}
    default_duty_limits = {"hours_7_days": 65, "hours_28_days": 210}
    default_rest = {
        "daily_rest_min_hours": 12,
        "tz_crossing": [
            {"max_timezones": 3, "min_rest_hours": 12},
            {"max_timezones": 7, "min_rest_hours": 14},
            {"over_timezones": 7, "min_rest_hours": 36}
        ],
        "weekly_rest": {
            "min_hours": 36,
            "require_two_local_nights": True,
            "max_gap_between_weekly_rests_hours": 168
        }
    }
    default_standby = {
        "rostered_notice_min_hours": 12,
        "home_max_hours": 12,
        "airport_max_hours": 8,
        "counting_rules": {
            "airport_counts_to_duty_pct": 100,
            "airport_to_fdp_if_flown_pct": 50,
            "home_callup_over_6h_reduce_fdp_pct": 50,
            "home_no_flight_counts_to_duty_pct": 25
        },
        "post_standby_rest": {
            "after_home_min_hours": 8,
            "after_airport_min_hours": 12
        }
    }
    default_discretion = {
        "ft_extension_max_hours": 1.5,
        "fdp_extension_max_hours": 4,
        "extra_landings_max": 1,
        "extra_night_sequences_limit_per_28_days": 1,
        "compensatory_rest_multiplier": 2.0
    }
    default_composition = {
        "cabin": {
            "min_by_seats": [
                {"min_seats": 10, "max_seats": 50,  "min_cabin_crew": 1},
                {"min_seats": 51, "max_seats": 100, "min_cabin_crew": 2},
                {"min_seats": 101, "step": 50,      "extra_per_step": 1}
            ],
            "defaults_by_aircraft": {"A320": 4, "ATR72": 2},
            "sccm": {"required_if_cc_gt_1": True, "min_sccm_ulh": 2, "experience_min_months": 12}
        },
        "cockpit": {
            "min_standard": {"captains": 1, "first_officers": 1},
            "augmented_threshold_hours": 8.0,
            "augmented_crew_min": 3
        }
    }

    return Rules(
        daily_max_duty_hrs = d.get("daily_max_duty_hrs", {"Captain":10,"First Officer":10,"Cabin":11}),
        weekly_max_duty_hrs_default = int(d.get("weekly_max_duty_hrs_default", 45)),
        min_rest_hours_between_duties = int(d.get("min_rest_hours_between_duties", 12)),
        max_overnight_duties_per_week = int(d.get("max_overnight_duties_per_week", 4)),
        turnaround_minutes = int(d.get("turnaround_minutes", 45)),
        night_duty_window = night_tuple,
        max_consecutive_night_duties = int(d.get("max_consecutive_night_duties", 3)),
        # Extended schema below (with robust defaults)
        wocl_window = wocl_tuple,
        fdp_rules = d.get("fdp_rules", default_fdp_rules),
        fdp_wocl_reduction = d.get("fdp_wocl_reduction", default_fdp_wocl),
        flight_time_limits = d.get("flight_time_limits", default_ft_limits),
        duty_time_limits = d.get("duty_time_limits", default_duty_limits),
        rest_requirements = d.get("rest_requirements", default_rest),
        standby = d.get("standby", default_standby),
        discretion = d.get("discretion", default_discretion),
        composition = d.get("composition", default_composition),
        ulh_ft_threshold_hours = float(d.get("ulh_ft_threshold_hours", 11.0)),
        notes = d.get("notes", "")
    )

def _read_preferences(path: str) -> Dict[str, CrewPreference]:
    try:
        df = pd.read_csv(path)
        # Filter out rows with NaN crew_id
        df = df.dropna(subset=['crew_id'])
    except Exception:
        return {}
    prefs: Dict[str, CrewPreference] = {}
    for _, r in df.iterrows():
        days = set()
        sectors = set()
        
        # Handle requested_days_off - check for NaN first
        days_off_val = r.get("requested_days_off", "")
        if pd.notna(days_off_val) and isinstance(days_off_val, str) and days_off_val.strip():
            days = set([tok.strip() for tok in days_off_val.split("|") if tok.strip()])
            
        # Handle preferred_sectors - check for NaN first  
        sectors_val = r.get("preferred_sectors", "")
        if pd.notna(sectors_val) and isinstance(sectors_val, str) and sectors_val.strip():
            sectors = set([tok.strip() for tok in sectors_val.split("|") if tok.strip()])
            
        prefs[str(r["crew_id"])] = CrewPreference(
            crew_id=str(r["crew_id"]),
            requested_days_off=days,
            preferred_sectors=sectors
        )
    return prefs

def _read_sickness(path: str) -> Dict[str, Set[str]]:
    """Return crew_id -> set of sick dates ('YYYY-MM-DD')."""
    try:
        df = pd.read_csv(path)
    except Exception:
        return {}
    sick_map: Dict[str, Set[str]] = {}
    for _, r in df.iterrows():
        cid = str(r["crew_id"])
        day = str(r["sick_date"])
        sick_map.setdefault(cid, set()).add(day)
    return sick_map

def _read_disruptions(path: str) -> List[Disruption]:
    try:
        df = pd.read_csv(path)
        # Filter out rows with NaN flight_id (comment lines)
        df = df.dropna(subset=['flight_id'])
    except Exception:
        return []
    out: List[Disruption] = []
    for _, r in df.iterrows():
        # Handle NaN values more robustly
        delay_val = r.get("delay_minutes", 0)
        if pd.isna(delay_val):
            delay_val = 0
        
        out.append(
            Disruption(
                flight_id=str(r["flight_id"]),
                disruption_type=str(r["disruption_type"]),
                delay_minutes=int(delay_val),
            )
        )
    return out


# ---------- Main loader ----------

def load_data(
    flights_csv: str,
    crew_csv: str,
    rules_json: str,
    prefs_csv: Optional[str] = None,
    disruptions_csv: Optional[str] = None,
    sickness_csv: Optional[str] = None,
    start_date: Optional[str] = None,    # "YYYY-MM-DD"
    end_date: Optional[str] = None       # "YYYY-MM-DD"
) -> DataBundle:
    """
    Load and normalize all inputs into typed objects for the solver.
    1) Reads flights & applies (optional) date filter.
    2) Applies disruptions: removes cancellations; shifts delayed flights.
    3) Reads crew & filters out leave/training/sick (static). Per-day sickness handled later.
    4) Reads preferences & sickness maps.
    5) Parses rules.
    6) Returns DataBundle with helpful indexes.
    """

    # ---- Flights
    fdf = pd.read_csv(flights_csv)
    # Ensure datetime parsing
    fdf["dep_dt"] = pd.to_datetime(fdf["dep_dt"])
    fdf["arr_dt"] = pd.to_datetime(fdf["arr_dt"])

    # Date filter (optional)
    if start_date:
        sd = pd.to_datetime(start_date).date()
        fdf = fdf[fdf["dep_dt"].dt.date >= sd]
    if end_date:
        ed = pd.to_datetime(end_date).date()
        fdf = fdf[fdf["dep_dt"].dt.date <= ed]
    fdf = fdf.reset_index(drop=True)

    # ---- Disruptions
    disruptions: List[Disruption] = _read_disruptions(disruptions_csv) if disruptions_csv else []
    if disruptions:
        cancels = {d.flight_id for d in disruptions if d.disruption_type.lower() == "cancellation"}
        delays  = {d.flight_id: d.delay_minutes for d in disruptions if d.disruption_type.lower() == "delay"}
        # Remove cancellations
        if cancels:
            fdf = fdf[~fdf["flight_id"].isin(cancels)].copy()
        # Apply delays
        if delays:
            delta = fdf["flight_id"].map(delays).fillna(0).astype(int)
            fdf["dep_dt"] = fdf["dep_dt"] + pd.to_timedelta(delta, unit="m")
            fdf["arr_dt"] = fdf["arr_dt"] + pd.to_timedelta(delta, unit="m")

    # Convert to Flight objects
    flights: List[Flight] = []
    for _, r in fdf.iterrows():
        # Handle optional needed_sc field for backward compatibility
        needed_sc = int(r.get("needed_sc", 0))
        
        flights.append(
            Flight(
                flight_id=str(r["flight_id"]),
                dep_airport=str(r["dep_airport"]),
                arr_airport=str(r["arr_airport"]),
                dep_dt=r["dep_dt"].to_pydatetime(),
                arr_dt=r["arr_dt"].to_pydatetime(),
                aircraft_type=str(r["aircraft_type"]),
                needed_captains=int(r["needed_captains"]),
                needed_fo=int(r["needed_fo"]),
                needed_sc=needed_sc,
                needed_cc=int(r["needed_cc"]),
            )
        )

    flights_by_id = {f.flight_id: f for f in flights}
    operating_days = sorted({f.dep_dt.date().isoformat() for f in flights})

    # ---- Crew
    cdf = pd.read_csv(crew_csv)
    # Filter out static unavailability
    cdf = cdf[~cdf["leave_status"].isin(["On Leave", "Sick", "Training"])].copy()

    crew_list: List[Crew] = []
    for _, r in cdf.iterrows():
        # Optional extended crew fields
        sccm_val = r.get("sccm_certified", False)
        # Normalize to bool
        if isinstance(sccm_val, str):
            sccm_norm = sccm_val.strip().lower() in ("1", "true", "yes", "y", "t")
        else:
            try:
                sccm_norm = bool(int(sccm_val))
            except Exception:
                sccm_norm = bool(sccm_val)
        exp_months = r.get("experience_months", 0)
        try:
            exp_months = int(exp_months) if pd.notna(exp_months) else 0
        except Exception:
            exp_months = 0

        crew_list.append(
            Crew(
                crew_id=str(r["crew_id"]),
                name=str(r["name"]),
                role=str(r["role"]),
                base=str(r["base"]),
                qualified_types=str(r["qualified_types"]),
                weekly_max_duty_hrs=int(r["weekly_max_duty_hrs"]) if pd.notna(r["weekly_max_duty_hrs"]) else None,
                leave_status=str(r["leave_status"]),
                sccm_certified=sccm_norm,
                experience_months=exp_months,
            )
        )
    crew_by_id = {c.crew_id: c for c in crew_list}

    # ---- Preferences & Sickness
    prefs = _read_preferences(prefs_csv) if prefs_csv else {}
    sickness_days = _read_sickness(sickness_csv) if sickness_csv else {}

    # ---- Rules
    with open(rules_json, "r") as f:
        rules_raw = json.load(f)
    rules = _rules_from_json(rules_raw)

    # Done
    return DataBundle(
        flights=flights,
        crew=crew_list,
        prefs=prefs,
        rules=rules,
        flights_by_id=flights_by_id,
        crew_by_id=crew_by_id,
        sickness_days=sickness_days,
        operating_days=operating_days,
    )