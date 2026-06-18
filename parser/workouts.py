import pandas as pd
from datetime import datetime
from lxml import etree


def _time_diff_minutes(start: str, end: str) -> float:
    fmt = "%Y-%m-%d %H:%M:%S %z"
    t0 = datetime.strptime(start, fmt)
    t1 = datetime.strptime(end, fmt)
    return (t1 - t0).total_seconds() / 60


def parse_workouts(xml_path: str, progress_callback=None) -> pd.DataFrame:
    """Parse all Workout elements from export.xml into a DataFrame."""
    workouts = []
    context = etree.iterparse(xml_path, events=("end",), tag="Workout")

    for i, (_, workout) in enumerate(context):
        data = {
            "ActivityType": workout.get("workoutActivityType", "").replace(
                "HKWorkoutActivityType", ""
            ),
            "Duration_min": float(workout.get("duration", 0)),
            "Source": workout.get("sourceName", ""),
            "SourceVersion": workout.get("sourceVersion", ""),
            "StartDate": workout.get("startDate", ""),
            "EndDate": workout.get("endDate", ""),
        }

        # Metadata
        for meta in workout.findall("MetadataEntry"):
            key = meta.get("key", "")
            val = meta.get("value", "")
            if key == "HKAverageMETs":
                try:
                    data["AverageMETs"] = float(val.split(" ")[0])
                except (ValueError, IndexError):
                    pass
            elif key == "HKIndoorWorkout":
                data["IndoorWorkout"] = int(val) if val.isdigit() else 0

        # WorkoutStatistics
        for stat in workout.findall("WorkoutStatistics"):
            stat_type = stat.get("type", "").replace("HKQuantityTypeIdentifier", "")
            unit = stat.get("unit", "")
            for attr in ("sum", "average", "minimum", "maximum"):
                val = stat.get(attr)
                if val:
                    col = f"{stat_type}_{attr}_{unit}"
                    try:
                        data[col] = float(val)
                    except ValueError:
                        pass

        # Paused duration from WorkoutEvents
        paused = 0.0
        motion_paused_at = None
        pause_at = None

        for event in workout.findall("WorkoutEvent"):
            etype = event.get("type", "")
            edate = event.get("date", "")

            if etype == "HKWorkoutEventTypeMotionPaused":
                motion_paused_at = edate
            elif etype == "HKWorkoutEventTypeMotionResumed" and motion_paused_at:
                try:
                    paused += _time_diff_minutes(motion_paused_at, edate)
                except (ValueError, TypeError):
                    pass
                motion_paused_at = None
            elif etype == "HKWorkoutEventTypePause":
                pause_at = edate
            elif etype == "HKWorkoutEventTypeResume" and pause_at:
                try:
                    paused += _time_diff_minutes(pause_at, edate)
                except (ValueError, TypeError):
                    pass
                pause_at = None

        data["PausedDuration_min"] = round(paused, 2)
        workouts.append(data)

        # Free memory
        workout.clear()
        while workout.getprevious() is not None:
            del workout.getparent()[0]

        if progress_callback and i % 50 == 0:
            progress_callback(i)

    df = pd.DataFrame(workouts)

    # Convert dates
    if not df.empty:
        df["StartDate"] = pd.to_datetime(df["StartDate"], format="%Y-%m-%d %H:%M:%S %z", utc=True)
        df["EndDate"] = pd.to_datetime(df["EndDate"], format="%Y-%m-%d %H:%M:%S %z", utc=True)

    return df
