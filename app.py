import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from parser.cache import load_or_parse
from parser.config import profile_exists, load_profile, save_profile, RACE_PRESETS
from parser.theme import metric_card_css, COLORS, CHART_COLORS

st.set_page_config(
    page_title="Apple Health Dashboard",
    page_icon="🏃",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject theme CSS
st.markdown(metric_card_css(), unsafe_allow_html=True)

BASE_DIR = str(Path(__file__).parent)

# ============================================================================
# ONBOARDING WIZARD (first launch only)
# ============================================================================
if not profile_exists():
    st.title("Welcome to Apple Health Dashboard")
    st.markdown("Let's set up your profile to personalize insights and benchmarks.")
    st.markdown("---")

    with st.form("onboarding"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Name", placeholder="Jason")
            birth_year = st.number_input("Birth Year", min_value=1940, max_value=2010, value=1982)
            sex = st.selectbox("Sex", ["Male", "Female"])
        with col2:
            city = st.text_input("City (for weather data)", value="Dallas, TX")
            lat = st.number_input("Latitude", value=32.7767, format="%.4f")
            lon = st.number_input("Longitude", value=-96.7970, format="%.4f")

        st.markdown("### Training Goal")
        race_type = st.selectbox("Goal", list(RACE_PRESETS.keys()), index=0)
        race_date = st.date_input("Target Date", value=pd.Timestamp("2026-10-01"))

        submitted = st.form_submit_button("Save & Continue", type="primary")
        if submitted:
            profile = {
                "name": name,
                "birth_year": birth_year,
                "sex": sex,
                "city": city,
                "lat": lat,
                "lon": lon,
                "race_type": race_type,
                "race_date": race_date.isoformat(),
            }
            save_profile(profile)
            st.rerun()

    st.stop()

# ============================================================================
# MAIN DASHBOARD
# ============================================================================
profile = load_profile()


@st.cache_data(show_spinner=False)
def load_data():
    return load_or_parse(BASE_DIR)


with st.spinner("Loading health data..."):
    try:
        data = load_data()
    except FileNotFoundError as e:
        st.error(str(e))
        st.stop()

workouts = data["workouts"]
resting_hr = data["resting_hr"]
hrv = data["hrv"]
sleep = data["sleep"]

# Normalize tz
for df_name in ["workouts"]:
    df = data[df_name]
    if not df.empty and hasattr(df["StartDate"].dtype, "tz") and df["StartDate"].dtype.tz:
        workouts = df.copy()
        workouts["StartDate"] = workouts["StartDate"].dt.tz_localize(None)

# Sidebar
st.sidebar.markdown(f"### {profile.get('name', 'Athlete') or 'Athlete'}")
st.sidebar.caption(f"{profile.get('race_type', '')} — {profile.get('race_date', '')}")
st.sidebar.markdown("---")

if not workouts.empty:
    min_date = workouts["StartDate"].min().date()
    max_date = workouts["StartDate"].max().date()
    date_range = st.sidebar.date_input(
        "Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
    if len(date_range) == 2:
        start, end = date_range
        mask = (workouts["StartDate"].dt.date >= start) & (workouts["StartDate"].dt.date <= end)
        workouts = workouts[mask]

# Title
st.title("Dashboard")
st.markdown("---")

# KPIs
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Workouts", len(workouts))

with col2:
    if not workouts.empty:
        days_span = (workouts["StartDate"].max() - workouts["StartDate"].min()).days
        weeks = max(days_span / 7, 1)
        st.metric("Avg/Week", f"{len(workouts) / weeks:.1f}")
    else:
        st.metric("Avg/Week", "N/A")

with col3:
    hr_data = data["heart_rate"]
    if not hr_data.empty:
        hr_local = hr_data.copy()
        if hasattr(hr_local["startDate"].dtype, "tz") and hr_local["startDate"].dtype.tz:
            hr_local["startDate"] = hr_local["startDate"].dt.tz_localize(None)
        recent_hr = hr_local[hr_local["startDate"] >= (pd.Timestamp.now() - pd.Timedelta(days=7))]
        if not recent_hr.empty:
            daily_p5 = recent_hr.groupby(recent_hr["startDate"].dt.date)["value"].quantile(0.05)
            st.metric("Resting HR", f"{daily_p5.mean():.0f} bpm")
        else:
            st.metric("Resting HR", "N/A")
    else:
        st.metric("Resting HR", "N/A")

with col4:
    if not sleep.empty:
        sleep_actual = sleep[sleep["value"].isin(["Asleep", "AsleepCore", "AsleepDeep", "AsleepREM"])]
        if not sleep_actual.empty and "duration_hours" in sleep_actual.columns:
            sl = sleep_actual.copy()
            if hasattr(sl["startDate"].dtype, "tz") and sl["startDate"].dtype.tz:
                sl["startDate"] = sl["startDate"].dt.tz_localize(None)
            nightly = sl.groupby(sl["startDate"].dt.date)["duration_hours"].sum()
            avg_sleep = nightly.tail(14).mean()
            st.metric("Sleep (14d)", f"{avg_sleep:.1f} hrs")
        else:
            st.metric("Sleep", "N/A")
    else:
        st.metric("Sleep", "N/A")

st.markdown("---")

# Weekly volume chart
st.subheader("Weekly Training Volume")
if not workouts.empty:
    weekly = workouts.groupby(workouts["StartDate"].dt.to_period("W").apply(lambda x: x.start_time)).agg(
        {"Duration_min": "sum", "ActivityType": "count"}
    ).reset_index()
    weekly.columns = ["Week", "Minutes", "Count"]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=weekly["Week"], y=weekly["Minutes"],
        marker_color=COLORS["primary"], name="Minutes",
    ))
    fig.update_layout(
        yaxis_title="Total Minutes", xaxis_title="",
        height=300, margin=dict(t=20, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)

# Activity distribution
st.subheader("Activity Mix")
if not workouts.empty:
    col1, col2 = st.columns(2)

    with col1:
        type_counts = workouts["ActivityType"].value_counts().reset_index()
        type_counts.columns = ["Activity", "Count"]
        fig = px.pie(
            type_counts, values="Count", names="Activity",
            color_discrete_sequence=CHART_COLORS,
        )
        fig.update_layout(height=350, margin=dict(t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        monthly_types = (
            workouts.groupby([workouts["StartDate"].dt.to_period("M"), "ActivityType"])
            .size().reset_index()
        )
        monthly_types.columns = ["Month", "Activity", "Count"]
        monthly_types["Month"] = monthly_types["Month"].apply(lambda x: x.start_time)
        fig = px.bar(
            monthly_types, x="Month", y="Count", color="Activity",
            color_discrete_sequence=CHART_COLORS,
        )
        fig.update_layout(height=350, margin=dict(t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)

# Recent HR + HRV trends
hr_data = data["heart_rate"]
if not hr_data.empty or not hrv.empty:
    st.subheader("Vitals")
    col1, col2 = st.columns(2)

    with col1:
        if not hr_data.empty:
            hr_local = hr_data.copy()
            if hasattr(hr_local["startDate"].dtype, "tz") and hr_local["startDate"].dtype.tz:
                hr_local["startDate"] = hr_local["startDate"].dt.tz_localize(None)
            # Derive resting HR from daily 5th percentile of all HR readings
            import numpy as np
            daily_p5 = hr_local.groupby(hr_local["startDate"].dt.date)["value"].quantile(0.05).reset_index()
            daily_p5.columns = ["Date", "RestingHR"]
            daily_p5["Date"] = pd.to_datetime(daily_p5["Date"])
            rhr_weekly = daily_p5.set_index("Date").resample("W")["RestingHR"].mean().reset_index()
            fig = px.line(rhr_weekly, x="Date", y="RestingHR",
                          color_discrete_sequence=[COLORS["primary"]])
            fig.update_layout(title="Resting HR (Weekly)", yaxis_title="BPM",
                              xaxis_title="", height=280, margin=dict(t=40, b=20))
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        if not hrv.empty:
            hrv_d = hrv.copy()
            if hasattr(hrv_d["startDate"].dtype, "tz") and hrv_d["startDate"].dtype.tz:
                hrv_d["startDate"] = hrv_d["startDate"].dt.tz_localize(None)
            hrv_weekly = hrv_d.set_index("startDate").resample("W")["value"].mean().reset_index()
            fig = px.line(hrv_weekly, x="startDate", y="value",
                          color_discrete_sequence=[COLORS["secondary"]])
            fig.update_layout(title="HRV (Weekly)", yaxis_title="ms",
                              xaxis_title="", height=280, margin=dict(t=40, b=20))
            st.plotly_chart(fig, use_container_width=True)
