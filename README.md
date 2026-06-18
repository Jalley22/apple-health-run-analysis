# Apple Health Dashboard

A local Streamlit app that turns your Apple Health export into an interactive analytics dashboard with training insights, age-group benchmarks, weather-adjusted performance, and race readiness tracking.

## Features

- **Workouts** — All activity types with running pace analysis, year-over-year comparisons, and weather-adjusted performance
- **Heart Rate & HRV** — Resting HR trends (derived from raw readings), HRV analysis, training load correlations
- **Sleep** — Duration trends, stage breakdown, bedtime consistency, sleep vs resting HR
- **Insights** — Auto-generated trend alerts, anomaly detection, health risk flags, and cross-metric correlations
- **Benchmarks** — Compare your metrics against age-group norms (males/females 30-54), fitness age estimate
- **Race Readiness** — Configurable goal tracker (Half Ironman, Marathon, 10K, etc.) with readiness score, gap analysis, projected finish time, and training recommendations
- **Settings** — Configurable profile (age, location, race goals) that adapts all analytics

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Export your data from iPhone:
#    Health app → profile icon → Export All Health Data
#    Place export.zip in this folder

# 3. Run the dashboard
streamlit run app.py
```

**First run:** Parses the XML (~90 seconds for 3M+ records), stores in DuckDB.  
**Subsequent runs:** Loads from database in seconds. New exports only parse incremental data.

## How It Works

```
apple-health-run-analysis/
├── app.py                      # Main dashboard + onboarding wizard
├── pages/
│   ├── 1_Workouts.py           # All workouts + weather-adjusted pace
│   ├── 2_Heart_Rate.py         # HR & HRV trends
│   ├── 3_Sleep.py              # Sleep analysis
│   ├── 4_Insights.py           # Auto-generated health insights
│   ├── 5_Benchmarks.py         # Age-group comparisons
│   ├── 6_Race_Readiness.py     # Race goal tracker
│   └── 7_Settings.py           # Profile configuration
├── parser/
│   ├── cache.py                # DuckDB incremental storage
│   ├── workouts.py             # Workout XML parser
│   ├── records.py              # Single-pass HR/HRV/sleep parser
│   ├── insights.py             # Insight generation engine
│   ├── benchmarks.py           # Age-group health norms
│   ├── weather.py              # Open-Meteo API + caching
│   ├── race_readiness.py       # Readiness scoring engine
│   ├── config.py               # Profile management (JSON-backed)
│   └── theme.py                # Chart colors & styling
├── .streamlit/config.toml      # Streamlit theme
├── export.zip                  # Your Apple Health export (not committed)
├── health_data.duckdb          # Parsed data cache (not committed)
└── user_profile.json           # Your settings (not committed)
```

## Data Pipeline

1. **Extract** — Unzips `export.zip` to get `export.xml`
2. **Parse** — Single-pass lxml iterparse through 3M+ records, extracting workouts, HR, HRV, and sleep
3. **Store** — Saves to local DuckDB database
4. **Incremental** — On new exports, only parses records newer than what's already stored
5. **Analyze** — Streamlit pages query DuckDB and render interactive Plotly charts

## Configuration

On first launch, an onboarding wizard collects your profile. Change anytime via the Settings page:

- **Name, birth year, sex** — Used for age-group benchmarks
- **Location** — Fetches historical weather from Open-Meteo (free, no API key)
- **Race goal** — Presets for Half/Full Ironman, Olympic/Sprint Tri, Marathon, Half Marathon, 10K, 5K, or Custom distances

## Notes

- Apple Watch stopped recording Resting HR and HRV after watchOS 11 if not worn at night. The dashboard derives resting HR from the daily 5th percentile of all HR readings as a proxy.
- Weather data is cached in DuckDB to avoid re-fetching on each load.
- All timestamps are normalized to local time (America/Chicago) for display.
