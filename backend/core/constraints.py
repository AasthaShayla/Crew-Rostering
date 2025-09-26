# constraints.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple, List
import math
from datetime import timedelta

from ortools.sat.python import cp_model

from models import Rules, role_key
from loader import DataBundle
from eligibility import EligibilityBundle, RoleSlot


# ---------------- Public structures we return ----------------

@dataclass
class ModelArtifacts:
    """Everything the next stages (objective/solve) need."""
    model: cp_model.CpModel
    # Decision variables: (crew_id, flight_id, role, slot_idx) -> BoolVar
    x: Dict[Tuple[str, str, str, int], cp_model.IntVar]
    # Optional interval variables for NoOverlap (per-crew lists)
    intervals_by_crew: Dict[str, List[cp_model.IntervalVar]]
    # Totals & caps
    minutes_total_by_crew: Dict[str, cp_model.IntVar]          # total minutes per crew
    minutes_by_crew_day: Dict[Tuple[str, str], cp_model.IntVar]# per-crew, per-day minutes
    overtime_by_crew: Dict[str, cp_model.IntVar]               # >= total - weekly_cap*60
    # Base return penalty variables for pilots
    base_penalty_vars: Dict[str, cp_model.IntVar]              # pilot base return penalties
    # Handy references
    role_slots: List[RoleSlot]


# ---------------- Core builder ----------------

def build_model_with_constraints(
    bundle: DataBundle,
    elig: EligibilityBundle,
) -> ModelArtifacts:
    """
    Create a CP-SAT model with:
      - decision vars x[c,f,r,s] and optional intervals
      - Coverage constraints
      - NoOverlap per crew (with turnaround padding)
      - Daily caps per crew (by role)
      - Weekly cap via overtime variables (non-negative)
    No objective yet — added later in objective.py.
    """
    model = cp_model.CpModel()
    rules: Rules = bundle.rules

    # --- Decision vars ---
    x: Dict[Tuple[str, str, str, int], cp_model.IntVar] = {}
    intervals_by_crew: Dict[str, List[cp_model.IntervalVar]] = {}

    # Cache flight timestamps (seconds) and minutes
    # (We already have per-flight minutes in elig.minutes_by_flight.)
    def to_ts(dt) -> int:
        # OR-Tools IntervalVar expects ints (seconds).
        return int(dt.timestamp())

    # Build optional intervals per eligible assignment to use AddNoOverlap
    for (c_id, f_id, role, slot_idx) in elig.eligible:
        f = bundle.flights_by_id[f_id]
        var = model.NewBoolVar(f"x[{c_id},{f_id},{role},{slot_idx}]")
        x[(c_id, f_id, role, slot_idx)] = var

        start = to_ts(f.dep_dt)
        end   = to_ts(f.arr_dt)
        size_sec = (end - start) + rules.turnaround_minutes * 60  # pad end by turnaround

        iv = model.NewOptionalIntervalVar(
            start, size_sec, start + size_sec, var,
            f"iv[{c_id},{f_id},{role},{slot_idx}]"
        )
        intervals_by_crew.setdefault(c_id, []).append(iv)

    # --- Coverage constraints ---
    # For each role-slot (f, r, s), sum of x over crews must equal 1.
    for rs in elig.role_slots:
        model.Add(
            sum(
                x[(c, f, r, s)]
                for (c, f, r, s) in x
                if f == rs.flight_id and r == rs.role and s == rs.slot_index
            ) == 1
        )

    # --- At-most-one slot per (crew, flight) ---
    # Prevent a single crew from occupying multiple seats on the same flight (any role/slot).
    for c_id in {c.crew_id for c in bundle.crew}:
        f_ids_for_c = {f for (cc, f, r, s) in x if cc == c_id}
        for f_id in f_ids_for_c:
            model.Add(
                sum(
                    x[(cc, ff, rr, ss)]
                    for (cc, ff, rr, ss) in x
                    if cc == c_id and ff == f_id
                ) <= 1
            )

    # --- Composition constraints: SCCM presence for cabin crew ---
    # If a flight requires more than 1 cabin crew (CC + SC), ensure at least one SCCM-qualified crew is assigned.
    # Senior Crew are automatically SCCM qualified, so include both SC and SCCM-certified CC.
    # For ULH flights (duration > ulh_ft_threshold_hours), ensure at least 2 SCCMs (per rule).
    sccm_cfg = rules.composition.get("cabin", {}).get("sccm", {}) if hasattr(rules, "composition") else {}
    exp_min = int(sccm_cfg.get("experience_min_months", 12)) if isinstance(sccm_cfg, dict) else 12
    min_sccm_ulh = int(sccm_cfg.get("min_sccm_ulh", 2)) if isinstance(sccm_cfg, dict) else 2
    ulh_thr = float(getattr(rules, "ulh_ft_threshold_hours", 11.0))

    for f in bundle.flights:
        total_cabin_crew = f.needed_cc + f.needed_sc
        if total_cabin_crew > 1:
            # All Senior Crew are SCCM qualified
            sc_vars = [
                x[(c_id, f.flight_id, "SC", s)]
                for (c_id, ff, r, s) in x
                if ff == f.flight_id and r == "SC"
            ]
            # SCCM-certified Cabin Crew
            sccm_cc_vars = [
                x[(c_id, f.flight_id, "CC", s)]
                for (c_id, ff, r, s) in x
                if ff == f.flight_id and r == "CC"
                and bundle.crew_by_id[c_id].sccm_certified
                and bundle.crew_by_id[c_id].experience_months >= exp_min
            ]
            
            sccm_vars = sc_vars + sccm_cc_vars
            # Only add constraint when feasible variables exist to avoid infeasibility due to data gaps
            if sccm_vars:
                req = 1
                if (f.duration_minutes / 60.0) > ulh_thr:
                    req = max(req, min_sccm_ulh)
                model.Add(sum(sccm_vars) >= req)

<<<<<<< HEAD
    # --- No overlap per crew (with DGCA compliance) ---
    # AddNoOverlap over that crew's intervals ensures they don't clash in time,
    # and turnaround padding is already included in interval size.
=======

>>>>>>> 58238b40cb6a50a8a32e8a4f00a31adaa7e93663
    for c_id, iv_list in intervals_by_crew.items():
        if iv_list:
            model.AddNoOverlap(iv_list)
    
<<<<<<< HEAD
    # --- DGCA Rule: Minimum rest between duties ---
    # For each crew, ensure minimum rest hours between consecutive duties
    min_rest_seconds = rules.min_rest_hours_between_duties * 3600

    for c_id in intervals_by_crew:
        # Get all possible flight assignments for this crew
        crew_assignments = [(f_id, bundle.flights_by_id[f_id]) for (c_id_var, f_id, r, s) in x if c_id_var == c_id]

        # Remove duplicates (same flight, different roles/slots)
=======
  
    min_rest_seconds = rules.min_rest_hours_between_duties * 3600

    for c_id in intervals_by_crew:
        crew_assignments = [(f_id, bundle.flights_by_id[f_id]) for (c_id_var, f_id, r, s) in x if c_id_var == c_id]

>>>>>>> 58238b40cb6a50a8a32e8a4f00a31adaa7e93663
        unique_flights = {}
        for f_id, flight in crew_assignments:
            if f_id not in unique_flights:
                unique_flights[f_id] = flight

<<<<<<< HEAD
        # Sort flights by departure time
        sorted_flights = sorted(unique_flights.items(), key=lambda item: item[1].dep_dt)

        # Apply rest constraints between consecutive flights
=======
        sorted_flights = sorted(unique_flights.items(), key=lambda item: item[1].dep_dt)

>>>>>>> 58238b40cb6a50a8a32e8a4f00a31adaa7e93663
        for i in range(len(sorted_flights) - 1):
            f1_id, f1 = sorted_flights[i]
            f2_id, f2 = sorted_flights[i + 1]

<<<<<<< HEAD
            # Calculate actual rest time available
            rest_time_available = (f2.dep_dt.timestamp() - f1.arr_dt.timestamp())

            # Only apply constraint if rest time is insufficient
            if rest_time_available < min_rest_seconds:
                # Find all decision variables for f1 and f2 for this crew
=======
            rest_time_available = (f2.dep_dt.timestamp() - f1.arr_dt.timestamp())

            if rest_time_available < min_rest_seconds:
>>>>>>> 58238b40cb6a50a8a32e8a4f00a31adaa7e93663
                f1_vars = [var for (c_id_var, f_id, r, s), var in x.items()
                          if c_id_var == c_id and f_id == f1_id]
                f2_vars = [var for (c_id_var, f_id, r, s), var in x.items()
                          if c_id_var == c_id and f_id == f2_id]

<<<<<<< HEAD
                # If any assignment to f1 and any assignment to f2 are both selected,
                # it violates the rest constraint
=======

>>>>>>> 58238b40cb6a50a8a32e8a4f00a31adaa7e93663
                for var1 in f1_vars:
                    for var2 in f2_vars:
                        model.Add(var1 + var2 <= 1)

    # --- DGCA Rule: Night duty and consecutive night duty limits ---
    from models import in_night_window
    
    night_start_time, night_end_time = rules.night_window_times()
    # WOCL window and length (in minutes)
    wocl_start_time, wocl_end_time = rules.wocl_window_times()
    try:
        _w_s, _w_e = rules.wocl_window
        wocl_len_minutes = (_w_e - _w_s) if _w_e >= _w_s else (24*60 - (_w_s - _w_e))
        wocl_len_minutes = int(wocl_len_minutes)
    except Exception:
        wocl_len_minutes = 240  # default 4h window
    
    # Track night duties per crew per week
    night_duties_by_crew: Dict[str, List[cp_model.IntVar]] = {}
    
    for c_id in {c.crew_id for c in bundle.crew}:
        night_duty_vars: List[cp_model.IntVar] = []
        consecutive_nights: List[List[cp_model.IntVar]] = []  # Groups of consecutive nights
        
        # Get all potential night flights for this crew
        night_assignments = []
        for (c_id_var, f_id, r, s), var in x.items():
            if c_id_var != c_id:
                continue
            
            f = bundle.flights_by_id[f_id]
            if in_night_window(f.dep_dt, f.arr_dt, night_start_time, night_end_time):
                night_assignments.append((f_id, f, var))
                night_duty_vars.append(var)
        
        # Apply weekly night duty limit
        if night_duty_vars:
            night_sum = sum(night_duty_vars)
            model.Add(night_sum <= rules.max_overnight_duties_per_week)
        
        # Apply consecutive night duty limit
        if len(night_assignments) >= rules.max_consecutive_night_duties:
            # Sort by date
            night_assignments.sort(key=lambda x: x[1].dep_dt)
            
            # Check for consecutive nights (simplified: consecutive dates)
            for i in range(len(night_assignments) - rules.max_consecutive_night_duties + 1):
                consecutive_vars = []
                current_date = night_assignments[i][1].dep_dt.date()
                
                # Look for consecutive dates starting from i
                for j in range(i, min(i + rules.max_consecutive_night_duties + 1, len(night_assignments))):
                    flight_date = night_assignments[j][1].dep_dt.date()
                    if flight_date == current_date:
                        consecutive_vars.append(night_assignments[j][2])
                        current_date = flight_date + timedelta(days=1)
                    else:
                        break
                
                # If we have max_consecutive_night_duties or more consecutive vars
                if len(consecutive_vars) >= rules.max_consecutive_night_duties:
                    model.Add(sum(consecutive_vars[:rules.max_consecutive_night_duties + 1]) <= rules.max_consecutive_night_duties)
        
        night_duties_by_crew[c_id] = night_duty_vars
    
    # --- Daily caps & weekly overtime variables ---
    minutes_total_by_crew: Dict[str, cp_model.IntVar] = {}
    minutes_by_crew_day: Dict[Tuple[str, str], cp_model.IntVar] = {}
    overtime_by_crew: Dict[str, cp_model.IntVar] = {}

<<<<<<< HEAD
    # Precompute per-assignment minutes
    # (All assignments on the same flight share the same minutes.)
    # We'll use elig.minutes_by_flight.
    # Get distinct operating days from bundle.operating_days.
    days = bundle.operating_days

    # For each crew, define daily minute sum vars and total minutes
    for c in bundle.crew:
        c_id = c.crew_id
        # total minutes
        tot = model.NewIntVar(0, 10_000_000, f"tot[{c_id}]")
        # linear expression for total minutes from all assignments of this crew
=======
    days = bundle.operating_days


    for c in bundle.crew:
        c_id = c.crew_id

        tot = model.NewIntVar(0, 10_000_000, f"tot[{c_id}]")

>>>>>>> 58238b40cb6a50a8a32e8a4f00a31adaa7e93663
        total_terms = []
        for (cc, f_id, r, s), var in x.items():
            if cc != c_id:
                continue
            mins = int(max(1, elig.minutes_by_flight[f_id]))
            total_terms.append((mins, var))
        if total_terms:
            model.Add(tot == sum(m * v for m, v in total_terms))
        else:
            model.Add(tot == 0)
        minutes_total_by_crew[c_id] = tot

<<<<<<< HEAD
        # Per-day caps
=======

>>>>>>> 58238b40cb6a50a8a32e8a4f00a31adaa7e93663
        daily_cap_hours = rules.daily_cap_for_role(role_key(c.role))  # hours
        daily_cap_minutes = daily_cap_hours * 60

        for d in days:
<<<<<<< HEAD
            # Per-day duty minutes
=======

>>>>>>> 58238b40cb6a50a8a32e8a4f00a31adaa7e93663
            dvar = model.NewIntVar(0, 1_000_000, f"day[{c_id},{d}]")
            d_terms = []
            # Per-day flight count
            fcnt = model.NewIntVar(0, 1_000_000, f"flights[{c_id},{d}]")
            f_terms = []
            # WOCL indicators (start-in-WOCL and overlap-WOCL)
            start_wocl_count = model.NewIntVar(0, 1_000_000, f"wocl_start_cnt[{c_id},{d}]")
            overlap_wocl_count = model.NewIntVar(0, 1_000_000, f"wocl_ovlp_cnt[{c_id},{d}]")
            start_wocl_terms = []
            overlap_wocl_terms = []
            for (cc, f_id, r, s), var in x.items():
                if cc != c_id:
                    continue
                if elig.day_by_flight[f_id] != d:
                    continue
                mins = int(max(1, elig.minutes_by_flight[f_id]))
                d_terms.append((mins, var))
                f_terms.append(var)
                # WOCL checks
                f = bundle.flights_by_id[f_id]
                dep_t = f.dep_dt.time()
                # dep in WOCL
                if (wocl_start_time <= wocl_end_time and (wocl_start_time <= dep_t < wocl_end_time)) or \
                   (wocl_start_time > wocl_end_time and (dep_t >= wocl_start_time or dep_t < wocl_end_time)):
                    start_wocl_terms.append(var)
                # any overlap with WOCL
                from models import in_night_window as _in_nw
                if _in_nw(f.dep_dt, f.arr_dt, wocl_start_time, wocl_end_time):
                    overlap_wocl_terms.append(var)
            # Bind sums
            if d_terms:
                model.Add(dvar == sum(m * v for m, v in d_terms))
            else:
                model.Add(dvar == 0)
            if f_terms:
                model.Add(fcnt == sum(f_terms))
            else:
                model.Add(fcnt == 0)
            if start_wocl_terms:
                model.Add(start_wocl_count == sum(start_wocl_terms))
            else:
                model.Add(start_wocl_count == 0)
            if overlap_wocl_terms:
                model.Add(overlap_wocl_count == sum(overlap_wocl_terms))
            else:
                model.Add(overlap_wocl_count == 0)

            minutes_by_crew_day[(c_id, d)] = dvar

            # Base daily cap by role
            model.Add(dvar <= daily_cap_minutes)

            # DGCA FDP landings cap (conservative): max 6 landings per duty day
            model.Add(fcnt <= 6)

<<<<<<< HEAD
            # DGCA FDP landings cap (piecewise by daily flight time)
            # Base cap: 6; tightened when daily flight time exceeds thresholds (8h -> 3, 11h -> 1)
            # Piecewise brackets for daily flight time minutes
=======
>>>>>>> 58238b40cb6a50a8a32e8a4f00a31adaa7e93663
            b_le_8  = model.NewBoolVar(f"b_le_8[{c_id},{d}]")     # dvar <= 8h
            b_8_11  = model.NewBoolVar(f"b_8_11[{c_id},{d}]")     # 8h &lt; dvar &lt;= 11h
            b_gt_11 = model.NewBoolVar(f"b_gt_11[{c_id},{d}]")    # dvar &gt; 11h
            model.Add(b_le_8 + b_8_11 + b_gt_11 == 1)

            th1 = 8 * 60
            th2 = 11 * 60

            # Bind brackets (reified)
            model.Add(dvar <= th1).OnlyEnforceIf(b_le_8)
            model.Add(dvar >= th1 + 1).OnlyEnforceIf(b_le_8.Not())

            model.Add(dvar >= th1 + 1).OnlyEnforceIf(b_8_11)
            model.Add(dvar <= th2).OnlyEnforceIf(b_8_11)

            model.Add(dvar <= th2).OnlyEnforceIf(b_gt_11.Not())
            model.Add(dvar >= th2 + 1).OnlyEnforceIf(b_gt_11)

            # Enforce landing caps per bracket from DGCA FDP table
            # ≤8 hrs FT → max 6 landings; 8–11 hrs → max 3; &gt;11 hrs (up to 14) → max 1
            model.Add(fcnt <= 6).OnlyEnforceIf(b_le_8)
            model.Add(fcnt <= 3).OnlyEnforceIf(b_8_11)
            model.Add(fcnt <= 1).OnlyEnforceIf(b_gt_11)
            # WOCL-based FDP reduction (approximation):
            # If FDP starts in WOCL → reduce cap by 100% of WOCL length.
            # If FDP ends/overlaps WOCL → reduce cap by 50% of WOCL length.
            ind_start_wocl = model.NewBoolVar(f"wocl_start_ind[{c_id},{d}]")
            ind_ovlp_wocl = model.NewBoolVar(f"wocl_ovlp_ind[{c_id},{d}]")
            model.Add(start_wocl_count >= 1).OnlyEnforceIf(ind_start_wocl)
            model.Add(start_wocl_count == 0).OnlyEnforceIf(ind_start_wocl.Not())
            model.Add(overlap_wocl_count >= 1).OnlyEnforceIf(ind_ovlp_wocl)
            model.Add(overlap_wocl_count == 0).OnlyEnforceIf(ind_ovlp_wocl.Not())

            red_full = min(daily_cap_minutes, int(wocl_len_minutes))
            red_half = min(daily_cap_minutes, int(wocl_len_minutes // 2))
            # Apply reduced caps under indicators
            model.Add(dvar <= daily_cap_minutes - red_full).OnlyEnforceIf(ind_start_wocl)
            model.Add(dvar <= daily_cap_minutes - red_half).OnlyEnforceIf(ind_ovlp_wocl)

        # Weekly cap → overtime var
        wk_cap = c.weekly_max_duty_hrs if c.weekly_max_duty_hrs is not None else rules.weekly_max_duty_hrs_default
        wk_cap_minutes = int(wk_cap) * 60
        ot = model.NewIntVar(0, 10_000_000, f"ot[{c_id}]")
        model.Add(ot >= tot - wk_cap_minutes)
        overtime_by_crew[c_id] = ot

        # DGCA cumulative Flight Time weekly hard cap (7 days)
        # We approximate duty minutes with flight minutes in this POC.
        try:
            ft7_cap_minutes = int(rules.flight_time_limits.get("hours_7_days", 40)) * 60
            model.Add(tot <= ft7_cap_minutes)
        except Exception:
            pass

    # --- Location Continuity Constraints (All Crew) ---
    # For each crew, the next assigned flight must depart from the previous flight's arrival station
    _add_pilot_continuity_constraints(model, x, bundle, elig)
    
    # --- Base Return Priority Constraints ---
    # Encourage pilots to return to base by EOD
    base_penalty_vars = _add_base_return_constraints(model, x, bundle, elig)

    # Return all artifacts; objective will be added later
    return ModelArtifacts(
        model=model,
        x=x,
        intervals_by_crew=intervals_by_crew,
        minutes_total_by_crew=minutes_total_by_crew,
        minutes_by_crew_day=minutes_by_crew_day,
        overtime_by_crew=overtime_by_crew,
        base_penalty_vars=base_penalty_vars,
        role_slots=elig.role_slots,
    )


def _add_pilot_continuity_constraints(
    model: cp_model.CpModel,
    x: Dict[Tuple[str, str, str, int], cp_model.IntVar],
    bundle: DataBundle,
    elig: EligibilityBundle,
) -> None:
    """
    Location continuity for ALL crew:
    If a crew member is assigned to two consecutive flights in time,
    then the second must depart from the first's arrival station.

    Implemented as hard constraints between adjacent time-ordered flights
    for each crew (var1 + var2 <= 1 when locations mismatch).
    """
    # For each crew, consider the distinct flights they could be assigned to (from decision vars)
    for c_id in {c.crew_id for c in bundle.crew}:
        # Collect distinct flights present in x for this crew
        crew_fids: List[Tuple[str, any]] = []
        seen = set()
        for (cc, f_id, r, s) in x.keys():
            if cc != c_id:
                continue
            if f_id in seen:
                continue
            seen.add(f_id)
            crew_fids.append((f_id, bundle.flights_by_id[f_id]))
        if len(crew_fids) < 2:
            continue

        # Sort by departure to derive potential adjacency
        crew_fids.sort(key=lambda it: it[1].dep_dt)

        # Enforce location continuity only between adjacent flights in time
        for i in range(len(crew_fids) - 1):
            f1_id, f1 = crew_fids[i]
            f2_id, f2 = crew_fids[i + 1]

            # If arrival of first doesn't match departure of next, they cannot both be assigned
            if f1.arr_airport != f2.dep_airport:
                f1_vars = [var for (cc, fid, r, s), var in x.items() if cc == c_id and fid == f1_id]
                f2_vars = [var for (cc, fid, r, s), var in x.items() if cc == c_id and fid == f2_id]
                for v1 in f1_vars:
                    for v2 in f2_vars:
                        model.Add(v1 + v2 <= 1)


def _add_base_return_constraints(
    model: cp_model.CpModel,
    x: Dict[Tuple[str, str, str, int], cp_model.IntVar],
    bundle: DataBundle,
    elig: EligibilityBundle,
) -> Dict[str, cp_model.IntVar]:
    """
    Add base return priority constraints: encourage pilots to return to base by EOD.
    Returns penalty variables for use in objective.
    """
    base_penalty_vars = {}
    pilot_roles = {"Captain", "FO"}
    
    # For each pilot and each day, track if they end the day away from base
    for crew in bundle.crew:
        if crew.role_norm not in pilot_roles:
            continue
            
        c_id = crew.crew_id
        crew_base = crew.base
        
        for day_str in bundle.operating_days:
            # Find all flights for this crew on this day
            day_flights = []
            for (cc_id, f_id, role, slot_idx), var in x.items():
                if cc_id != c_id or elig.day_by_flight[f_id] != day_str:
                    continue
                if role not in pilot_roles:
                    continue
                flight = bundle.flights_by_id[f_id]
                day_flights.append((flight, var))
            
            if not day_flights:
                continue
                
            # Sort flights by departure time to find last flight of day
            day_flights.sort(key=lambda x: x[0].dep_dt)
            
            # Create penalty variable for ending day away from base
            away_from_base_penalty = model.NewIntVar(0, 1000, f"base_penalty[{c_id},{day_str}]")
            base_penalty_vars[f"{c_id}_{day_str}"] = away_from_base_penalty
            
            # For the last flight of the day, if it doesn't end at base, add penalty
            if day_flights:
                last_flight, last_var = day_flights[-1]
                if last_flight.arr_airport != crew_base:
                    # If last flight is assigned and doesn't end at base, activate penalty
                    model.Add(away_from_base_penalty >= last_var * 100)
                else:
                    # If last flight ends at base, no penalty
                    model.Add(away_from_base_penalty == 0)
    
    return base_penalty_vars