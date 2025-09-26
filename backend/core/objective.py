# objective.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple, List

from ortools.sat.python import cp_model

from loader import DataBundle
from eligibility import EligibilityBundle
from constraints import ModelArtifacts


@dataclass(frozen=True)
class Weights:
    """Tunable objective weights."""
    w_ot: int = 100       # Overtime penalty (heavy)
    w_fair: int = 10      # Fairness penalty (medium)
    w_pref: int = 1       # Preferences penalty (light)
    w_base: int = 50      # Base return penalty (medium-heavy)
    w_continuity: int = 75 # Pilot continuity penalty (heavy)


def add_objective(
    bundle: DataBundle,
    elig: EligibilityBundle,
    art: ModelArtifacts,
    weights: Weights = Weights(),
) -> None:
    """
    Augment the model in-place with the objective:
      Minimize  w_ot * Sum(overtime)
              + w_fair * Sum(deviation from average minutes)
              + w_pref * (day-off penalties + non-preferred sector penalties)
              + w_base * Sum(base return penalties for pilots)
              + w_continuity * Sum(pilot continuity violations)
    """

    model: cp_model.CpModel = art.model
    x = art.x

    # ---------- 1) Overtime term ----------
    # Already created in constraints: overtime_by_crew[c] >= total[c] - cap[c]
    overtime_sum = sum(art.overtime_by_crew.values())

    # ---------- 2) Fairness term ----------
    # Encourage everyone to be close to the average assigned minutes.
    sum_totals = model.NewIntVar(0, 1_000_000_000, "sum_totals_obj")
    model.Add(sum_totals == sum(art.minutes_total_by_crew[c] for c in art.minutes_total_by_crew))

    n = max(1, len(art.minutes_total_by_crew))
    avg_minutes = model.NewIntVar(0, 1_000_000_000, "avg_minutes_obj")
    # avg_minutes * n == sum_totals
    model.AddMultiplicationEquality(sum_totals, [avg_minutes, n])

    dev_pos: Dict[str, cp_model.IntVar] = {}
    dev_neg: Dict[str, cp_model.IntVar] = {}
    for c_id, tot in art.minutes_total_by_crew.items():
        dpos = model.NewIntVar(0, 1_000_000_000, f"dpos[{c_id}]")
        dneg = model.NewIntVar(0, 1_000_000_000, f"dneg[{c_id}]")
        model.Add(tot - avg_minutes == dpos - dneg)
        dev_pos[c_id] = dpos
        dev_neg[c_id] = dneg

    fairness_sum = sum(dev_pos.values()) + sum(dev_neg.values())

    # ---------- 3) Preference penalties ----------
    # (a) Requested Days Off: big penalty if assigned on that date
    # (b) Preferred Sectors: small penalty when assigned to non-preferred sector (if crew has preferences)
    pref_pen_terms: List[cp_model.IntVar] = []

    # Build quick lookups
    days_off = {cid: p.requested_days_off for cid, p in bundle.prefs.items()}
    pref_sectors = {cid: p.preferred_sectors for cid, p in bundle.prefs.items()}

    # For each potential assignment x[(c,f,r,s)], create small penalty vars when appropriate
    for (c_id, f_id, role, slot_idx), var in x.items():
        day_str = elig.day_by_flight[f_id]                    # "YYYY-MM-DD"
        sector = elig.sector_by_flight[f_id]                  # "DEP-ARR"

        # (a) Day-off request penalty (big)
        if c_id in days_off and day_str in days_off[c_id]:
            pen = model.NewIntVar(0, 1_000_000, f"pen_dayoff[{c_id},{f_id}]")
            model.Add(pen == var * 1000)  # big penalty if assigned
            pref_pen_terms.append(pen)

        # (b) Preferred sectors penalty (tiny if assigned outside given prefs)
        if c_id in pref_sectors and len(pref_sectors[c_id]) > 0 and sector not in pref_sectors[c_id]:
            pen2 = model.NewIntVar(0, 1_000_000, f"pen_pref[{c_id},{f_id}]")
            model.Add(pen2 == var * 1)    # tiny penalty
            pref_pen_terms.append(pen2)

    pref_sum = sum(pref_pen_terms) if pref_pen_terms else 0

    # ---------- 4) Base return penalties ----------
    # Penalize pilots who don't return to base by end of day
    base_return_sum = sum(art.base_penalty_vars.values()) if art.base_penalty_vars else 0

    # ---------- Final objective ----------
    model.Minimize(
        weights.w_ot   * overtime_sum
        + weights.w_fair * fairness_sum
        + weights.w_pref * pref_sum
        + weights.w_base * base_return_sum
    )