"""Fetch and cache historical weather data from Open-Meteo API."""
import os
import pandas as pd
import duckdb
import requests
from datetime import date, timedelta
from .config import get_location


OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"


def _fetch_weather(start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch daily weather from Open-Meteo for the user's location."""
    location = get_location()
    params = {
        "latitude": location["lat"],
        "longitude": location["lon"],
        "start_date": start_date,
        "end_date": end_date,
        "daily": "temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum",
        "temperature_unit": "fahrenheit",
        "timezone": "America/Chicago",
    }
    response = requests.get(OPEN_METEO_URL, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    daily = data.get("daily", {})
    if not daily or not daily.get("time"):
        return pd.DataFrame()

    df = pd.DataFrame({
        "date": pd.to_datetime(daily["time"]),
        "temp_max_f": daily.get("temperature_2m_max"),
        "temp_min_f": daily.get("temperature_2m_min"),
        "temp_mean_f": daily.get("temperature_2m_mean"),
        "precipitation_in": daily.get("precipitation_sum"),
    })
    return df


def get_weather_data(db_path: str, start_date: date, end_date: date) -> pd.DataFrame:
    """
    Get weather data, using DuckDB cache. Only fetches missing dates from API.
    """
    con = duckdb.connect(db_path)

    # Check if weather table exists
    table_exists = con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name = 'weather_daily'"
    ).fetchone()[0] > 0

    if table_exists:
        cached = con.execute("SELECT * FROM weather_daily ORDER BY date").fetchdf()
        if not cached.empty:
            cached_max = cached["date"].max().date()
            # Only fetch dates we're missing (after cache end)
            if cached_max >= end_date:
                con.close()
                return cached[
                    (cached["date"].dt.date >= start_date)
                    & (cached["date"].dt.date <= end_date)
                ]
            # Fetch the gap
            fetch_start = cached_max + timedelta(days=1)
        else:
            fetch_start = start_date
    else:
        cached = pd.DataFrame()
        fetch_start = start_date

    # Fetch missing data from API
    # Open-Meteo has a limit of ~2 years per request, so chunk if needed
    all_new = []
    current = fetch_start
    while current <= end_date:
        chunk_end = min(current + timedelta(days=730), end_date)
        try:
            df_chunk = _fetch_weather(current.isoformat(), chunk_end.isoformat())
            if not df_chunk.empty:
                all_new.append(df_chunk)
        except Exception:
            pass
        current = chunk_end + timedelta(days=1)

    if all_new:
        df_new = pd.concat(all_new, ignore_index=True)
        # Store in DuckDB
        if table_exists:
            con.execute("INSERT INTO weather_daily SELECT * FROM df_new")
        else:
            con.execute("CREATE TABLE weather_daily AS SELECT * FROM df_new")

        # Reload full dataset
        result = con.execute("SELECT * FROM weather_daily ORDER BY date").fetchdf()
    else:
        result = cached

    con.close()

    if result.empty:
        return result

    return result[
        (result["date"].dt.date >= start_date)
        & (result["date"].dt.date <= end_date)
    ]


def adjust_pace_for_heat(pace_min_per_mile: float, temp_f: float) -> float:
    """
    Adjust pace for temperature. Returns what the pace would be in ideal conditions (55-60F).
    Formula: ~1.5% pace penalty per 10°F above 60°F.
    """
    ideal_temp = 57.5
    if temp_f <= ideal_temp:
        return pace_min_per_mile
    penalty_pct = ((temp_f - ideal_temp) / 10) * 0.015
    return pace_min_per_mile / (1 + penalty_pct)
