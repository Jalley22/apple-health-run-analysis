"""Shared chart styling and color palette for the dashboard."""
import plotly.io as pio
import plotly.graph_objects as go

# Athletic color palette
COLORS = {
    "primary": "#FF6B35",      # warm orange — energy
    "secondary": "#00C9A7",    # teal — recovery/health
    "accent": "#6C5CE7",       # purple — highlights
    "success": "#2ECC40",
    "warning": "#FFB800",
    "alert": "#FF4B4B",
    "dark": "#1a1a2e",
    "light": "#FAFAFA",
    "muted": "#636e72",
}

# Chart color sequence (replaces default blue)
CHART_COLORS = [
    "#FF6B35",  # orange
    "#00C9A7",  # teal
    "#6C5CE7",  # purple
    "#FFB800",  # gold
    "#FF4B4B",  # red
    "#0984E3",  # blue (sparingly)
    "#00B894",  # mint
    "#FD79A8",  # pink
]

# Plotly template
_template = go.layout.Template()
_template.layout.colorway = CHART_COLORS
_template.layout.font = dict(family="Inter, -apple-system, sans-serif", color=COLORS["dark"])
_template.layout.paper_bgcolor = "rgba(0,0,0,0)"
_template.layout.plot_bgcolor = "rgba(0,0,0,0)"
_template.layout.xaxis = dict(gridcolor="#E8E8E8", linecolor="#E8E8E8")
_template.layout.yaxis = dict(gridcolor="#E8E8E8", linecolor="#E8E8E8")

pio.templates["athletic"] = _template
pio.templates.default = "athletic"


def card_html(title: str, detail: str, severity: str = "info") -> str:
    """Render a styled insight card with left-border accent."""
    border_colors = {
        "alert": COLORS["alert"],
        "warning": COLORS["warning"],
        "info": COLORS["secondary"],
    }
    icons = {"alert": "🚨", "warning": "⚡", "info": "ℹ️"}
    border = border_colors.get(severity, COLORS["secondary"])
    icon = icons.get(severity, "ℹ️")

    return f"""
    <div style="
        border-left: 4px solid {border};
        background: white;
        padding: 16px 20px;
        margin-bottom: 12px;
        border-radius: 6px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    ">
        <strong style="color: {COLORS['dark']};">{icon} {title}</strong><br>
        <span style="color: {COLORS['muted']}; font-size: 0.92em;">{detail}</span>
    </div>
    """


def metric_card_css() -> str:
    """Inject CSS to style Streamlit metric cards and sidebar."""
    return """
    <style>
        [data-testid="stMetric"] {
            background: white;
            border-radius: 8px;
            padding: 12px 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }
        [data-testid="stMetricLabel"] {
            color: #636e72;
            font-size: 0.85em;
        }
        [data-testid="stMetricValue"] {
            color: #1a1a2e;
            font-weight: 700;
        }
        .stApp > header {
            background-color: transparent;
        }
        section[data-testid="stSidebar"] > div:first-child {
            background: linear-gradient(180deg, #1a1a2e 0%, #2d3436 100%);
            padding-top: 1rem;
        }
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3,
        section[data-testid="stSidebar"] span.st-emotion-cache-1gulkj5,
        section[data-testid="stSidebar"] label p {
            color: #EEEEEE !important;
        }
    </style>
    """
