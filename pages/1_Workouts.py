import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import sys
import os

sys.path.insert(0, str(Path(__file__).parent.parent))
from parser.cache import load_or_parse
from parser.weather import get_weather_data, adjust_pace_for_heat
from parser.cache import _db_path
from parser.theme import metric_card_css, COLORS, CHART_COLORS

st.set_page_config(page_title="Workouts", page_icon="💪", layout="wide")
st.markdown(metric_card_css(), unsafe_allow_html=True)
BASE_DIR = str(Path(__file__).parent.parent)


@st.cache_data(show_spinner=False)
def load_data():
    return load_or_parse(BASE_DIR)


data = load_data()
workouts = data["workouts"].copy()

if workouts.empty:
    st.warning("No workout data found.")
    st.stop()

# Sidebar filters
st.sidebar.title("Workout Filters")

activity_types = sorted(workouts["ActivityType"].unique())
selected_types = st.sidebar.multiselect(
    "Activity Type", activity_types, default=activity_types
)

min_date = workouts["StartDate"].min().date()
max_date = workouts["StartDate"].max().date()
date_range = st.sidebar.date_input(
    "Date Range", value=(min_date, max_date), min_value=min_date, max_value=max_date
)

# Apply filters
if len(date_range) == 2:
    start, end = date_range
    workouts = workouts[
        (workouts["StartDate"].dt.date >= start)
        & (workouts["StartDate"].dt.date <= end)
        & (workouts["ActivityType"].isin(selected_types))
    ]

st.title("Workouts")
st.markdown(f"**{len(workouts)}** workouts matching filters")
st.markdown("---")

# ---- Running-specific analysis ----
running = workouts[workouts["ActivityType"] == "Running"].copy()

if not running.empty and "DistanceWalkingRunning_sum_mi" in running.columns:
    st.subheader("Running Performance")

    # Compute pace (min/mile)
    running = running.dropna(subset=["DistanceWalkingRunning_sum_mi"])
    running = running[running["DistanceWalkingRunning_sum_mi"] > 0]
    running["Pace_min_per_mile"] = (
        (running["Duration_min"] - running["PausedDuration_min"])
        / running["DistanceWalkingRunning_sum_mi"]
    )
    # Filter out unrealistic paces
    running = running[(running["Pace_min_per_mile"] > 4) & (running["Pace_min_per_mile"] < 20)]

    col1, col2, col3 = st.columns(3)
    with col1:
        avg_pace = running["Pace_min_per_mile"].mean()
        st.metric("Avg Pace", f"{avg_pace:.1f} min/mi")
    with col2:
        avg_dist = running["DistanceWalkingRunning_sum_mi"].mean()
        st.metric("Avg Distance", f"{avg_dist:.2f} mi")
    with col3:
        total_miles = running["DistanceWalkingRunning_sum_mi"].sum()
        st.metric("Total Miles", f"{total_miles:.0f}")

    # Pace over time
    fig = px.scatter(
        running,
        x="StartDate",
        y="Pace_min_per_mile",
        color="DistanceWalkingRunning_sum_mi",
        title="Running Pace Over Time",
        labels={
            "Pace_min_per_mile": "Pace (min/mi)",
            "StartDate": "Date",
            "DistanceWalkingRunning_sum_mi": "Distance (mi)",
        },
        trendline="lowess",
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(height=400, margin=dict(t=40, b=20))
    st.plotly_chart(fig, use_container_width=True)

    # Year-over-year comparison
    running["Year"] = running["StartDate"].dt.year
    running["DayOfYear"] = running["StartDate"].dt.dayofyear

    fig = px.scatter(
        running,
        x="DayOfYear",
        y="Pace_min_per_mile",
        color="Year",
        title="Pace by Day of Year (Year-over-Year)",
        labels={"Pace_min_per_mile": "Pace (min/mi)", "DayOfYear": "Day of Year"},
        opacity=0.6,
        trendline="lowess",
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(height=400, margin=dict(t=40, b=20))
    st.plotly_chart(fig, use_container_width=True)

    # Heart rate during runs
    if "HeartRate_average_count/min" in running.columns:
        hr_runs = running.dropna(subset=["HeartRate_average_count/min"])
        if not hr_runs.empty:
            fig = px.scatter(
                hr_runs,
                x="Pace_min_per_mile",
                y="HeartRate_average_count/min",
                color="Year",
                title="Heart Rate vs Pace",
                labels={
                    "Pace_min_per_mile": "Pace (min/mi)",
                    "HeartRate_average_count/min": "Avg HR (bpm)",
                },
            )
            fig.update_layout(height=400, margin=dict(t=40, b=20))
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

# ---- All workouts analysis ----
st.subheader("All Workouts")

# Duration & calories over time
col1, col2 = st.columns(2)

with col1:
    monthly_stats = (
        workouts.groupby(workouts["StartDate"].dt.to_period("M"))
        .agg({"Duration_min": "sum", "ActivityType": "count"})
        .reset_index()
    )
    monthly_stats.columns = ["Month", "TotalMinutes", "Count"]
    monthly_stats["Month"] = monthly_stats["Month"].apply(lambda x: x.start_time)

    fig = px.bar(
        monthly_stats,
        x="Month",
        y="TotalMinutes",
        title="Monthly Training Volume (Minutes)",
        labels={"TotalMinutes": "Total Minutes", "Month": ""},
    )
    fig.update_layout(height=350, margin=dict(t=40, b=20))
    st.plotly_chart(fig, use_container_width=True)

with col2:
    if "ActiveEnergyBurned_sum_Cal" in workouts.columns:
        monthly_cal = (
            workouts.groupby(workouts["StartDate"].dt.to_period("M"))["ActiveEnergyBurned_sum_Cal"]
            .sum()
            .reset_index()
        )
        monthly_cal.columns = ["Month", "Calories"]
        monthly_cal["Month"] = monthly_cal["Month"].apply(lambda x: x.start_time)

        fig = px.bar(
            monthly_cal,
            x="Month",
            y="Calories",
            title="Monthly Calories Burned",
            labels={"Calories": "Active Calories", "Month": ""},
        )
        fig.update_layout(height=350, margin=dict(t=40, b=20))
        st.plotly_chart(fig, use_container_width=True)

# Average duration by activity type
avg_by_type = (
    workouts.groupby("ActivityType")
    .agg({"Duration_min": "mean", "ActivityType": "count"})
    .rename(columns={"ActivityType": "Count", "Duration_min": "AvgDuration"})
    .reset_index()
)
avg_by_type = avg_by_type.sort_values("AvgDuration", ascending=True)

fig = px.bar(
    avg_by_type,
    x="AvgDuration",
    y="ActivityType",
    orientation="h",
    title="Average Duration by Activity Type",
    labels={"AvgDuration": "Avg Duration (min)", "ActivityType": ""},
    text="Count",
)
fig.update_layout(height=max(300, len(avg_by_type) * 40), margin=dict(t=40, b=20))
st.plotly_chart(fig, use_container_width=True)

# ---- Weather-Adjusted Performance ----
st.markdown("---")
st.subheader("Weather-Adjusted Running Pace")

if not running.empty and "DistanceWalkingRunning_sum_mi" in running.columns:
    pace_runs = running.copy()
    if "Pace_min_per_mile" not in pace_runs.columns:
        pace_runs = pace_runs.dropna(subset=["DistanceWalkingRunning_sum_mi"])
        pace_runs = pace_runs[pace_runs["DistanceWalkingRunning_sum_mi"] > 0.5]
        pace_runs["Pace_min_per_mile"] = (
            (pace_runs["Duration_min"] - pace_runs["PausedDuration_min"])
            / pace_runs["DistanceWalkingRunning_sum_mi"]
        )
        pace_runs = pace_runs[(pace_runs["Pace_min_per_mile"] > 4) & (pace_runs["Pace_min_per_mile"] < 20)]

    if not pace_runs.empty:
        run_dates = pace_runs["StartDate"].copy()
        if hasattr(run_dates.dtype, "tz") and run_dates.dtype.tz:
            run_dates = run_dates.dt.tz_localize(None)

        try:
            weather = get_weather_data(
                _db_path(BASE_DIR),
                run_dates.min().date(),
                run_dates.max().date(),
            )

            if not weather.empty:
                pace_runs["run_date"] = run_dates.dt.date
                weather["weather_date"] = weather["date"].dt.date

                merged = pd.merge(
                    pace_runs,
                    weather[["weather_date", "temp_mean_f"]],
                    left_on="run_date",
                    right_on="weather_date",
                    how="inner",
                )

                if not merged.empty:
                    merged["Adjusted_Pace"] = merged.apply(
                        lambda r: adjust_pace_for_heat(r["Pace_min_per_mile"], r["temp_mean_f"]),
                        axis=1,
                    )

                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=merged["temp_mean_f"],
                        y=merged["Pace_min_per_mile"],
                        mode="markers",
                        name="Actual Pace",
                        marker=dict(size=6, opacity=0.6),
                    ))
                    fig.add_trace(go.Scatter(
                        x=merged["temp_mean_f"],
                        y=merged["Adjusted_Pace"],
                        mode="markers",
                        name="Heat-Adjusted Pace",
                        marker=dict(size=6, opacity=0.6, symbol="diamond"),
                    ))
                    fig.update_yaxes(autorange="reversed")
                    fig.update_layout(
                        title="Running Pace vs Temperature (Dallas, TX)",
                        xaxis_title="Temperature (°F)",
                        yaxis_title="Pace (min/mi)",
                        height=400,
                        margin=dict(t=40, b=20),
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    # Stats
                    hot_runs = merged[merged["temp_mean_f"] >= 85]
                    cool_runs = merged[merged["temp_mean_f"] <= 65]
                    if len(hot_runs) >= 3 and len(cool_runs) >= 3:
                        heat_penalty = hot_runs["Pace_min_per_mile"].mean() - cool_runs["Pace_min_per_mile"].mean()
                        st.caption(
                            f"Hot days (>85°F): avg pace **{hot_runs['Pace_min_per_mile'].mean():.1f} min/mi** | "
                            f"Cool days (<65°F): avg pace **{cool_runs['Pace_min_per_mile'].mean():.1f} min/mi** | "
                            f"Heat penalty: **+{heat_penalty:.1f} min/mi**"
                        )
                else:
                    st.info("Could not match weather data to run dates.")
            else:
                st.info("No weather data available.")
        except Exception as e:
            st.warning(f"Could not load weather data: {e}")
else:
    st.info("No running data available for weather analysis.")
