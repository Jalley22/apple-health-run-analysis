import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from parser.cache import load_or_parse
from parser.config import get_age, get_age_group
from parser.benchmarks import (
    get_resting_hr_benchmarks,
    get_max_hr_expected,
    get_hrv_benchmarks,
    get_pace_benchmarks,
    estimate_fitness_age,
)
from parser.theme import metric_card_css, COLORS

st.set_page_config(page_title="Benchmarks", page_icon="📊", layout="wide")
st.markdown(metric_card_css(), unsafe_allow_html=True)
BASE_DIR = str(Path(__file__).parent.parent)


@st.cache_data(show_spinner=False)
def load_data():
    return load_or_parse(BASE_DIR)


data = load_data()
age = get_age()
age_group = get_age_group()

st.title(f"Age-Group Benchmarks")
st.markdown(f"**Age:** {age} | **Group:** {age_group} | Male")
st.markdown("---")


def gauge_chart(value, title, ranges, unit="", reverse=False):
    """Create a gauge chart with colored ranges."""
    if reverse:
        # Lower is better (HR, pace)
        colors = ["#2ECC40", "#FFDC00", "#FF851B", "#FF4136"]
        steps = [
            {"range": [ranges[0], ranges[1]], "color": colors[0]},
            {"range": [ranges[1], ranges[2]], "color": colors[1]},
            {"range": [ranges[2], ranges[3]], "color": colors[2]},
            {"range": [ranges[3], ranges[4]], "color": colors[3]},
        ]
    else:
        # Higher is better (HRV, exercise mins)
        colors = ["#FF4136", "#FF851B", "#FFDC00", "#2ECC40"]
        steps = [
            {"range": [ranges[0], ranges[1]], "color": colors[0]},
            {"range": [ranges[1], ranges[2]], "color": colors[1]},
            {"range": [ranges[2], ranges[3]], "color": colors[2]},
            {"range": [ranges[3], ranges[4]], "color": colors[3]},
        ]

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={"text": title},
        number={"suffix": f" {unit}"},
        gauge={
            "axis": {"range": [ranges[0], ranges[-1]]},
            "bar": {"color": "#333"},
            "steps": steps,
            "threshold": {
                "line": {"color": "black", "width": 4},
                "thickness": 0.75,
                "value": value,
            },
        },
    ))
    fig.update_layout(height=250, margin=dict(t=50, b=10, l=30, r=30))
    return fig


# Compute current values
hr_data = data.get("heart_rate", pd.DataFrame())
workouts = data.get("workouts", pd.DataFrame())
hrv_data = data.get("hrv", pd.DataFrame())

# Resting HR (daily 5th percentile, last 30 days)
current_rhr = None
if not hr_data.empty:
    hr_data_local = hr_data.copy()
    if hasattr(hr_data_local["startDate"].dtype, "tz") and hr_data_local["startDate"].dtype.tz:
        hr_data_local["startDate"] = hr_data_local["startDate"].dt.tz_localize(None)
    recent_hr = hr_data_local[hr_data_local["startDate"] >= (pd.Timestamp.now() - pd.Timedelta(days=30))]
    if not recent_hr.empty:
        daily_p5 = recent_hr.groupby(recent_hr["startDate"].dt.date)["value"].quantile(0.05)
        current_rhr = daily_p5.mean()

# Running pace (last 20 runs)
current_pace = None
if not workouts.empty:
    wk = workouts.copy()
    if hasattr(wk["StartDate"].dtype, "tz") and wk["StartDate"].dtype.tz:
        wk["StartDate"] = wk["StartDate"].dt.tz_localize(None)
    running = wk[wk["ActivityType"] == "Running"].copy()
    if "DistanceWalkingRunning_sum_mi" in running.columns:
        running = running.dropna(subset=["DistanceWalkingRunning_sum_mi"])
        running = running[running["DistanceWalkingRunning_sum_mi"] > 0.5]
        running["Pace"] = (
            (running["Duration_min"] - running["PausedDuration_min"])
            / running["DistanceWalkingRunning_sum_mi"]
        )
        running = running[(running["Pace"] > 4) & (running["Pace"] < 20)]
        if len(running) >= 5:
            current_pace = running.sort_values("StartDate").tail(20)["Pace"].mean()

# HRV
current_hrv = None
if not hrv_data.empty:
    current_hrv = hrv_data.sort_values("startDate").tail(14)["value"].mean()

# Weekly exercise minutes (last 4 weeks)
weekly_exercise = None
if not workouts.empty:
    wk = workouts.copy()
    if hasattr(wk["StartDate"].dtype, "tz") and wk["StartDate"].dtype.tz:
        wk["StartDate"] = wk["StartDate"].dt.tz_localize(None)
    recent_wk = wk[wk["StartDate"] >= (pd.Timestamp.now() - pd.Timedelta(weeks=4))]
    if not recent_wk.empty:
        weekly_exercise = recent_wk["Duration_min"].sum() / 4

# Display gauges
col1, col2 = st.columns(2)

with col1:
    if current_rhr is not None:
        rhr_bench = get_resting_hr_benchmarks()
        exc, good, avg = rhr_bench["thresholds"]
        fig = gauge_chart(current_rhr, "Resting Heart Rate", [40, exc, good, avg, 100], "bpm", reverse=True)
        st.plotly_chart(fig, use_container_width=True)

        category = "Excellent" if current_rhr < exc else "Good" if current_rhr < good else "Average" if current_rhr < avg else "Below Average"
        st.caption(f"Your resting HR: **{current_rhr:.0f} bpm** — {category} for age {age}")
    else:
        st.info("Not enough HR data for resting HR benchmark")

with col2:
    if current_pace is not None:
        pace_bench = get_pace_benchmarks()
        exc, good, avg = pace_bench["thresholds"]
        fig = gauge_chart(current_pace, "Running Pace", [5, exc, good, avg, 14], "min/mi", reverse=True)
        st.plotly_chart(fig, use_container_width=True)

        category = "Excellent" if current_pace < exc else "Good" if current_pace < good else "Average" if current_pace < avg else "Below Average"
        st.caption(f"Your pace: **{current_pace:.1f} min/mi** — {category} for age {age}")
    else:
        st.info("Not enough running data for pace benchmark")

col3, col4 = st.columns(2)

with col3:
    if current_hrv is not None:
        hrv_bench = get_hrv_benchmarks()
        exc, good, avg = hrv_bench["thresholds"]
        fig = gauge_chart(current_hrv, "HRV (SDNN)", [0, avg, good, exc, 80], "ms", reverse=False)
        st.plotly_chart(fig, use_container_width=True)

        category = "Excellent" if current_hrv > exc else "Good" if current_hrv > good else "Average" if current_hrv > avg else "Below Average"
        st.caption(f"Your HRV: **{current_hrv:.0f} ms** — {category} for age {age}")
    else:
        st.info("Not enough HRV data (requires overnight wear)")

with col4:
    if weekly_exercise is not None:
        fig = gauge_chart(weekly_exercise, "Weekly Exercise", [0, 75, 150, 300, 500], "min", reverse=False)
        st.plotly_chart(fig, use_container_width=True)

        category = "Excellent" if weekly_exercise > 300 else "Good" if weekly_exercise > 150 else "Average" if weekly_exercise > 75 else "Below Average"
        st.caption(f"Your weekly avg: **{weekly_exercise:.0f} min** — {category}")
    else:
        st.info("Not enough workout data")

# Fitness Age
st.markdown("---")
st.subheader("Estimated Fitness Age")

if current_rhr is not None and current_pace is not None:
    fitness_age = estimate_fitness_age(current_rhr, current_pace)
    diff = fitness_age - age

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Chronological Age", f"{age}")
    with col2:
        st.metric("Fitness Age", f"{fitness_age}", delta=f"{diff:+d} years", delta_color="inverse")
    with col3:
        max_hr_expected = get_max_hr_expected()
        st.metric("Expected Max HR", f"{max_hr_expected:.0f} bpm")

    if diff < -3:
        st.success(f"Your fitness age is {abs(diff)} years younger than your actual age.")
    elif diff > 3:
        st.warning(f"Your fitness age is {diff} years older — room for improvement.")
    else:
        st.info("Your fitness age is close to your chronological age.")
else:
    st.info("Need both resting HR and running pace data to estimate fitness age.")
