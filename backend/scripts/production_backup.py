"""FR-53: export one production to JSON through the API, and import it back into an empty one.

A restore that needs no database access — the service token is enough — so a
deleted production, a bad migration or a lost Supabase project can be recovered
from a file on the founder's Mac. Uses only public schemas of the API, so it
keeps working as long as the API does.

Usage (from backend/, token in ~/.config/filmrunner/api_token or FILMRUNNER_API_TOKEN):
    python -m scripts.production_backup export <production_id> > noc.json
    python -m scripts.production_backup export --all --out-dir backups/2026-09-22/
    python -m scripts.production_backup import noc.json                     # into a new production, same name
    python -m scripts.production_backup import noc.json --into <production_id>  # into an existing EMPTY production

What is carried: production name/status, contacts (name, phone, e-mail; photos are not), crew (department,
position, standing call, HoD), cast (character, usual pickup), locations (address, parking, hospital,
coordinates), members (e-mail, role), every day with its current revision (calls, sun, weather, safety,
head of day, scenes, cast calls, personal calls), day status (draft/published/cancelled).
What is not: revision history (only the current revision), push subscriptions, read receipts, personal
tokens (new ones are minted — crew get new links), photos.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

API = os.environ.get("FILMRUNNER_API_BASE", "https://filmrunner-api.fly.dev")
FORMAT = 1


def _token() -> str:
    env = os.environ.get("FILMRUNNER_API_TOKEN")
    if env:
        return env
    path = Path(os.path.expanduser("~/.config/filmrunner/api_token"))
    if not path.exists():
        sys.exit("No service token: set FILMRUNNER_API_TOKEN or put it in ~/.config/filmrunner/api_token")
    return path.read_text().strip()


def call(method: str, path: str, body: Any = None) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, method=method, data=data,
                                 headers={"Authorization": f"Bearer {_token()}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        sys.exit(f"{method} {path} → {exc.code}: {exc.read().decode()[:300]}")


# ---- export -----------------------------------------------------------------------

def export_production(pid: str) -> dict:
    production = call("GET", f"/api/v1/productions/{pid}")
    crew = call("GET", f"/api/v1/productions/{pid}/crew-members")
    cast = call("GET", f"/api/v1/productions/{pid}/cast-members")
    locations = call("GET", f"/api/v1/productions/{pid}/locations")
    members = call("GET", f"/api/v1/productions/{pid}/members")
    days = call("GET", f"/api/v1/productions/{pid}/call-sheets")
    contacts: dict[str, dict] = {}
    for m in crew + cast:
        c = m["contact"]
        contacts[c["id"]] = {"id": c["id"], "name": c["name"], "phone": c.get("phone"), "email": c.get("email")}
    full_days = []
    for d in days:
        sheet = call("GET", f"/api/v1/call-sheets/{d['id']}")
        rev = sheet.get("current_revision") or {}
        full_days.append({
            "id": sheet["id"], "shoot_date": sheet["shoot_date"], "day_number": sheet["day_number"], "day_count": sheet["day_count"],
            "unit_name": sheet["unit_name"], "status": sheet.get("status", "published"),
            "revision": {
                "revision_letter": rev.get("revision_letter"), "general_crew_call": rev.get("general_crew_call"), "shooting_call": rev.get("shooting_call"),
                "sunrise": rev.get("sunrise"), "sunset": rev.get("sunset"), "weather_forecast": rev.get("weather_forecast"), "safety_notes": rev.get("safety_notes"),
                "head_of_day_crew_member_id": rev.get("head_of_day_crew_member_id"),
                "schedule_items": [{k: i.get(k) for k in ("order_index", "scene_number", "int_ext", "day_night", "set_description", "page_count_eighths", "location_id")} for i in rev.get("schedule_items", [])],
                "cast_calls": [{k: c.get(k) for k in ("cast_member_id", "status_code", "pickup_time", "call_time", "makeup_hair_time", "on_set_time")} for c in rev.get("cast_calls", [])],
                "crew_calls": [{k: c.get(k) for k in ("crew_member_id", "call_time", "pickup_time", "note")} for c in rev.get("crew_calls", [])],
            },
        })
    return {
        "format": FORMAT, "exported_from": API,
        "production": {k: production.get(k) for k in ("id", "name", "working_title", "production_company", "status")},
        "contacts": list(contacts.values()),
        "crew": [{k: m.get(k) for k in ("id", "contact_id", "department", "position", "standard_call_time", "is_head_of_department")} for m in crew],
        "cast": [{k: a.get(k) for k in ("id", "contact_id", "character_name", "standard_pickup_time")} for a in cast],
        "locations": [{k: l.get(k) for k in ("id", "name", "address", "parking_notes", "nearest_hospital", "geo_lat", "geo_lng")} for l in locations],
        "members": [{k: m.get(k) for k in ("email", "role")} for m in members],
        "days": full_days,
    }


# ---- import -----------------------------------------------------------------------

class NotEmpty(SystemExit):
    pass


def import_production(data: dict, into: str | None = None) -> str:
    if data.get("format") != FORMAT:
        sys.exit(f"Unknown backup format {data.get('format')!r}; this script reads format {FORMAT}")
    if into:
        pid = into
        existing_days = call("GET", f"/api/v1/productions/{pid}/call-sheets")
        existing_crew = call("GET", f"/api/v1/productions/{pid}/crew-members")
        if existing_days or existing_crew:
            raise NotEmpty(f"Production {pid} already has {len(existing_days)} days and {len(existing_crew)} crew; import only into an empty one, never merged silently")
    else:
        p = data["production"]
        pid = call("POST", "/api/v1/productions", {"name": p["name"], "working_title": p.get("working_title"), "production_company": p.get("production_company"), "status": p.get("status") or "prep"})["id"]

    contact_map: dict[str, str] = {}
    for c in data["contacts"]:
        contact_map[c["id"]] = call("POST", "/api/v1/contacts", {"name": c["name"], "phone": c.get("phone"), "email": c.get("email")})["id"]
    crew_map: dict[str, str] = {}
    for m in data["crew"]:
        crew_map[m["id"]] = call("POST", f"/api/v1/productions/{pid}/crew-members", {
            "contact_id": contact_map[m["contact_id"]], "department": m["department"], "position": m["position"],
            "standard_call_time": m.get("standard_call_time"), "is_head_of_department": bool(m.get("is_head_of_department")),
        })["id"]
    cast_map: dict[str, str] = {}
    for a in data["cast"]:
        cast_map[a["id"]] = call("POST", f"/api/v1/productions/{pid}/cast-members", {
            "contact_id": contact_map[a["contact_id"]], "character_name": a["character_name"], "standard_pickup_time": a.get("standard_pickup_time"),
        })["id"]
    loc_map: dict[str, str] = {}
    for l in data["locations"]:
        # Coordinates travel with the address, so the API trusts them instead of asking the geocoder again.
        created = call("POST", f"/api/v1/productions/{pid}/locations", {
            "name": l["name"], "address": l.get("address"), "parking_notes": l.get("parking_notes"), "nearest_hospital": l.get("nearest_hospital"),
            "geo_lat": l.get("geo_lat"), "geo_lng": l.get("geo_lng"),
        })
        loc_map[l["id"]] = created["id"]
    for m in data["members"]:
        if m.get("email"):
            call("POST", f"/api/v1/productions/{pid}/members", {"email": m["email"], "role": m["role"]})
    for d in sorted(data["days"], key=lambda x: (x["shoot_date"], x["day_number"])):
        rev = d["revision"]
        payload = {
            "shoot_date": d["shoot_date"], "day_number": d["day_number"], "day_count": d["day_count"], "unit_name": d["unit_name"],
            "draft": d.get("status") == "draft",
            "initial_revision": {
                "created_by": "restore", "general_crew_call": rev.get("general_crew_call"), "shooting_call": rev.get("shooting_call"),
                "sunrise": rev.get("sunrise"), "sunset": rev.get("sunset"), "weather_forecast": rev.get("weather_forecast"), "safety_notes": rev.get("safety_notes"),
                "head_of_day_crew_member_id": crew_map.get(rev.get("head_of_day_crew_member_id") or ""),
                "schedule_items": [{**i, "location_id": loc_map.get(i.get("location_id") or "")} for i in rev.get("schedule_items", [])],
                "cast_calls": [{**c, "cast_member_id": cast_map[c["cast_member_id"]]} for c in rev.get("cast_calls", []) if c["cast_member_id"] in cast_map],
                "crew_calls": [{**c, "crew_member_id": crew_map[c["crew_member_id"]]} for c in rev.get("crew_calls", []) if c["crew_member_id"] in crew_map],
            },
        }
        created = call("POST", f"/api/v1/productions/{pid}/call-sheets", payload)
        if d.get("status") == "cancelled":
            call("POST", f"/api/v1/call-sheets/{created['id']}/cancel")
    return pid


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("export"); ex.add_argument("production_id", nargs="?"); ex.add_argument("--all", action="store_true"); ex.add_argument("--out-dir")
    im = sub.add_parser("import"); im.add_argument("file"); im.add_argument("--into")
    args = ap.parse_args(argv)
    if args.cmd == "export":
        if args.all:
            out = Path(args.out_dir or "."); out.mkdir(parents=True, exist_ok=True)
            for p in call("GET", "/api/v1/productions"):
                path = out / f"{p['id']}.json"
                path.write_text(json.dumps(export_production(p["id"]), ensure_ascii=False, indent=1))
                print(f"wrote {path} ({p['name']})", file=sys.stderr)
        else:
            if not args.production_id:
                sys.exit("export needs a production id or --all")
            print(json.dumps(export_production(args.production_id), ensure_ascii=False, indent=1))
    else:
        data = json.loads(Path(args.file).read_text())
        pid = import_production(data, into=args.into)
        print(pid)


if __name__ == "__main__":
    main()
