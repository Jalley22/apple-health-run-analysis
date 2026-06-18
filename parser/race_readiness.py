"""Race readiness scoring engine — adapts to any race goal from user profile."""
import pandas as pd
import numpy as np
from datetime import date, timedelta
from .config import get_race_config, get_age


def compute_readiness(data: dict[str, pd.DataFrame]) -> dict:
    """
    Compute race readiness score and component metrics.
    Adapts to the user's configured race goal.
    """
    race_config = get_race_config()
    today = date.today()
    race_date = race_config["race_date"]
    distances = race_config["distances"]
    weeks_remaining = max(0, (race_date - today).days // 7)

    workouts = data.get("workouts", pd.DataFrame())
    hr_data = data.get("heart_rate", pd.DataFrame())

    target_run = distances.get("run_mi", 0)
    target_bike = distances.get("bike_mi", 0)
    target_swim = distances.get("swim_mi", 0)

    result = {
        "weeks_remaining": weeks_remaining,
        "race_date": race_date,
        "race_type": race_config["race_type"],
        "target_run_miles": target_run,
        "target_bike_miles": target_bike,
        "target_swim_miles": target_swim,
        "scores": {},
        "metrics": {},
        "gaps": [],
        "projected_finish": None,
    }

    if workouts.empty:
        result["total_score"] = 0
        return result

    # Normalize timestamps
    wk = workouts.copy()
    if hasattr(wk["StartDate"].dtype, "tz") and wk["StartDate"].dtype.tz:
        wk["StartDate"] = wk["StartDate"].dt.tz_localize(None)

    now = pd.Timestamp.now()

    # =========================================================================
    # RUNNING ANALYSIS
    # =========================================================================
    running = wk[wk["ActivityType"] == "Running"].copy()
    run_score = 0
    run_metrics = {}

    if "DistanceWalkingRunning_sum_mi" in running.columns:
        running = running.dropna(subset=["DistanceWalkingRunning_sum_mi"])
        running = running[running["DistanceWalkingRunning_sum_mi"] > 0.5]
        running["Pace"] = (
            (running["Duration_min"] - running["PausedDuration_min"])
            / running["DistanceWalkingRunning_sum_mi"]
        )
        running = running[(running["Pace"] > 4) & (running["Pace"] < 20)]

        if not running.empty:
            # Weekly mileage (last 4 weeks)
            recent_4w = running[running["StartDate"] >= (now - pd.Timedelta(weeks=4))]
            weekly_miles = recent_4w["DistanceWalkingRunning_sum_mi"].sum() / 4
            run_metrics["weekly_miles"] = weekly_miles

            # Longest run (last 4 weeks)
            longest_run = recent_4w["DistanceWalkingRunning_sum_mi"].max() if not recent_4w.empty else 0
            run_metrics["longest_run"] = longest_run

            # Average pace (last 10 runs)
            recent_pace = running.sort_values("StartDate").tail(10)["Pace"].mean()
            run_metrics["avg_pace"] = recent_pace

            # Projected half marathon time
            projected_hm_time = recent_pace * target_run
            run_metrics["projected_hm_mins"] = projected_hm_time

            # Running volume score (0-100)
            # Target weekly miles = ~2x race distance (standard training guidance)
            target_weekly_run = max(10, target_run * 2) if target_run > 0 else 15
            volume_pct = min(100, (weekly_miles / target_weekly_run) * 100)

            # Long run score (0-100)
            # Target: 75% of race distance
            target_long_run = max(5, target_run * 0.75) if target_run > 0 else 5
            long_run_pct = min(100, (longest_run / target_long_run) * 100)

            run_score = (volume_pct * 0.5 + long_run_pct * 0.5)

    result["scores"]["running"] = run_score
    result["metrics"]["running"] = run_metrics

    # =========================================================================
    # CYCLING ANALYSIS
    # =========================================================================
    cycling = wk[wk["ActivityType"] == "Cycling"].copy()
    bike_score = 0
    bike_metrics = {}

    if "DistanceCycling_sum_mi" in cycling.columns:
        cycling = cycling.dropna(subset=["DistanceCycling_sum_mi"])
        if not cycling.empty:
            recent_4w = cycling[cycling["StartDate"] >= (now - pd.Timedelta(weeks=4))]
            weekly_bike_miles = recent_4w["DistanceCycling_sum_mi"].sum() / 4 if not recent_4w.empty else 0
            longest_ride = recent_4w["DistanceCycling_sum_mi"].max() if not recent_4w.empty else 0

            bike_metrics["weekly_miles"] = weekly_bike_miles
            bike_metrics["longest_ride"] = longest_ride

            target_weekly_bike = max(20, target_bike * 0.9) if target_bike > 0 else 20
            target_long_ride = max(15, target_bike * 0.7) if target_bike > 0 else 15
            volume_pct = min(100, (weekly_bike_miles / target_weekly_bike) * 100)
            long_ride_pct = min(100, (longest_ride / target_long_ride) * 100)
            bike_score = (volume_pct * 0.5 + long_ride_pct * 0.5)

    result["scores"]["cycling"] = bike_score
    result["metrics"]["cycling"] = bike_metrics

    # =========================================================================
    # SWIMMING ANALYSIS
    # =========================================================================
    swimming = wk[wk["ActivityType"] == "Swimming"].copy()
    swim_score = 0
    swim_metrics = {}

    if "DistanceSwimming_sum_yd" in swimming.columns:
        swimming = swimming.dropna(subset=["DistanceSwimming_sum_yd"])
        if not swimming.empty:
            recent_4w = swimming[swimming["StartDate"] >= (now - pd.Timedelta(weeks=4))]
            weekly_yards = recent_4w["DistanceSwimming_sum_yd"].sum() / 4 if not recent_4w.empty else 0
            longest_swim = recent_4w["DistanceSwimming_sum_yd"].max() if not recent_4w.empty else 0

            swim_metrics["weekly_yards"] = weekly_yards
            swim_metrics["longest_swim"] = longest_swim

            target_weekly_swim = max(2000, target_swim * 1760 * 1.5) if target_swim > 0 else 2000
            target_long_swim = max(1000, target_swim * 1760) if target_swim > 0 else 1000
            volume_pct = min(100, (weekly_yards / target_weekly_swim) * 100)
            long_swim_pct = min(100, (longest_swim / target_long_swim) * 100)
            swim_score = (volume_pct * 0.5 + long_swim_pct * 0.5)

    result["scores"]["swimming"] = swim_score
    result["metrics"]["swimming"] = swim_metrics

    # =========================================================================
    # CONSISTENCY SCORE
    # =========================================================================
    recent_12w = wk[wk["StartDate"] >= (now - pd.Timedelta(weeks=12))]
    if not recent_12w.empty:
        weekly_counts = recent_12w.groupby(recent_12w["StartDate"].dt.isocalendar().week).size()
        avg_per_week = weekly_counts.mean()
        zero_weeks = 12 - len(weekly_counts)
        consistency = min(100, (avg_per_week / 5) * 100) * (1 - zero_weeks / 12)
    else:
        consistency = 0

    result["scores"]["consistency"] = consistency

    # =========================================================================
    # HR EFFICIENCY (cardiac drift — pace per bpm)
    # =========================================================================
    hr_efficiency_score = 50  # neutral default
    if not running.empty and "HeartRate_average_count/min" in running.columns:
        hr_runs = running.dropna(subset=["HeartRate_average_count/min"])
        if len(hr_runs) >= 10:
            recent_10 = hr_runs.sort_values("StartDate").tail(10)
            prior_10 = hr_runs.sort_values("StartDate").iloc[-20:-10] if len(hr_runs) >= 20 else hr_runs.iloc[:len(hr_runs)//2]

            if len(prior_10) >= 5:
                # Efficiency = pace / HR (lower is better)
                recent_eff = (recent_10["Pace"].mean() / recent_10["HeartRate_average_count/min"].mean())
                prior_eff = (prior_10["Pace"].mean() / prior_10["HeartRate_average_count/min"].mean())

                if prior_eff > 0:
                    improvement = ((prior_eff - recent_eff) / prior_eff) * 100
                    hr_efficiency_score = min(100, max(0, 50 + improvement * 5))

    result["scores"]["hr_efficiency"] = hr_efficiency_score

    # =========================================================================
    # OVERALL SCORE (weights adapt to race type)
    # =========================================================================
    has_swim = target_swim > 0
    has_bike = target_bike > 0
    has_run = target_run > 0

    if has_swim and has_bike and has_run:
        # Triathlon
        weights = {"running": 0.35, "cycling": 0.20, "swimming": 0.15, "consistency": 0.20, "hr_efficiency": 0.10}
    elif has_bike and has_run:
        # Duathlon
        weights = {"running": 0.35, "cycling": 0.30, "swimming": 0.0, "consistency": 0.25, "hr_efficiency": 0.10}
    elif has_run and not has_bike:
        # Running race
        weights = {"running": 0.50, "cycling": 0.0, "swimming": 0.0, "consistency": 0.35, "hr_efficiency": 0.15}
    else:
        # General fitness
        weights = {"running": 0.30, "cycling": 0.15, "swimming": 0.10, "consistency": 0.35, "hr_efficiency": 0.10}

    total = sum(result["scores"].get(k, 50) * w for k, w in weights.items())
    result["total_score"] = round(total, 1)
    result["weights"] = weights

    # =========================================================================
    # GAP ANALYSIS
    # =========================================================================
    gaps = []
    target_weekly_run = max(10, target_run * 2) if target_run > 0 else 15

    rm = result["metrics"].get("running", {})
    if target_run > 0:
        current_miles = rm.get("weekly_miles", 0)
        if current_miles < target_weekly_run * 0.6:
            deficit = target_weekly_run - current_miles
            ramp_per_week = deficit / max(weeks_remaining, 1)
            gaps.append({
                "discipline": "Run",
                "status": "red" if current_miles < target_weekly_run * 0.3 else "yellow",
                "message": f"Need {target_weekly_run:.0f} mi/week. Currently at {current_miles:.1f}. Ramp +{ramp_per_week:.1f} mi/week.",
            })
        elif current_miles < target_weekly_run:
            gaps.append({
                "discipline": "Run",
                "status": "yellow",
                "message": f"At {current_miles:.1f} mi/week — approaching target of {target_weekly_run:.0f}+.",
            })
        else:
            gaps.append({
                "discipline": "Run",
                "status": "green",
                "message": f"Running volume on track at {current_miles:.1f} mi/week.",
            })

    target_weekly_bike = max(20, target_bike * 0.9) if target_bike > 0 else 0
    bm = result["metrics"].get("cycling", {})
    if target_bike > 0:
        current_bike = bm.get("weekly_miles", 0)
        if current_bike < target_weekly_bike * 0.6:
            gaps.append({
                "discipline": "Bike",
                "status": "red" if current_bike < target_weekly_bike * 0.2 else "yellow",
                "message": f"Need {target_weekly_bike:.0f}+ mi/week on bike. Currently {current_bike:.1f}.",
            })
        else:
            gaps.append({
                "discipline": "Bike",
                "status": "green" if current_bike >= target_weekly_bike else "yellow",
                "message": f"Bike volume: {current_bike:.1f} mi/week (target: {target_weekly_bike:.0f}).",
            })

    target_weekly_swim = max(2000, target_swim * 1760 * 1.5) if target_swim > 0 else 0
    sm = result["metrics"].get("swimming", {})
    if target_swim > 0:
        current_swim = sm.get("weekly_yards", 0)
        if current_swim < target_weekly_swim * 0.6:
            gaps.append({
                "discipline": "Swim",
                "status": "red" if current_swim < target_weekly_swim * 0.2 else "yellow",
                "message": f"Need {target_weekly_swim:.0f}+ yd/week. Currently {current_swim:.0f}.",
            })
        else:
            gaps.append({
                "discipline": "Swim",
                "status": "green" if current_swim >= target_weekly_swim else "yellow",
                "message": f"Swim volume: {current_swim:.0f} yd/week (target: {target_weekly_swim:.0f}).",
            })

    result["gaps"] = gaps

    # =========================================================================
    # PROJECTED FINISH TIME
    # =========================================================================
    if rm.get("avg_pace") and target_run > 0:
        projected = {"run_mins": rm["avg_pace"] * target_run * 1.1}  # 10% fatigue factor

        if target_swim > 0:
            projected["swim_mins"] = (target_swim * 1760 / 100) * 2.0  # 2:00/100yd
        else:
            projected["swim_mins"] = 0

        if target_bike > 0:
            bike_mph = 16
            projected["bike_mins"] = (target_bike / bike_mph) * 60
        else:
            projected["bike_mins"] = 0

        projected["transitions_mins"] = 8 if (target_swim > 0 or target_bike > 0) else 0
        projected["total_mins"] = (
            projected["swim_mins"] + projected["bike_mins"]
            + projected["run_mins"] + projected["transitions_mins"]
        )
        result["projected_finish"] = projected

    return result
