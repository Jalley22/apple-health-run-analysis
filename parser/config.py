"""User profile configuration — loads from user_profile.json, falls back to defaults."""
import json
import os
from datetime import date
from pathlib import Path

_PROFILE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "user_profile.json")

# Race presets: {type: {swim_mi, bike_mi, run_mi}}
RACE_PRESETS = {
    "Half Ironman (70.3)": {"swim_mi": 1.2, "bike_mi": 56, "run_mi": 13.1},
    "Full Ironman (140.6)": {"swim_mi": 2.4, "bike_mi": 112, "run_mi": 26.2},
    "Olympic Triathlon": {"swim_mi": 0.93, "bike_mi": 24.8, "run_mi": 6.2},
    "Sprint Triathlon": {"swim_mi": 0.47, "bike_mi": 12.4, "run_mi": 3.1},
    "Marathon": {"swim_mi": 0, "bike_mi": 0, "run_mi": 26.2},
    "Half Marathon": {"swim_mi": 0, "bike_mi": 0, "run_mi": 13.1},
    "10K": {"swim_mi": 0, "bike_mi": 0, "run_mi": 6.2},
    "5K": {"swim_mi": 0, "bike_mi": 0, "run_mi": 3.1},
    "General Fitness": {"swim_mi": 0, "bike_mi": 0, "run_mi": 0},
    "Custom": {"swim_mi": 0, "bike_mi": 0, "run_mi": 0},
}

_DEFAULTS = {
    "name": "",
    "birth_year": 1982,
    "sex": "Male",
    "city": "Dallas, TX",
    "lat": 32.7767,
    "lon": -96.7970,
    "race_type": "Half Ironman (70.3)",
    "race_date": "2026-10-01",
    "custom_swim_mi": 0,
    "custom_bike_mi": 0,
    "custom_run_mi": 0,
}


def profile_exists() -> bool:
    return os.path.exists(_PROFILE_PATH)


def load_profile() -> dict:
    if profile_exists():
        with open(_PROFILE_PATH, "r") as f:
            saved = json.load(f)
        # Merge with defaults for any missing keys
        profile = {**_DEFAULTS, **saved}
    else:
        profile = dict(_DEFAULTS)
    return profile


def save_profile(profile: dict):
    with open(_PROFILE_PATH, "w") as f:
        json.dump(profile, f, indent=2)


def get_age(as_of: date = None) -> int:
    profile = load_profile()
    if as_of is None:
        as_of = date.today()
    return as_of.year - profile["birth_year"]


def get_age_group() -> str:
    age = get_age()
    lower = (age // 5) * 5
    return f"{lower}-{lower + 4}"


def get_location() -> dict:
    profile = load_profile()
    return {"city": profile["city"], "lat": profile["lat"], "lon": profile["lon"]}


def get_race_config() -> dict:
    profile = load_profile()
    race_type = profile.get("race_type", "Half Ironman (70.3)")
    race_date_str = profile.get("race_date", "2026-10-01")

    try:
        race_date = date.fromisoformat(race_date_str)
    except (ValueError, TypeError):
        race_date = date(2026, 10, 1)

    if race_type == "Custom":
        distances = {
            "swim_mi": profile.get("custom_swim_mi", 0),
            "bike_mi": profile.get("custom_bike_mi", 0),
            "run_mi": profile.get("custom_run_mi", 0),
        }
    else:
        distances = RACE_PRESETS.get(race_type, RACE_PRESETS["Half Ironman (70.3)"])

    return {
        "race_type": race_type,
        "race_date": race_date,
        "distances": distances,
    }
