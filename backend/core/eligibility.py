# eligibility.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple
from datetime import datetime

from models import role_key
from loader import DataBundle


# ----- Data structures we export -----

@dataclass(frozen=True)
class RoleSlot:
    """One required seat on a flight for a given role."""
    flight_id: str
    role: str         # Normalized: "Captain" | "FO" | "SC" | "CC"
    slot_index: int   # 0..(needed_role-1)


@dataclass
class EligibilityBundle:
    """All data the solver needs to know about feasible assignments."""
    role_slots: List[RoleSlot]
    # All eligible (crew, flight, role, slot) combinations
    eligible: List[Tuple[str, str, str, int]]
    # Precomputed flight properties
    minutes_by_flight: Dict[str, int]
    day_by_flight: Dict[str, str]         # "YYYY-MM-DD"
    sector_by_flight: Dict[str, str]      # "DEP-ARR"
    aircraft_by_flight: Dict[str, str]    # "A320" / "A321" / "ATR72"


# ----- Helpers -----

def _flight_day_str(dt: datetime) -> str:
    return dt.date().isoformat()


def build_role_slots(bundle: DataBundle) -> List[RoleSlot]:
    """Expand each flight's demand into explicit role slots."""
    slots: List[RoleSlot] = []
    for f in bundle.flights:
        # Captain seats
        for i in range(int(f.needed_captains)):
            slots.append(RoleSlot(flight_id=f.flight_id, role="Captain", slot_index=i))
        # First Officer seats
        for i in range(int(f.needed_fo)):
            slots.append(RoleSlot(flight_id=f.flight_id, role="FO", slot_index=i))
        # Senior Crew seats
        for i in range(int(f.needed_sc)):
            slots.append(RoleSlot(flight_id=f.flight_id, role="SC", slot_index=i))
        # Cabin Crew seats
        for i in range(int(f.needed_cc)):
            slots.append(RoleSlot(flight_id=f.flight_id, role="CC", slot_index=i))
    return slots


def _crew_can_work_that_day(crew_id: str, day_str: str, bundle: DataBundle) -> bool:
    """Check per-day sickness. Static leave/training/sick already filtered in loader."""
    sick_days = bundle.sickness_days.get(crew_id, set())
    return day_str not in sick_days


def _crew_role_matches(slot_role: str, crew_role_raw: str) -> bool:
    """Match slot role with normalized crew role."""
    return role_key(crew_role_raw) == slot_role


def _crew_qualified_for(ac_type: str, qualified_types: str) -> bool:
    """Aircraft-type check."""
    return ac_type in str(qualified_types).split("|")


def build_eligibility(bundle: DataBundle) -> EligibilityBundle:
    """
    Construct:
      - role_slots: list of RoleSlot for all flights
      - eligible: list of feasible (crew_id, flight_id, role, slot_idx)
      - flight property maps used by constraints/objective
    """
    role_slots = build_role_slots(bundle)

    # Precompute maps for flights
    minutes_by_flight: Dict[str, int] = {}
    day_by_flight: Dict[str, str] = {}
    sector_by_flight: Dict[str, str] = {}
    aircraft_by_flight: Dict[str, str] = {}

    for f in bundle.flights:
        minutes_by_flight[f.flight_id] = max(1, int((f.arr_dt - f.dep_dt).total_seconds() // 60))
        day_by_flight[f.flight_id] = _flight_day_str(f.dep_dt)
        sector_by_flight[f.flight_id] = f"{f.dep_airport}-{f.arr_airport}"
        aircraft_by_flight[f.flight_id] = f.aircraft_type

    # Build eligible (crew, flight, role, slot) tuples
    eligible: List[Tuple[str, str, str, int]] = []
    for slot in role_slots:
        f = bundle.flights_by_id[slot.flight_id]
        day_str = day_by_flight[slot.flight_id]
        ac_type = f.aircraft_type

        for c in bundle.crew:
            if not _crew_role_matches(slot.role, c.role):
                continue
            if not _crew_qualified_for(ac_type, c.qualified_types):
                continue
            if not _crew_can_work_that_day(c.crew_id, day_str, bundle):
                continue
            eligible.append((c.crew_id, slot.flight_id, slot.role, slot.slot_index))

    return EligibilityBundle(
        role_slots=role_slots,
        eligible=eligible,
        minutes_by_flight=minutes_by_flight,
        day_by_flight=day_by_flight,
        sector_by_flight=sector_by_flight,
        aircraft_by_flight=aircraft_by_flight,
    )