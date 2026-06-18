"""
Health Insights Engine — auto-generates trend alerts, anomaly detection,
health risk flags, and cross-metric correlations from parsed health data.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class Insight:
    category: str  # "trend", "anomaly", "risk", "correlation"
    severity: str  # "info", "warning", "alert"
    title: str
    detail: str
    metric: str
    date_range: tuple = field(default_factory=tuple)
    value: Optional[float] = None


def generate_all_insights(
    data: dict[str, pd.DataFrame],
    trend_short_days: int = 30,
    trend_long_days: int = 90,
    anomaly_threshold: float = 2.5,
) -> list[Insight]:
    """Run all insight generators and return sorted list."""
    # Normalize all date columns to tz-naive for consistent comparisons
    normalized = {}
    for key, df in data.items():
        if df is None or df.empty:
            normalized[key] = df
            continue
        df = df.copy()
        for col in df.columns:
            if hasattr(df[col].dtype, "tz") and df[col].dtype.tz is not None:
                df[col] = df[col].dt.tz_localize(None)
        normalized[key] = df

    insights = []
    insights.extend(_trend_insights(normalized, trend_short_days, trend_long_days))
    insights.extend(_anomaly_insights(normalized, anomaly_threshold))
    insights.extend(_health_risk_insights(normalized))
    insights.extend(_correlation_insights(normalized))

    # Sort: alerts first, then warnings, then info
    severity_order = {"alert": 0, "warning": 1, "info": 2}
    insights.sort(key=lambda i: (severity_order.get(i.severity, 3), i.category))
    return insights


# =============================================================================
# TREND DETECTION
# =============================================================================

def _trend_insights(
    data: dict[str, pd.DataFrame],
    short_days: int = 30,
    long_days: int = 90,
) -> list[Insight]:
    insights = []
    today = pd.Timestamp.now()

    # --- Resting HR trend (from raw HR daily 5th percentile) ---
    hr = data.get("heart_rate")
    if hr is not None and not hr.empty:
        daily_p5 = hr.groupby(hr["startDate"].dt.date)["value"].quantile(0.05).reset_index()
        daily_p5.columns = ["Date", "RestingHR"]
        daily_p5["Date"] = pd.to_datetime(daily_p5["Date"])

        short_window = daily_p5[daily_p5["Date"] >= (today - pd.Timedelta(days=short_days))]
        long_window = daily_p5[
            (daily_p5["Date"] >= (today - pd.Timedelta(days=long_days)))
            & (daily_p5["Date"] < (today - pd.Timedelta(days=short_days)))
        ]

        if len(short_window) >= 7 and len(long_window) >= 14:
            recent_avg = short_window["RestingHR"].mean()
            baseline_avg = long_window["RestingHR"].mean()
            pct_change = ((recent_avg - baseline_avg) / baseline_avg) * 100

            if abs(pct_change) >= 5:
                direction = "increased" if pct_change > 0 else "decreased"
                severity = "warning" if abs(pct_change) >= 10 else "info"
                if pct_change > 15:
                    severity = "alert"
                insights.append(Insight(
                    category="trend",
                    severity=severity,
                    title=f"Resting HR {direction}",
                    detail=(
                        f"Last {short_days}d avg: {recent_avg:.0f} bpm vs "
                        f"prior {long_days - short_days}d avg: {baseline_avg:.0f} bpm "
                        f"({pct_change:+.1f}%)"
                    ),
                    metric="resting_hr",
                    value=pct_change,
                ))

    # --- Running pace trend ---
    workouts = data.get("workouts")
    if workouts is not None and not workouts.empty:
        running = workouts[workouts["ActivityType"] == "Running"].copy()
        if "DistanceWalkingRunning_sum_mi" in running.columns:
            running = running.dropna(subset=["DistanceWalkingRunning_sum_mi"])
            running = running[running["DistanceWalkingRunning_sum_mi"] > 0.5]
            running["Pace"] = (
                (running["Duration_min"] - running["PausedDuration_min"])
                / running["DistanceWalkingRunning_sum_mi"]
            )
            running = running[(running["Pace"] > 4) & (running["Pace"] < 20)]
            running = running.sort_values("StartDate")

            if len(running) >= 15:
                recent_runs = running.tail(10)
                prior_runs = running.iloc[-40:-10] if len(running) >= 40 else running.iloc[:-10]

                if len(prior_runs) >= 5:
                    recent_pace = recent_runs["Pace"].mean()
                    prior_pace = prior_runs["Pace"].mean()
                    pct_change = ((recent_pace - prior_pace) / prior_pace) * 100

                    if abs(pct_change) >= 5:
                        direction = "slower" if pct_change > 0 else "faster"
                        severity = "warning" if pct_change > 10 else "info"
                        insights.append(Insight(
                            category="trend",
                            severity=severity,
                            title=f"Running pace getting {direction}",
                            detail=(
                                f"Last 10 runs: {recent_pace:.1f} min/mi vs "
                                f"prior avg: {prior_pace:.1f} min/mi ({pct_change:+.1f}%)"
                            ),
                            metric="running_pace",
                            value=pct_change,
                        ))

        # --- Workout frequency trend ---
        recent_4w = workouts[workouts["StartDate"] >= (today - pd.Timedelta(weeks=4))]
        prior_12w = workouts[
            (workouts["StartDate"] >= (today - pd.Timedelta(weeks=16)))
            & (workouts["StartDate"] < (today - pd.Timedelta(weeks=4)))
        ]

        if len(prior_12w) >= 4:
            recent_per_week = len(recent_4w) / 4
            prior_per_week = len(prior_12w) / 12
            pct_change = ((recent_per_week - prior_per_week) / max(prior_per_week, 0.1)) * 100

            if abs(pct_change) >= 25:
                direction = "dropped" if pct_change < 0 else "increased"
                severity = "warning" if pct_change < -40 else "info"
                insights.append(Insight(
                    category="trend",
                    severity=severity,
                    title=f"Workout frequency {direction}",
                    detail=(
                        f"Last 4 weeks: {recent_per_week:.1f}/week vs "
                        f"prior 12 weeks: {prior_per_week:.1f}/week ({pct_change:+.0f}%)"
                    ),
                    metric="workout_frequency",
                    value=pct_change,
                ))

    # --- Sleep duration trend ---
    sleep = data.get("sleep")
    if sleep is not None and not sleep.empty:
        sleep_stages = ["Asleep", "AsleepCore", "AsleepDeep", "AsleepREM"]
        actual_sleep = sleep[sleep["value"].isin(sleep_stages)].copy()
        if not actual_sleep.empty and "duration_hours" in actual_sleep.columns:
            nightly = actual_sleep.groupby(actual_sleep["startDate"].dt.date)["duration_hours"].sum().reset_index()
            nightly.columns = ["Date", "Hours"]
            nightly["Date"] = pd.to_datetime(nightly["Date"])
            nightly = nightly[(nightly["Hours"] > 2) & (nightly["Hours"] < 16)]

            recent_sleep = nightly[nightly["Date"] >= (today - pd.Timedelta(days=14))]
            prior_sleep = nightly[
                (nightly["Date"] >= (today - pd.Timedelta(days=60)))
                & (nightly["Date"] < (today - pd.Timedelta(days=14)))
            ]

            if len(recent_sleep) >= 5 and len(prior_sleep) >= 14:
                recent_avg = recent_sleep["Hours"].mean()
                prior_avg = prior_sleep["Hours"].mean()
                diff = recent_avg - prior_avg

                if abs(diff) >= 0.5:
                    direction = "decreased" if diff < 0 else "increased"
                    severity = "warning" if diff < -1.0 else "info"
                    insights.append(Insight(
                        category="trend",
                        severity=severity,
                        title=f"Sleep duration {direction}",
                        detail=(
                            f"Last 14d avg: {recent_avg:.1f} hrs vs "
                            f"prior 46d avg: {prior_avg:.1f} hrs ({diff:+.1f} hrs)"
                        ),
                        metric="sleep",
                        value=diff,
                    ))

    return insights


# =============================================================================
# ANOMALY DETECTION
# =============================================================================

def _anomaly_insights(
    data: dict[str, pd.DataFrame],
    threshold: float = 2.5,
) -> list[Insight]:
    insights = []
    today = pd.Timestamp.now()
    lookback = today - pd.Timedelta(days=30)

    # --- HR spikes (non-workout) ---
    hr = data.get("heart_rate")
    workouts = data.get("workouts")
    if hr is not None and not hr.empty:
        recent_hr = hr[hr["startDate"] >= lookback].copy()
        if not recent_hr.empty:
            daily_max = recent_hr.groupby(recent_hr["startDate"].dt.date)["value"].max().reset_index()
            daily_max.columns = ["Date", "MaxHR"]

            mean_max = daily_max["MaxHR"].mean()
            std_max = daily_max["MaxHR"].std()

            if std_max > 0:
                anomalies = daily_max[daily_max["MaxHR"] > mean_max + threshold * std_max]
                for _, row in anomalies.iterrows():
                    insights.append(Insight(
                        category="anomaly",
                        severity="warning",
                        title=f"HR spike: {row['MaxHR']:.0f} bpm",
                        detail=(
                            f"On {row['Date']}, max HR reached {row['MaxHR']:.0f} bpm "
                            f"(personal avg daily max: {mean_max:.0f} bpm, "
                            f"threshold: {mean_max + threshold * std_max:.0f} bpm)"
                        ),
                        metric="heart_rate",
                        date_range=(row["Date"], row["Date"]),
                        value=row["MaxHR"],
                    ))

    # --- Unusually short sleep ---
    sleep = data.get("sleep")
    if sleep is not None and not sleep.empty:
        sleep_stages = ["Asleep", "AsleepCore", "AsleepDeep", "AsleepREM"]
        actual_sleep = sleep[sleep["value"].isin(sleep_stages)].copy()
        if not actual_sleep.empty and "duration_hours" in actual_sleep.columns:
            nightly = actual_sleep.groupby(actual_sleep["startDate"].dt.date)["duration_hours"].sum().reset_index()
            nightly.columns = ["Date", "Hours"]
            nightly["Date"] = pd.to_datetime(nightly["Date"])
            nightly = nightly[(nightly["Hours"] > 0.5) & (nightly["Hours"] < 16)]

            mean_sleep = nightly["Hours"].mean()
            std_sleep = nightly["Hours"].std()

            if std_sleep > 0:
                recent_nightly = nightly[nightly["Date"] >= lookback]
                short_nights = recent_nightly[recent_nightly["Hours"] < mean_sleep - threshold * std_sleep]
                for _, row in short_nights.iterrows():
                    insights.append(Insight(
                        category="anomaly",
                        severity="info",
                        title=f"Very short sleep: {row['Hours']:.1f} hrs",
                        detail=(
                            f"On {row['Date'].strftime('%b %d')}, slept only {row['Hours']:.1f} hrs "
                            f"(your avg: {mean_sleep:.1f} hrs)"
                        ),
                        metric="sleep",
                        date_range=(row["Date"], row["Date"]),
                        value=row["Hours"],
                    ))

    # --- Workout HR anomalies (high HR for easy run) ---
    if workouts is not None and not workouts.empty:
        running = workouts[
            (workouts["ActivityType"] == "Running")
            & (workouts["StartDate"] >= lookback)
        ].copy()
        if "HeartRate_average_count/min" in running.columns:
            hr_runs = running.dropna(subset=["HeartRate_average_count/min"])
            if len(hr_runs) >= 5:
                mean_hr = hr_runs["HeartRate_average_count/min"].mean()
                std_hr = hr_runs["HeartRate_average_count/min"].std()
                if std_hr > 0:
                    high_hr_runs = hr_runs[
                        hr_runs["HeartRate_average_count/min"] > mean_hr + threshold * std_hr
                    ]
                    for _, row in high_hr_runs.iterrows():
                        insights.append(Insight(
                            category="anomaly",
                            severity="warning",
                            title=f"Unusually high workout HR: {row['HeartRate_average_count/min']:.0f} bpm",
                            detail=(
                                f"On {row['StartDate'].strftime('%b %d')}, avg HR was "
                                f"{row['HeartRate_average_count/min']:.0f} bpm during a run "
                                f"(your typical: {mean_hr:.0f} bpm)"
                            ),
                            metric="workout_hr",
                            value=row["HeartRate_average_count/min"],
                        ))

    return insights


# =============================================================================
# HEALTH RISK FLAGS
# =============================================================================

def _health_risk_insights(data: dict[str, pd.DataFrame]) -> list[Insight]:
    insights = []
    today = pd.Timestamp.now()

    hr = data.get("heart_rate")
    workouts = data.get("workouts")

    if hr is None or hr.empty:
        return insights

    # Compute daily resting HR (5th percentile)
    daily_p5 = hr.groupby(hr["startDate"].dt.date)["value"].quantile(0.05).reset_index()
    daily_p5.columns = ["Date", "RestingHR"]
    daily_p5["Date"] = pd.to_datetime(daily_p5["Date"])

    if len(daily_p5) < 30:
        return insights

    # --- Sustained elevated resting HR ---
    p90 = daily_p5["RestingHR"].quantile(0.90)
    last_14d = daily_p5.tail(14)
    days_above_p90 = (last_14d["RestingHR"] > p90).sum()

    if days_above_p90 >= 10:
        recent_avg = last_14d["RestingHR"].mean()
        insights.append(Insight(
            category="risk",
            severity="alert",
            title="Sustained elevated resting HR",
            detail=(
                f"Resting HR has been above your 90th percentile ({p90:.0f} bpm) "
                f"for {days_above_p90} of the last 14 days. "
                f"Current avg: {recent_avg:.0f} bpm. "
                f"Consider rest, hydration, or consulting a physician if this persists."
            ),
            metric="resting_hr",
            value=recent_avg,
        ))

    # --- Sudden HR jump (week over week) ---
    last_7d = daily_p5[daily_p5["Date"] >= (today - pd.Timedelta(days=7))]
    prior_7d = daily_p5[
        (daily_p5["Date"] >= (today - pd.Timedelta(days=14)))
        & (daily_p5["Date"] < (today - pd.Timedelta(days=7)))
    ]
    if len(last_7d) >= 5 and len(prior_7d) >= 5:
        this_week = last_7d["RestingHR"].mean()
        last_week = prior_7d["RestingHR"].mean()
        jump = this_week - last_week
        if jump >= 8:
            insights.append(Insight(
                category="risk",
                severity="alert" if jump >= 12 else "warning",
                title=f"Sudden resting HR jump: +{jump:.0f} bpm",
                detail=(
                    f"This week avg: {this_week:.0f} bpm vs last week: {last_week:.0f} bpm. "
                    f"Sudden increases can indicate illness, stress, dehydration, or overtraining."
                ),
                metric="resting_hr",
                value=jump,
            ))

    # --- Declining fitness (pace worsening + HR increasing) ---
    if workouts is not None and not workouts.empty:
        running = workouts[workouts["ActivityType"] == "Running"].copy()
        if "DistanceWalkingRunning_sum_mi" in running.columns and "HeartRate_average_count/min" in running.columns:
            running = running.dropna(subset=["DistanceWalkingRunning_sum_mi", "HeartRate_average_count/min"])
            running = running[running["DistanceWalkingRunning_sum_mi"] > 0.5]
            running["Pace"] = (
                (running["Duration_min"] - running["PausedDuration_min"])
                / running["DistanceWalkingRunning_sum_mi"]
            )
            running = running[(running["Pace"] > 4) & (running["Pace"] < 20)]
            running = running.sort_values("StartDate")

            if len(running) >= 20:
                recent_10 = running.tail(10)
                prior_10 = running.iloc[-20:-10]

                pace_change = recent_10["Pace"].mean() - prior_10["Pace"].mean()
                hr_change = recent_10["HeartRate_average_count/min"].mean() - prior_10["HeartRate_average_count/min"].mean()

                # Pace getting worse AND HR getting higher = fitness decline
                if pace_change > 0.5 and hr_change > 3:
                    insights.append(Insight(
                        category="risk",
                        severity="warning",
                        title="Possible fitness decline",
                        detail=(
                            f"Running pace slowed by {pace_change:.1f} min/mi while avg HR "
                            f"increased by {hr_change:.0f} bpm (last 10 runs vs prior 10). "
                            f"This pattern suggests declining cardiovascular fitness or overtraining."
                        ),
                        metric="fitness",
                        value=pace_change,
                    ))

    return insights


# =============================================================================
# CORRELATION ANALYSIS
# =============================================================================

def _correlation_insights(data: dict[str, pd.DataFrame]) -> list[Insight]:
    insights = []

    hr = data.get("heart_rate")
    workouts = data.get("workouts")
    sleep = data.get("sleep")

    # --- Training load vs resting HR (next week) ---
    if hr is not None and not hr.empty and workouts is not None and not workouts.empty:
        daily_p5 = hr.groupby(hr["startDate"].dt.date)["value"].quantile(0.05).reset_index()
        daily_p5.columns = ["Date", "RestingHR"]
        daily_p5["Date"] = pd.to_datetime(daily_p5["Date"])

        # Weekly aggregation
        daily_p5_idx = daily_p5.set_index("Date")
        weekly_rhr = daily_p5_idx.resample("W")["RestingHR"].mean().reset_index()
        weekly_rhr.columns = ["Week", "AvgRHR"]

        weekly_volume = (
            workouts.set_index("StartDate")
            .resample("W")["Duration_min"]
            .sum()
            .reset_index()
        )
        weekly_volume.columns = ["Week", "TrainingMin"]
        weekly_volume["Week"] = weekly_volume["Week"].dt.tz_localize(None)

        # Shift RHR by 1 week to compare "this week training" → "next week RHR"
        weekly_rhr["Week_shifted"] = weekly_rhr["Week"] - pd.Timedelta(weeks=1)
        merged = pd.merge(
            weekly_volume,
            weekly_rhr[["Week_shifted", "AvgRHR"]].rename(columns={"Week_shifted": "Week"}),
            on="Week",
            how="inner",
        )

        if len(merged) >= 10:
            corr = merged["TrainingMin"].corr(merged["AvgRHR"])
            if abs(corr) >= 0.3:
                direction = "rises" if corr > 0 else "drops"
                # Quantify: compare top vs bottom quartile training weeks
                q75 = merged["TrainingMin"].quantile(0.75)
                q25 = merged["TrainingMin"].quantile(0.25)
                heavy_weeks_rhr = merged[merged["TrainingMin"] >= q75]["AvgRHR"].mean()
                light_weeks_rhr = merged[merged["TrainingMin"] <= q25]["AvgRHR"].mean()
                diff = heavy_weeks_rhr - light_weeks_rhr

                insights.append(Insight(
                    category="correlation",
                    severity="info",
                    title=f"Training load → resting HR {direction}",
                    detail=(
                        f"After heavy training weeks (>{q75:.0f} min), next-week resting HR "
                        f"averages {heavy_weeks_rhr:.0f} bpm vs {light_weeks_rhr:.0f} bpm "
                        f"after light weeks ({diff:+.1f} bpm, r={corr:.2f})"
                    ),
                    metric="training_hr_correlation",
                    value=corr,
                ))

    # --- Sleep vs running performance ---
    if (
        sleep is not None and not sleep.empty
        and workouts is not None and not workouts.empty
        and "DistanceWalkingRunning_sum_mi" in workouts.columns
    ):
        sleep_stages = ["Asleep", "AsleepCore", "AsleepDeep", "AsleepREM"]
        actual_sleep = sleep[sleep["value"].isin(sleep_stages)].copy()
        if not actual_sleep.empty and "duration_hours" in actual_sleep.columns:
            nightly = actual_sleep.groupby(actual_sleep["startDate"].dt.date)["duration_hours"].sum().reset_index()
            nightly.columns = ["Date", "SleepHours"]
            nightly["Date"] = pd.to_datetime(nightly["Date"])
            nightly = nightly[(nightly["SleepHours"] > 2) & (nightly["SleepHours"] < 16)]

            running = workouts[workouts["ActivityType"] == "Running"].copy()
            running = running.dropna(subset=["DistanceWalkingRunning_sum_mi"])
            running = running[running["DistanceWalkingRunning_sum_mi"] > 0.5]
            running["Pace"] = (
                (running["Duration_min"] - running["PausedDuration_min"])
                / running["DistanceWalkingRunning_sum_mi"]
            )
            running = running[(running["Pace"] > 4) & (running["Pace"] < 20)]
            running["RunDate"] = running["StartDate"].dt.date

            # Match: sleep night before → next day's run
            nightly["NextDay"] = nightly["Date"] + pd.Timedelta(days=1)
            nightly["NextDay_date"] = nightly["NextDay"].dt.date

            merged = pd.merge(
                running,
                nightly[["NextDay_date", "SleepHours"]].rename(columns={"NextDay_date": "RunDate"}),
                on="RunDate",
                how="inner",
            )

            if len(merged) >= 10:
                corr = merged["SleepHours"].corr(merged["Pace"])
                if abs(corr) >= 0.2:
                    # Negative correlation = more sleep → lower pace (faster)
                    good_sleep = merged[merged["SleepHours"] >= merged["SleepHours"].quantile(0.75)]
                    poor_sleep = merged[merged["SleepHours"] <= merged["SleepHours"].quantile(0.25)]
                    if len(good_sleep) >= 3 and len(poor_sleep) >= 3:
                        diff = poor_sleep["Pace"].mean() - good_sleep["Pace"].mean()
                        insights.append(Insight(
                            category="correlation",
                            severity="info",
                            title="Sleep affects running pace",
                            detail=(
                                f"After good sleep (>{good_sleep['SleepHours'].min():.1f} hrs), "
                                f"you run {diff:.1f} min/mi faster on average than after "
                                f"poor sleep (<{poor_sleep['SleepHours'].max():.1f} hrs). "
                                f"(r={corr:.2f})"
                            ),
                            metric="sleep_pace_correlation",
                            value=corr,
                        ))

    # --- Day-of-week performance ---
    if workouts is not None and not workouts.empty:
        running = workouts[workouts["ActivityType"] == "Running"].copy()
        if "DistanceWalkingRunning_sum_mi" in running.columns:
            running = running.dropna(subset=["DistanceWalkingRunning_sum_mi"])
            running = running[running["DistanceWalkingRunning_sum_mi"] > 0.5]
            running["Pace"] = (
                (running["Duration_min"] - running["PausedDuration_min"])
                / running["DistanceWalkingRunning_sum_mi"]
            )
            running = running[(running["Pace"] > 4) & (running["Pace"] < 20)]
            running["DayOfWeek"] = running["StartDate"].dt.day_name()

            if len(running) >= 20:
                dow_pace = running.groupby("DayOfWeek")["Pace"].mean()
                if len(dow_pace) >= 3:
                    best_day = dow_pace.idxmin()
                    worst_day = dow_pace.idxmax()
                    spread = dow_pace.max() - dow_pace.min()
                    if spread >= 0.3:
                        insights.append(Insight(
                            category="correlation",
                            severity="info",
                            title=f"Best run day: {best_day}",
                            detail=(
                                f"You run fastest on {best_day}s ({dow_pace[best_day]:.1f} min/mi) "
                                f"and slowest on {worst_day}s ({dow_pace[worst_day]:.1f} min/mi). "
                                f"Spread: {spread:.1f} min/mi."
                            ),
                            metric="day_of_week",
                            value=spread,
                        ))

    return insights
