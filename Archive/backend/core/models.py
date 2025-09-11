# models.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, time
from typing import Optional, Set, Dict, Tuple, Iterable, List, Any


# ---------- Roles & utilities ----------

def role_key(raw: str) -> str:
    """Normalize role strings to: 'Captain', 'FO', 'SC', 'CC'."""
    r = (raw or "").strip()
    if r in ("FO", "First Officer"):
        return "FO"
    if r in ("Senior Crew", "Senior Cabin Crew", "SC"):
        return "SC"
    if r in ("Junior Cabin Crew", "Cabin Crew", "CC"):
        return "CC"
    return "Captain"  # default for 'Captain'


def has_qual(qualified_types: str, ac_type: str) -> bool:
    """Check if crew's qualified_types include the aircraft type."""
    if not qualified_types:
        return False
    return ac_type in qualified_types.split("|")


def overlaps_with_turnaround(a_start: datetime, a_end: datetime,
                             b_start: datetime, b_end: datetime,
                             turnaround_minutes: int) -> bool:
    """
    Return True if two flight duties overlap for the same crew,
    considering a turnaround buffer padding at the end of each flight.
    """
    # Pad end by turnaround
    a_end_pad = a_end.timestamp() + turnaround_minutes * 60
    b_end_pad = b_end.timestamp() + turnaround_minutes * 60
    # Intervals [start, end+turnaround]
    return not (a_end_pad <= b_start.timestamp() or b_end_pad <= a_start.timestamp())


def in_night_window(dep: datetime, arr: datetime, start_local: time, end_local: time) -> bool:
    """
    True if any portion of [dep, arr] is within the night window [start_local, end_local).
    Window may wrap midnight (e.g., 22:00–05:00).
    NOTE: We treat datetimes as local for POC (naive, no tz math).
    """
    # Reduce to times for a coarse check: if either departure or arrival time lies in the window,
    # or if window wraps midnight and the interval spans midnight.
    dep_t, arr_t = dep.time(), arr.time()
    wraps = start_local > end_local
    def in_window(t: time) -> bool:
        if wraps:
            return t >= start_local or t < end_local
        return start_local <= t < end_local
    return in_window(dep_t) or in_window(arr_t) or (wraps and dep.date() != arr.date())


# ---------- Data classes for each table ----------

@dataclass(frozen=True)
class Flight:
    flight_id: str
    dep_airport: str
    arr_airport: str
    dep_dt: datetime
    arr_dt: datetime
    aircraft_type: str
    needed_captains: int
    needed_fo: int
    needed_sc: int
    needed_cc: int

    @property
    def duration_minutes(self) -> int:
        return int((self.arr_dt - self.dep_dt).total_seconds() // 60)

    @property
    def sector(self) -> str:
        return f"{self.dep_airport}-{self.arr_airport}"


@dataclass(frozen=True)
class Crew:
    crew_id: str
    name: str
    role: str            # raw role (Captain / First Officer / Senior/Junior Cabin Crew)
    base: str
    qualified_types: str # e.g., "A320|A321"
    weekly_max_duty_hrs: Optional[int]
    leave_status: str    # Available / On Leave / Training / Sick
    sccm_certified: bool = False
    experience_months: int = 0

    @property
    def role_norm(self) -> str:
        return role_key(self.role)

    def qualified_for(self, ac_type: str) -> bool:
        return has_qual(self.qualified_types, ac_type)


@dataclass(frozen=True)
class CrewPreference:
    crew_id: str
    requested_days_off: Set[str]      # set of "YYYY-MM-DD"
    preferred_sectors: Set[str]       # set of "DEP-ARR"


@dataclass(frozen=True)
class Disruption:
    flight_id: str
    disruption_type: str  # "Delay" or "Cancellation"
    delay_minutes: int


@dataclass(frozen=True)
class CrewSickness:
    crew_id: str
    sick_date: str         # "YYYY-MM-DD"


@dataclass(frozen=True)
class Rules:
    daily_max_duty_hrs: Dict[str, int]            # {"Captain":10,"First Officer":10,"Cabin":11}
    weekly_max_duty_hrs_default: int              # e.g., 45
    min_rest_hours_between_duties: int            # e.g., 12  (POC, may be approximated)
    max_overnight_duties_per_week: int            # e.g., 4   (optional in POC)
    turnaround_minutes: int                       # e.g., 45
    night_duty_window: Tuple[int, int]            # (start_min, end_min) like (22*60, 5*60)
    max_consecutive_night_duties: int             # e.g., 3   (optional in POC)
    # Extended DGCA schema
    wocl_window: Tuple[int, int]                  # (start_min, end_min) like (2*60, 6*60)
    fdp_rules: List[Dict[str, Any]]               # brackets by max_flight_time_hrs with max_fdp_hrs, max_landings
    fdp_wocl_reduction: Dict[str, float]          # {"starts_in_wocl_factor":1.0,"overlaps_wocl_factor":0.5}
    flight_time_limits: Dict[str, int]            # cumulative FT caps: {"hours_7_days":40,...}
    duty_time_limits: Dict[str, int]              # cumulative duty caps: {"hours_7_days":65,"hours_28_days":210}
    rest_requirements: Dict[str, Any]             # daily/weekly rest and TZ-based minima
    standby: Dict[str, Any]                       # standby rules & post-standby rest
    discretion: Dict[str, Any]                    # unforeseen extensions and compensatory rest
    composition: Dict[str, Any]                   # min crew composition requirements
    ulh_ft_threshold_hours: float                 # ULH/ULR thresholds (for SCCM multiplier etc.)
    notes: str

    def night_window_times(self) -> Tuple[time, time]:
        start_min, end_min = self.night_duty_window
        return (time(hour=start_min // 60, minute=start_min % 60),
                time(hour=end_min // 60, minute=end_min % 60))

    def wocl_window_times(self) -> Tuple[time, time]:
        start_min, end_min = self.wocl_window
        return (time(hour=start_min // 60, minute=start_min % 60),
                time(hour=end_min // 60, minute=end_min % 60))

    def daily_cap_for_role(self, role_norm: str) -> int:
        """Return daily max duty hours based on normalized role."""
        if role_norm == "CC":
            # 'Cabin' key in rules maps to CC crew caps in our dataset
            return int(self.daily_max_duty_hrs.get("Cabin", 11))
        if role_norm == "SC":
            # Senior Crew follows cabin crew rules but with potentially higher limits
            return int(self.daily_max_duty_hrs.get("Senior Cabin", self.daily_max_duty_hrs.get("Cabin", 12)))
        if role_norm == "FO":
            return int(self.daily_max_duty_hrs.get("First Officer", 10))
        return int(self.daily_max_duty_hrs.get("Captain", 10))