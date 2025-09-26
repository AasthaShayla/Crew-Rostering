"""
Groq LLM helper for parsing natural-language disruption instructions into structured scenario data.

Exposes:
- parse_disruptions_nl(text: str, crew_list: list[dict], flights_list: list[dict]) -> dict
  Returns:
    {
      "success": bool,
      "flight_disruptions": [{"flight_id": str, "type": "delay"|"cancellation", "delay_minutes": int, "note": str}],
      "crew_sickness": [{"crew_id": str, "sick_date": "YYYY-MM-DD", "note": str}],
      "error": str | None
    }
"""
from __future__ import annotations

import os
import json
import re
from typing import List, Dict, Any, Optional

# Optional Groq dependency (graceful fallback if unavailable)
try:
    from groq import Groq  # type: ignore
except Exception:  # pragma: no cover
    Groq = None  # type: ignore


def _load_groq_api_key() -> Optional[str]:
    """
    Load Groq API key from:
      1) environment variable GROQ_API_KEY
      2) backend/.env file (supports either 'GROQ_API_KEY=...' or raw token on a single line)
    """
    key = os.environ.get("GROQ_API_KEY")
    if key:
        return key.strip()

    # Fallback: try to read backend/.env relative to this file
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    try:
        with open(env_path, "r") as f:
            content = f.read().strip()
        if not content:
            return None
        # If file contains a single token (no equals), treat content as the key
        if "=" not in content and "\n" not in content:
            return content.strip()
        # Else parse key=value lines
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("GROQ_API_KEY="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass

    return None


def _normalize_type(t: str) -> str:
    t = (t or "").strip().lower()
    if t in {"delay", "delayed"}:
        return "delay"
    if t in {"cancellation", "cancelled", "canceled", "cancel"}:
        return "cancellation"
    return "delay"


def _build_crew_index(crew_list: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Build a robust index for crew lookup by id or case-insensitive name tokens.
    """
    idx = {}
    for c in crew_list or []:
        cid = str(c.get("crew_id", "")).strip()
        name = str(c.get("name", "")).strip()
        if cid:
            idx[f"id:{cid}"] = c
        if name:
            nm = name.lower()
            idx[f"name:{nm}"] = c
            # also split tokens for partial matches
            for tok in re.split(r"[\s,.\-_/]+", nm):
                if tok:
                    # prefer full-name entries; only set if not already present
                    idx.setdefault(f"tok:{tok}", c)
    return idx


def _build_flight_index(flights_list: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Build a robust index for flight lookup by exact id, and sector tokens like 'DEL-BOM'.
    """
    idx = {}
    for f in flights_list or []:
        fid = str(f.get("flight_id", "")).strip()
        if fid:
            idx[f"id:{fid.lower()}"] = f
        dep = str(f.get("dep_airport", "")).strip()
        arr = str(f.get("arr_airport", "")).strip()
        if dep and arr:
            sector = f"{dep}-{arr}".lower()
            idx[f"sector:{sector}"] = f
    return idx


def _match_crew(text: str, crew_idx: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Heuristic crew matcher: look for 'crew 123', 'id 123', or any known name tokens.
    """
    t = text.lower()

    # by explicit crew_id patterns
    m = re.search(r"\b(crew|id)\s*[:#]?\s*([A-Za-z0-9_-]+)\b", t)
    if m:
        cid = m.group(2)
        cand = crew_idx.get(f"id:{cid}")
        if cand:
            return cand

    # by exact name presence (full name)
    for k, v in crew_idx.items():
        if k.startswith("name:"):
            name_lower = k.split(":", 1)[1]
            if name_lower and name_lower in t:
                return v

    # by token overlap (fallback)
    tokens = set(re.split(r"[\s,.\-_/]+", t))
    best = None
    for k, v in crew_idx.items():
        if k.startswith("tok:"):
            tok = k.split(":", 1)[1]
            if tok and tok in tokens:
                best = v
                break
    return best


def _match_flight(text: str, flight_idx: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Heuristic flight matcher: look for explicit flight ids (e.g., 6E1234) or sector like 'DEL-BOM'.
    """
    t = text.lower()

    # explicit flight id like 6e123, 6e-123, 6e 123
    m = re.search(r"\b([a-z]{1,3}[-\s]?\d{2,5})\b", t)
    if m:
        fid = m.group(1).replace(" ", "").replace("-", "").upper()
        cand = flight_idx.get(f"id:{fid.lower()}")
        if cand:
            return cand

    # sector like DEL-BOM
    m2 = re.search(r"\b([A-Z]{3})[-\s]?([A-Z]{3})\b", text)
    if m2:
        sector = f"{m2.group(1)}-{m2.group(2)}".lower()
        cand = flight_idx.get(f"sector:{sector}")
        if cand:
            return cand

    return None


def _fallback_parse(
    text: str,
    crew_list: List[Dict[str, Any]],
    flights_list: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Lightweight regex-based parser when Groq is not configured/available.
    Handles:
      - "Captain 102 is sick today/tomorrow/on 2025-09-10"
      - "6E123 is delayed by 45 minutes"
      - "6E456 cancelled" / "cancel 6E456"
    """
    crew_idx = _build_crew_index(crew_list)
    flight_idx = _build_flight_index(flights_list)

    flight_disruptions: List[Dict[str, Any]] = []
    crew_sickness: List[Dict[str, Any]] = []

    t = text.strip()

    # sick patterns
    if re.search(r"\b(sick|unwell|ill|not\s+fit)\b", t, flags=re.I):
        c = _match_crew(t, crew_idx)
        if c:
            # crude date extractor
            date = None
            m_date = re.search(r"\b(20\d{2}[-/]\d{2}[-/]\d{2})\b", t)
            if m_date:
                date = m_date.group(1).replace("/", "-")
            else:
                # default to today's sample date used in dataset
                date = "2025-09-08"
            crew_sickness.append({
                "crew_id": str(c.get("crew_id")),
                "sick_date": date,
                "note": "Parsed from NL (fallback)"
            })

    # delay patterns
    if re.search(r"\b(delay|delayed)\b", t, flags=re.I):
        f = _match_flight(t, flight_idx)
        if f:
            mins = 0
            m_min = re.search(r"\b(\d{1,3})\s*(min|mins|minutes)\b", t, flags=re.I)
            if m_min:
                mins = int(m_min.group(1))
            else:
                # try "by X" without unit
                m_by = re.search(r"\bby\s+(\d{1,3})\b", t, flags=re.I)
                if m_by:
                    mins = int(m_by.group(1))
            flight_disruptions.append({
                "flight_id": str(f.get("flight_id")),
                "type": "delay",
                "delay_minutes": mins,
                "note": "Parsed from NL (fallback)"
            })

    # cancellation patterns
    if re.search(r"\b(cancel|cancelled|canceled)\b", t, flags=re.I):
        f = _match_flight(t, flight_idx)
        if f:
            flight_disruptions.append({
                "flight_id": str(f.get("flight_id")),
                "type": "cancellation",
                "delay_minutes": 0,
                "note": "Parsed from NL (fallback)"
            })

    return {
        "success": True,
        "flight_disruptions": flight_disruptions,
        "crew_sickness": crew_sickness,
        "error": None
    }


def parse_disruptions_nl(
    text: str,
    crew_list: List[Dict[str, Any]],
    flights_list: List[Dict[str, Any]],
    model: str = "llama-3.1-70b-versatile",
) -> Dict[str, Any]:
    """
    Use Groq LLM to parse natural language into structured disruptions.
    Falls back to a regex-based heuristic parser if Groq is not available.
    """
    api_key = _load_groq_api_key()
    if not Groq or not api_key:
        return _fallback_parse(text, crew_list, flights_list)

    client = None
    try:
        client = Groq(api_key=api_key)
    except Exception as e:  # pragma: no cover
        return _fallback_parse(text, crew_list, flights_list)

    # Build compact context to help disambiguation
    crew_names = [
        {"crew_id": str(c.get("crew_id")), "name": c.get("name", ""), "role": c.get("role", "")}
        for c in (crew_list or [])
    ]
    flight_ids = [
        {
            "flight_id": str(f.get("flight_id")),
            "dep_airport": f.get("dep_airport", ""),
            "arr_airport": f.get("arr_airport", "")
        }
        for f in (flights_list or [])
    ]

    system_prompt = (
        "You convert airline disruption instructions into strict JSON. "
        "Only output JSON, no explanations. Schema:\n"
        "{\n"
        '  "flight_disruptions": [\n'
        '    {"flight_id": "6E123", "type": "delay|cancellation", "delay_minutes": 0, "note": "string"}\n'
        "  ],\n"
        '  "crew_sickness": [\n'
        '    {"crew_id": "C102", "sick_date": "YYYY-MM-DD", "note": "string"}\n'
        "  ]\n"
        "}\n"
        "Rules:\n"
        "- type must be exactly 'delay' or 'cancellation'.\n"
        "- delay_minutes must be integer (0 for cancellation).\n"
        "- Use crew_id/flight_id that exists in provided context when possible.\n"
        "- If no explicit date for sickness, default to '2025-09-08'.\n"
        "- If no explicit delay value, default to 60.\n"
        "- If multiple items are present, include all of them."
    )

    user_prompt = json.dumps({
        "instruction": text,
        "context": {
            "crew": crew_names,
            "flights": flight_ids
        }
    })

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content if resp and resp.choices else "{}"
        parsed = json.loads(content or "{}")

        # Normalize and validate
        flight_disruptions = []
        for d in parsed.get("flight_disruptions", []):
            fid = str(d.get("flight_id", "")).strip()
            if not fid:
                continue
            flight_disruptions.append({
                "flight_id": fid,
                "type": _normalize_type(d.get("type", "delay")),
                "delay_minutes": int(d.get("delay_minutes") or 0),
                "note": str(d.get("note") or "Parsed via Groq")
            })

        crew_sickness = []
        for s in parsed.get("crew_sickness", []):
            cid = str(s.get("crew_id", "")).strip()
            if not cid:
                continue
            sick_date = str(s.get("sick_date") or "2025-09-08").replace("/", "-")
            crew_sickness.append({
                "crew_id": cid,
                "sick_date": sick_date,
                "note": str(s.get("note") or "Parsed via Groq")
            })

        return {
            "success": True,
            "flight_disruptions": flight_disruptions,
            "crew_sickness": crew_sickness,
            "error": None
        }
    except Exception as e:  # pragma: no cover
        # Fallback to heuristic on any LLM error
        return _fallback_parse(text, crew_list, flights_list)