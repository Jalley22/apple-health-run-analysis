import streamlit as st
import pandas as pd
from pathlib import Path
import sys
import os

sys.path.insert(0, str(Path(__file__).parent.parent))
from parser.config import load_profile, save_profile, RACE_PRESETS, profile_exists
from parser.theme import metric_card_css, COLORS

st.set_page_config(page_title="Settings", page_icon="⚙️", layout="wide")
st.markdown(metric_card_css(), unsafe_allow_html=True)

st.title("Settings")
st.markdown("Configure your profile, location, and training goals.")
st.markdown("---")

profile = load_profile()

# --- Profile section ---
st.subheader("Profile")
col1, col2, col3 = st.columns(3)
with col1:
    name = st.text_input("Name", value=profile.get("name", ""))
with col2:
    birth_year = st.number_input("Birth Year", min_value=1940, max_value=2010, value=profile.get("birth_year", 1982))
with col3:
    sex = st.selectbox("Sex", ["Male", "Female"], index=0 if profile.get("sex", "Male") == "Male" else 1)

# --- Location section ---
st.subheader("Location")
st.caption("Used for weather-adjusted performance analysis")
col1, col2, col3 = st.columns(3)
with col1:
    city = st.text_input("City", value=profile.get("city", "Dallas, TX"))
with col2:
    lat = st.number_input("Latitude", value=profile.get("lat", 32.7767), format="%.4f")
with col3:
    lon = st.number_input("Longitude", value=profile.get("lon", -96.7970), format="%.4f")

# --- Training Goal section (outside form for reactivity) ---
st.subheader("Training Goal")

race_types = list(RACE_PRESETS.keys())
current_race = profile.get("race_type", "Half Ironman (70.3)")
race_idx = race_types.index(current_race) if current_race in race_types else 0
race_type = st.selectbox("Goal Race", race_types, index=race_idx)

race_date = st.date_input(
    "Target Date",
    value=pd.Timestamp(profile.get("race_date", "2026-10-01")).date(),
)

# Show distances based on selection
custom_swim = custom_bike = custom_run = 0.0
preset = RACE_PRESETS[race_type]

if race_type == "Custom":
    st.markdown("**Set your custom distances:**")
    col1, col2, col3 = st.columns(3)
    with col1:
        custom_swim = st.number_input("Swim (miles)", value=float(profile.get("custom_swim_mi", 0)), min_value=0.0, step=0.1)
    with col2:
        custom_bike = st.number_input("Bike (miles)", value=float(profile.get("custom_bike_mi", 0)), min_value=0.0, step=1.0)
    with col3:
        custom_run = st.number_input("Run (miles)", value=float(profile.get("custom_run_mi", 0)), min_value=0.0, step=0.5)
elif race_type != "General Fitness":
    cols = st.columns(3)
    with cols[0]:
        if preset["swim_mi"] > 0:
            st.metric("Swim", f"{preset['swim_mi']} mi")
    with cols[1]:
        if preset["bike_mi"] > 0:
            st.metric("Bike", f"{preset['bike_mi']} mi")
    with cols[2]:
        if preset["run_mi"] > 0:
            st.metric("Run", f"{preset['run_mi']} mi")

# --- Save button ---
st.markdown("---")
if st.button("Save Settings", type="primary"):
    updated = {
        "name": name,
        "birth_year": birth_year,
        "sex": sex,
        "city": city,
        "lat": lat,
        "lon": lon,
        "race_type": race_type,
        "race_date": race_date.isoformat(),
        "custom_swim_mi": custom_swim if race_type == "Custom" else 0,
        "custom_bike_mi": custom_bike if race_type == "Custom" else 0,
        "custom_run_mi": custom_run if race_type == "Custom" else 0,
    }
    save_profile(updated)
    st.success("Settings saved!")

# Reset option
st.markdown("---")
st.subheader("Danger Zone")
if st.button("Reset Profile", type="secondary"):
    profile_path = Path(__file__).parent.parent / "user_profile.json"
    if profile_path.exists():
        os.remove(profile_path)
        st.success("Profile reset. Refresh to run onboarding again.")
        st.rerun()
