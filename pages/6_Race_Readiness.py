import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
from datetime import date
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from parser.cache import load_or_parse
from parser.race_readiness import compute_readiness
from parser.config import get_race_config
from parser.theme import metric_card_css, COLORS

st.set_page_config(page_title="Race Readiness", page_icon="🏁", layout="wide")
st.markdown(metric_card_css(), unsafe_allow_html=True)
BASE_DIR = str(Path(__file__).parent.parent)


@st.cache_data(show_spinner=False)
def load_data():
    return load_or_parse(BASE_DIR)


data = load_data()
readiness = compute_readiness(data)
race_config = get_race_config()

st.title(f"{race_config['race_type']} Readiness")
st.markdown(f"**Target:** {readiness['race_date'].strftime('%B %d, %Y')} | **Weeks remaining:** {readiness['weeks_remaining']}")
st.markdown("---")

# Overall Readiness Score
col1, col2 = st.columns([1, 2])

with col1:
    score = readiness["total_score"]
    color = "#2ECC40" if score >= 70 else "#FFDC00" if score >= 40 else "#FF4136"

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        title={"text": "Overall Readiness"},
        number={"suffix": "/100"},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": color},
            "steps": [
                {"range": [0, 40], "color": "#FFE5E5"},
                {"range": [40, 70], "color": "#FFF8E0"},
                {"range": [70, 100], "color": "#E5FFE5"},
            ],
        },
    ))
    fig.update_layout(height=300, margin=dict(t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)

    if score >= 70:
        st.success("You're on track for race day!")
    elif score >= 40:
        st.warning("Making progress — gaps to close before October.")
    else:
        st.error("Significant training ramp needed. Prioritize consistency.")

with col2:
    # Component scores
    st.subheader("Component Scores")
    scores = readiness["scores"]

    components = [
        ("Running (35%)", scores.get("running", 0)),
        ("Cycling (20%)", scores.get("cycling", 0)),
        ("Swimming (15%)", scores.get("swimming", 0)),
        ("Consistency (20%)", scores.get("consistency", 0)),
        ("HR Efficiency (10%)", scores.get("hr_efficiency", 50)),
    ]

    for name, val in components:
        color = "#2ECC40" if val >= 70 else "#FFDC00" if val >= 40 else "#FF4136"
        st.markdown(
            f"**{name}:** "
            f"<span style='color: {color}; font-weight: bold;'>{val:.0f}/100</span>",
            unsafe_allow_html=True,
        )
        st.progress(min(100, int(val)) / 100)

st.markdown("---")

# Gap Analysis
st.subheader("Training Gap Analysis")

cols = st.columns(3)
status_emoji = {"green": "✅", "yellow": "⚠️", "red": "🔴"}

for i, gap in enumerate(readiness["gaps"]):
    with cols[i % 3]:
        emoji = status_emoji.get(gap["status"], "❓")
        st.markdown(f"### {emoji} {gap['discipline']}")
        st.markdown(gap["message"])

st.markdown("---")

# Current Metrics
st.subheader("Current Training Metrics")
col1, col2, col3 = st.columns(3)

run_metrics = readiness["metrics"].get("running", {})
bike_metrics = readiness["metrics"].get("cycling", {})
swim_metrics = readiness["metrics"].get("swimming", {})

with col1:
    st.markdown("**Running**")
    if run_metrics:
        st.metric("Weekly Miles", f"{run_metrics.get('weekly_miles', 0):.1f}", delta=f"target: 25+")
        st.metric("Longest Run", f"{run_metrics.get('longest_run', 0):.1f} mi", delta=f"target: 10+")
        st.metric("Avg Pace", f"{run_metrics.get('avg_pace', 0):.1f} min/mi")
    else:
        st.info("No recent running data")

with col2:
    st.markdown("**Cycling**")
    if bike_metrics:
        st.metric("Weekly Miles", f"{bike_metrics.get('weekly_miles', 0):.1f}", delta=f"target: 50+")
        st.metric("Longest Ride", f"{bike_metrics.get('longest_ride', 0):.1f} mi", delta=f"target: 40+")
    else:
        st.info("No recent cycling data")

with col3:
    st.markdown("**Swimming**")
    if swim_metrics:
        st.metric("Weekly Yards", f"{swim_metrics.get('weekly_yards', 0):.0f}", delta=f"target: 3000+")
        st.metric("Longest Swim", f"{swim_metrics.get('longest_swim', 0):.0f} yd", delta=f"target: 2000+")
    else:
        st.info("No recent swimming data")

st.markdown("---")

# Projected Finish Time
st.subheader("Projected Finish Time")

projected = readiness.get("projected_finish")
if projected:
    total_mins = projected["total_mins"]
    hours = int(total_mins // 60)
    mins = int(total_mins % 60)

    st.markdown(f"### Estimated finish: **{hours}h {mins:02d}m**")

    cols = []
    labels = []
    if projected.get("swim_mins", 0) > 0:
        cols.append(("swim_mins", f"Swim ({readiness['target_swim_miles']:.1f} mi)"))
    if projected.get("bike_mins", 0) > 0:
        cols.append(("bike_mins", f"Bike ({readiness['target_bike_miles']:.0f} mi)"))
    if projected.get("run_mins", 0) > 0:
        cols.append(("run_mins", f"Run ({readiness['target_run_miles']:.1f} mi)"))
    if projected.get("transitions_mins", 0) > 0:
        cols.append(("transitions_mins", "Transitions"))

    st_cols = st.columns(len(cols))
    for i, (key, label) in enumerate(cols):
        with st_cols[i]:
            val = projected[key]
            h = int(val // 60)
            m = int(val % 60)
            st.metric(label, f"{h}h {m:02d}m" if h > 0 else f"{m}m")

    st.caption(
        "Projections based on current pace + conservative estimates. "
        "Run includes 10% fatigue factor."
        + (" Bike assumes 16 mph avg." if projected.get("bike_mins", 0) > 0 else "")
        + (" Swim assumes 2:00/100yd." if projected.get("swim_mins", 0) > 0 else "")
    )

    # Contextual finish time feedback
    if race_config["race_type"] in ("Half Ironman (70.3)", "Full Ironman (140.6)", "Olympic Triathlon", "Sprint Triathlon"):
        cutoff_mins = 8 * 60 + 30 if "Half" in race_config["race_type"] else 17 * 60
        if total_mins > cutoff_mins:
            st.warning(f"Projected time may exceed typical race cutoff. Focus on building volume.")
        else:
            st.success("Projected finish is within race cutoff.")
    else:
        # Running races — give goal-based feedback
        if total_mins < 60:
            st.success(f"Projected sub-{int(total_mins)}min — strong!")
        else:
            st.info(f"Projected {hours}h {mins:02d}m finish. Consistent training will bring this down.")
else:
    st.info("Need running data to project finish time.")

# Training Plan Recommendations
st.markdown("---")
st.subheader("Recommendations")

target_run = readiness["target_run_miles"]
target_bike = readiness["target_bike_miles"]
target_swim = readiness["target_swim_miles"]
target_weekly_run = max(10, target_run * 2) if target_run > 0 else 0
target_long_run = max(5, target_run * 0.75) if target_run > 0 else 0

weeks = readiness["weeks_remaining"]
if weeks > 0:
    recommendations = []

    if target_run > 0:
        current_miles = run_metrics.get("weekly_miles", 0)
        if current_miles < target_weekly_run:
            ramp = (target_weekly_run - current_miles) / weeks
            recommendations.append(f"**Run:** Increase weekly mileage by ~{ramp:.1f} mi/week until reaching {target_weekly_run:.0f}+ mi/week.")

        if run_metrics.get("longest_run", 0) < target_long_run:
            recommendations.append(f"**Long run:** Build to {target_long_run:.0f}+ miles. Current longest: {run_metrics.get('longest_run', 0):.1f} mi.")

    if target_bike > 0 and bike_metrics.get("weekly_miles", 0) < target_bike * 0.6:
        recommendations.append(f"**Bike:** Add 2-3 bike sessions per week. Target one long ride building toward {target_bike * 0.7:.0f} mi.")

    if target_swim > 0 and swim_metrics.get("weekly_yards", 0) < target_swim * 1760:
        recommendations.append(f"**Swim:** Build to {target_swim * 1760 * 1.5:.0f} yd/week. Start with 2-3 pool sessions.")

    if scores.get("consistency", 0) < 60:
        recommendations.append("**Consistency:** Aim for 5+ workouts per week with no zero-activity weeks.")

    if not recommendations:
        if target_bike > 0 or target_swim > 0:
            recommendations.append("Training is on track! Add race-specific brick workouts (bike→run).")
        else:
            recommendations.append("Training is on track! Maintain volume and add a tempo run each week.")

    for rec in recommendations:
        st.markdown(f"- {rec}")
else:
    st.markdown("Race is here! Focus on taper, nutrition, and rest.")
