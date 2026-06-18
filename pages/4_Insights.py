import streamlit as st
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from parser.cache import load_or_parse
from parser.insights import generate_all_insights, Insight
from parser.theme import metric_card_css, card_html, COLORS

st.set_page_config(page_title="Insights", page_icon="🔍", layout="wide")
st.markdown(metric_card_css(), unsafe_allow_html=True)
BASE_DIR = str(Path(__file__).parent.parent)


@st.cache_data(show_spinner=False)
def load_data():
    return load_or_parse(BASE_DIR)


@st.cache_data(show_spinner=False)
def get_insights(_data, short_days, long_days, anomaly_thresh):
    return generate_all_insights(_data, short_days, long_days, anomaly_thresh)


data = load_data()

# Sidebar controls
st.sidebar.title("Insight Settings")
trend_short = st.sidebar.slider("Recent window (days)", 7, 60, 30)
trend_long = st.sidebar.slider("Baseline window (days)", 30, 180, 90)
anomaly_sensitivity = st.sidebar.select_slider(
    "Anomaly sensitivity",
    options=[2.0, 2.5, 3.0],
    value=2.5,
    help="Lower = more sensitive (more anomalies flagged)",
)

insights = get_insights(data, trend_short, trend_long, anomaly_sensitivity)

st.title("Health Insights")
st.markdown("Auto-generated analysis of your health data")
st.markdown("---")

if not insights:
    st.success("No notable insights detected. Your metrics look stable.")
    st.stop()


def render_card(insight: Insight):
    """Render a single insight as a styled card."""
    st.markdown(card_html(insight.title, insight.detail, insight.severity), unsafe_allow_html=True)


# Group and display by category
alerts = [i for i in insights if i.severity == "alert"]
warnings = [i for i in insights if i.severity == "warning"]
info = [i for i in insights if i.severity == "info"]

# Alerts section
if alerts:
    st.subheader(f"🚨 Alerts ({len(alerts)})")
    for insight in alerts:
        render_card(insight)
    st.markdown("---")

# Warnings section
if warnings:
    st.subheader(f"⚡ Warnings ({len(warnings)})")
    for insight in warnings:
        render_card(insight)
    st.markdown("---")

# Trends
trends = [i for i in insights if i.category == "trend" and i.severity == "info"]
if trends:
    st.subheader("📈 Trends")
    for insight in trends:
        render_card(insight)
    st.markdown("---")

# Correlations
correlations = [i for i in insights if i.category == "correlation"]
if correlations:
    st.subheader("📊 Correlations")
    for insight in correlations:
        render_card(insight)
    st.markdown("---")

# Anomalies (expandable)
anomalies = [i for i in insights if i.category == "anomaly" and i.severity == "info"]
if anomalies:
    with st.expander(f"🔎 Anomalies ({len(anomalies)} detected in last 30 days)"):
        for insight in anomalies:
            render_card(insight)

# Summary stats
st.markdown("---")
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Alerts", len(alerts))
with col2:
    st.metric("Warnings", len(warnings))
with col3:
    st.metric("Trends", len([i for i in insights if i.category == "trend"]))
with col4:
    st.metric("Correlations", len(correlations))
