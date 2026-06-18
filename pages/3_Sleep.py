import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from parser.cache import load_or_parse
from parser.theme import metric_card_css, COLORS

st.set_page_config(page_title="Sleep", page_icon="🌙", layout="wide")
st.markdown(metric_card_css(), unsafe_allow_html=True)
BASE_DIR = str(Path(__file__).parent.parent)


@st.cache_data(show_spinner=False)
def load_data():
    return load_or_parse(BASE_DIR)


data = load_data()
sleep = data["sleep"]

st.title("Sleep Analysis")
st.markdown("---")

if sleep.empty:
    st.warning("No sleep data found in your export.")
    st.stop()

# Filter to actual sleep records (not just InBed)
sleep_stages = ["Asleep", "AsleepCore", "AsleepDeep", "AsleepREM"]
in_bed_values = ["InBed"]

sleep_data = sleep.copy()

# Date filter
st.sidebar.title("Filters")
min_date = sleep_data["startDate"].min().date()
max_date = sleep_data["startDate"].max().date()
date_range = st.sidebar.date_input(
    "Date Range", value=(min_date, max_date), min_value=min_date, max_value=max_date
)
if len(date_range) == 2:
    sleep_data = sleep_data[
        (sleep_data["startDate"].dt.date >= date_range[0])
        & (sleep_data["startDate"].dt.date <= date_range[1])
    ]

# Compute nightly totals
actual_sleep = sleep_data[sleep_data["value"].isin(sleep_stages)].copy()

if actual_sleep.empty:
    st.warning("No sleep stage data found. Your Apple Watch may not record sleep stages.")
    st.stop()

# Group by night (using the date the sleep started)
actual_sleep["Night"] = actual_sleep["startDate"].dt.date
nightly_total = actual_sleep.groupby("Night")["duration_hours"].sum().reset_index()
nightly_total.columns = ["Night", "TotalSleep_hrs"]
nightly_total["Night"] = pd.to_datetime(nightly_total["Night"])

# Filter out unrealistic values
nightly_total = nightly_total[(nightly_total["TotalSleep_hrs"] > 2) & (nightly_total["TotalSleep_hrs"] < 16)]

# KPIs
col1, col2, col3, col4 = st.columns(4)
with col1:
    avg_sleep = nightly_total["TotalSleep_hrs"].mean()
    st.metric("Average Sleep", f"{avg_sleep:.1f} hrs")
with col2:
    recent_avg = nightly_total.tail(14)["TotalSleep_hrs"].mean()
    st.metric("Recent (14d avg)", f"{recent_avg:.1f} hrs")
with col3:
    st.metric("Best Night", f"{nightly_total['TotalSleep_hrs'].max():.1f} hrs")
with col4:
    consistency = nightly_total["TotalSleep_hrs"].std()
    st.metric("Consistency (std)", f"{consistency:.1f} hrs")

st.markdown("---")

# Sleep duration over time
st.subheader("Sleep Duration Trend")
nightly_total["Rolling_7d"] = nightly_total["TotalSleep_hrs"].rolling(7, min_periods=1).mean()

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=nightly_total["Night"], y=nightly_total["TotalSleep_hrs"],
    mode="markers", name="Nightly", marker=dict(size=4, opacity=0.4)
))
fig.add_trace(go.Scatter(
    x=nightly_total["Night"], y=nightly_total["Rolling_7d"],
    mode="lines", name="7-day Average", line=dict(width=3)
))
fig.add_hline(y=7, line_dash="dash", line_color="green", annotation_text="7hr target")
fig.update_layout(
    title="Nightly Sleep Duration",
    yaxis_title="Hours",
    xaxis_title="Date",
    height=400,
    margin=dict(t=40, b=20),
)
st.plotly_chart(fig, use_container_width=True)

# Sleep stages breakdown
st.subheader("Sleep Stages")
stage_summary = actual_sleep.groupby("value")["duration_hours"].sum().reset_index()
stage_summary.columns = ["Stage", "TotalHours"]

fig = px.pie(
    stage_summary,
    values="TotalHours",
    names="Stage",
    title="Total Time by Sleep Stage",
    color="Stage",
    color_discrete_map={
        "AsleepCore": "#636EFA",
        "AsleepDeep": "#1F3B73",
        "AsleepREM": "#AB63FA",
        "Asleep": "#636EFA",
    },
)
fig.update_layout(height=400, margin=dict(t=40, b=20))
st.plotly_chart(fig, use_container_width=True)

# Day of week patterns
st.subheader("Day of Week Patterns")
nightly_total["DayOfWeek"] = nightly_total["Night"].dt.day_name()
dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
nightly_total["DayOfWeek"] = pd.Categorical(nightly_total["DayOfWeek"], categories=dow_order, ordered=True)

fig = px.box(
    nightly_total.sort_values("DayOfWeek"),
    x="DayOfWeek",
    y="TotalSleep_hrs",
    title="Sleep Duration by Day of Week",
    labels={"TotalSleep_hrs": "Hours", "DayOfWeek": ""},
)
fig.update_layout(height=350, margin=dict(t=40, b=20))
st.plotly_chart(fig, use_container_width=True)

# Bedtime consistency
st.subheader("Bedtime Consistency")
actual_sleep_sorted = actual_sleep.sort_values("startDate")
first_sleep_per_night = actual_sleep_sorted.groupby("Night")["startDate"].min().reset_index()
first_sleep_per_night.columns = ["Night", "Bedtime"]
first_sleep_per_night["Night"] = pd.to_datetime(first_sleep_per_night["Night"])
first_sleep_per_night["BedtimeHour"] = (
    first_sleep_per_night["Bedtime"].dt.hour
    + first_sleep_per_night["Bedtime"].dt.minute / 60
)
# Shift so midnight is 24, 1am is 25, etc. for display
first_sleep_per_night["BedtimeHour"] = first_sleep_per_night["BedtimeHour"].apply(
    lambda x: x + 24 if x < 12 else x
)

fig = px.scatter(
    first_sleep_per_night,
    x="Night",
    y="BedtimeHour",
    title="Bedtime Over Time",
    labels={"BedtimeHour": "Bedtime (Hour)", "Night": "Date"},
    trendline="lowess",
)
fig.update_yaxes(
    tickvals=[20, 21, 22, 23, 24, 25, 26],
    ticktext=["8 PM", "9 PM", "10 PM", "11 PM", "12 AM", "1 AM", "2 AM"],
)
fig.update_layout(height=350, margin=dict(t=40, b=20))
st.plotly_chart(fig, use_container_width=True)

# Sleep vs Resting HR correlation
resting_hr = data["resting_hr"]
if not resting_hr.empty:
    st.subheader("Sleep vs Next-Day Resting HR")
    rhr_daily = resting_hr.copy()
    rhr_daily["Date"] = rhr_daily["startDate"].dt.date
    rhr_daily = rhr_daily.groupby("Date")["value"].mean().reset_index()
    rhr_daily["Date"] = pd.to_datetime(rhr_daily["Date"])

    nightly_with_rhr = nightly_total.copy()
    nightly_with_rhr["NextDay"] = nightly_with_rhr["Night"] + pd.Timedelta(days=1)
    merged = pd.merge(
        nightly_with_rhr, rhr_daily, left_on="NextDay", right_on="Date", how="inner"
    )

    if len(merged) > 10:
        fig = px.scatter(
            merged,
            x="TotalSleep_hrs",
            y="value",
            trendline="ols",
            title="Sleep Duration vs Next-Day Resting HR",
            labels={"TotalSleep_hrs": "Sleep (hours)", "value": "Resting HR (bpm)"},
        )
        fig.update_layout(height=400, margin=dict(t=40, b=20))
        st.plotly_chart(fig, use_container_width=True)
