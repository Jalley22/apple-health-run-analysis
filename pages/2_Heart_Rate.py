import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from parser.cache import load_or_parse
from parser.theme import metric_card_css, COLORS

st.set_page_config(page_title="Heart Rate & HRV", page_icon="❤️", layout="wide")
st.markdown(metric_card_css(), unsafe_allow_html=True)
BASE_DIR = str(Path(__file__).parent.parent)


@st.cache_data(show_spinner=False)
def load_data():
    return load_or_parse(BASE_DIR)


@st.cache_data(show_spinner=False)
def compute_daily_hr_stats(heart_rate: pd.DataFrame) -> pd.DataFrame:
    """Compute daily HR stats from raw readings: min, 5th percentile, median, max."""
    hr = heart_rate.copy()
    hr["Date"] = hr["startDate"].dt.date
    daily = hr.groupby("Date")["value"].agg(
        DailyMin="min",
        DailyP5=lambda x: np.percentile(x.dropna(), 5) if len(x.dropna()) > 0 else np.nan,
        DailyMedian="median",
        DailyMax="max",
        ReadingCount="count",
    ).reset_index()
    daily["Date"] = pd.to_datetime(daily["Date"])
    return daily


data = load_data()
heart_rate = data["heart_rate"]
resting_hr = data["resting_hr"]
hrv = data["hrv"]
workouts = data["workouts"]

st.title("Heart Rate & HRV")
st.markdown("---")

# Date filter from raw HR data (full range)
st.sidebar.title("Filters")
if not heart_rate.empty:
    min_date = heart_rate["startDate"].min().date()
    max_date = heart_rate["startDate"].max().date()
    date_range = st.sidebar.date_input(
        "Date Range", value=(min_date, max_date), min_value=min_date, max_value=max_date
    )
else:
    date_range = ()

# ---- Resting Heart Rate ----
st.subheader("Resting Heart Rate")

if not heart_rate.empty:
    daily_stats = compute_daily_hr_stats(heart_rate)

    if len(date_range) == 2:
        daily_stats = daily_stats[
            (daily_stats["Date"].dt.date >= date_range[0])
            & (daily_stats["Date"].dt.date <= date_range[1])
        ]

    # Use 5th percentile as estimated resting HR (best proxy without overnight data)
    col1, col2, col3 = st.columns(3)
    with col1:
        current_rhr = daily_stats.tail(7)["DailyP5"].mean()
        st.metric("Current (7d avg)", f"{current_rhr:.0f} bpm")
    with col2:
        all_time_rhr = daily_stats["DailyP5"].mean()
        st.metric("All-time Average", f"{all_time_rhr:.0f} bpm")
    with col3:
        lowest_rhr = daily_stats["DailyP5"].min()
        st.metric("Lowest Recorded", f"{lowest_rhr:.0f} bpm")

    # Weekly trend — derived resting HR
    daily_stats_indexed = daily_stats.set_index("Date")
    rhr_weekly = daily_stats_indexed.resample("W")["DailyP5"].mean().reset_index()
    rhr_weekly.columns = ["Date", "RestingHR"]

    # Also overlay the official RestingHeartRate data where available
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=rhr_weekly["Date"], y=rhr_weekly["RestingHR"],
        mode="lines", name="Estimated Resting HR (5th %ile)",
        line=dict(width=2, color="#636EFA"),
    ))

    if not resting_hr.empty:
        official_rhr = resting_hr.copy()
        if len(date_range) == 2:
            official_rhr = official_rhr[
                (official_rhr["startDate"].dt.date >= date_range[0])
                & (official_rhr["startDate"].dt.date <= date_range[1])
            ]
        official_weekly = official_rhr.set_index("startDate").resample("W")["value"].mean().reset_index()
        fig.add_trace(go.Scatter(
            x=official_weekly["startDate"], y=official_weekly["value"],
            mode="lines", name="Apple Official Resting HR",
            line=dict(width=2, color="#EF553B", dash="dot"),
        ))

    fig.add_hline(y=all_time_rhr, line_dash="dash", line_color="gray",
                  annotation_text=f"Avg: {all_time_rhr:.0f}")
    fig.update_layout(
        title="Resting Heart Rate Trend (Weekly)",
        yaxis_title="BPM",
        xaxis_title="Date",
        height=400,
        margin=dict(t=40, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "**Note:** Apple stopped recording official Resting HR after Jan 2025 "
        "(requires overnight wear). The blue line uses the daily 5th percentile "
        "of all HR readings as a proxy."
    )

    # Monthly boxplot of daily resting estimate
    daily_stats["Month"] = daily_stats["Date"].dt.to_period("M").apply(lambda x: x.start_time)
    fig = px.box(
        daily_stats,
        x="Month",
        y="DailyP5",
        title="Estimated Resting HR Distribution by Month",
        labels={"DailyP5": "BPM (5th %ile)", "Month": ""},
    )
    fig.update_layout(height=350, margin=dict(t=40, b=20))
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No heart rate data found.")

st.markdown("---")

# ---- HRV ----
st.subheader("Heart Rate Variability (SDNN)")

if not hrv.empty:
    hrv_data = hrv.copy()
    if len(date_range) == 2:
        hrv_data = hrv_data[
            (hrv_data["startDate"].dt.date >= date_range[0])
            & (hrv_data["startDate"].dt.date <= date_range[1])
        ]

    col1, col2, col3 = st.columns(3)
    with col1:
        current_hrv = hrv_data.sort_values("startDate").tail(7)["value"].mean()
        st.metric("Current (7d avg)", f"{current_hrv:.0f} ms")
    with col2:
        avg_hrv = hrv_data["value"].mean()
        st.metric("All-time Average", f"{avg_hrv:.0f} ms")
    with col3:
        highest_hrv = hrv_data["value"].max()
        st.metric("Highest Recorded", f"{highest_hrv:.0f} ms")

    # Weekly trend
    hrv_weekly = hrv_data.set_index("startDate").resample("W")["value"].mean().reset_index()
    fig = px.line(
        hrv_weekly,
        x="startDate",
        y="value",
        title="HRV Trend (Weekly Average)",
        labels={"value": "SDNN (ms)", "startDate": "Date"},
    )
    fig.add_hline(y=avg_hrv, line_dash="dash", line_color="gray",
                  annotation_text=f"Avg: {avg_hrv:.0f}")
    fig.update_layout(height=350, margin=dict(t=40, b=20))
    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "**Note:** HRV (SDNN) requires overnight wear to record. "
        "Data stops at Jan 2025 — no workaround available without sleep tracking."
    )

    # HRV vs Training Load
    if not workouts.empty:
        st.subheader("HRV vs Training Load")
        weekly_volume = (
            workouts.set_index("StartDate")
            .resample("W")["Duration_min"]
            .sum()
            .reset_index()
        )
        weekly_volume.columns = ["Week", "TrainingMinutes"]

        hrv_weekly_merged = hrv_weekly.copy()
        hrv_weekly_merged["Week"] = hrv_weekly_merged["startDate"].dt.tz_localize(None).dt.to_period("W").apply(
            lambda x: x.start_time
        )
        weekly_volume["Week"] = pd.to_datetime(weekly_volume["Week"]).dt.tz_localize(None)

        merged = pd.merge(hrv_weekly_merged, weekly_volume, on="Week", how="inner")

        if not merged.empty:
            fig = px.scatter(
                merged,
                x="TrainingMinutes",
                y="value",
                trendline="ols",
                title="Weekly HRV vs Training Volume",
                labels={"value": "HRV (ms)", "TrainingMinutes": "Training Minutes"},
            )
            fig.update_layout(height=400, margin=dict(t=40, b=20))
            st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No HRV data found.")

st.markdown("---")

# ---- Workout HR Summary ----
st.subheader("Workout Heart Rate by Activity")

if not workouts.empty and "HeartRate_average_count/min" in workouts.columns:
    hr_workouts = workouts.dropna(subset=["HeartRate_average_count/min"]).copy()
    if len(date_range) == 2:
        hr_workouts = hr_workouts[
            (hr_workouts["StartDate"].dt.date >= date_range[0])
            & (hr_workouts["StartDate"].dt.date <= date_range[1])
        ]
    if not hr_workouts.empty:
        fig = px.box(
            hr_workouts,
            x="ActivityType",
            y="HeartRate_average_count/min",
            title="Average HR During Workouts by Activity",
            labels={"HeartRate_average_count/min": "Avg HR (bpm)", "ActivityType": ""},
        )
        fig.update_layout(height=400, margin=dict(t=40, b=20))
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No workout heart rate data available.")
