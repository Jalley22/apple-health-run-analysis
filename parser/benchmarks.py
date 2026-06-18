"""Age-group health benchmarks for males based on published norms."""
from .config import get_age


# Benchmarks for males by age decade midpoint
# Sources: AHA, Cooper Institute, Tanaka formula, running community data
MALE_BENCHMARKS = {
    "resting_hr": {
        # bpm thresholds: (excellent_upper, good_upper, avg_upper)
        "30-34": (58, 64, 70),
        "35-39": (59, 65, 71),
        "40-44": (60, 66, 72),
        "45-49": (61, 67, 73),
        "50-54": (62, 68, 74),
    },
    "max_hr": {
        # Tanaka formula: 208 - 0.7 * age
        "formula": lambda age: 208 - 0.7 * age,
    },
    "hrv_sdnn": {
        # ms thresholds: (excellent_lower, good_lower, avg_lower)
        "30-34": (55, 40, 25),
        "35-39": (50, 35, 22),
        "40-44": (45, 30, 20),
        "45-49": (40, 28, 18),
        "50-54": (35, 25, 15),
    },
    "running_pace_5k": {
        # min/mile: (excellent_upper, good_upper, avg_upper)
        "30-34": (6.5, 7.5, 9.0),
        "35-39": (6.8, 8.0, 9.5),
        "40-44": (7.0, 8.5, 10.0),
        "45-49": (7.5, 9.0, 10.5),
        "50-54": (8.0, 9.5, 11.0),
    },
    "weekly_exercise_mins": {
        # minutes: (excellent_lower, good_lower, avg_lower)
        "all": (300, 150, 75),
    },
}


def get_age_group_key() -> str:
    age = get_age()
    brackets = [(30, 34), (35, 39), (40, 44), (45, 49), (50, 54)]
    for low, high in brackets:
        if low <= age <= high:
            return f"{low}-{high}"
    if age < 30:
        return "30-34"
    return "50-54"


def get_resting_hr_benchmarks() -> dict:
    key = get_age_group_key()
    exc, good, avg = MALE_BENCHMARKS["resting_hr"][key]
    return {
        "excellent": f"<{exc}",
        "good": f"{exc}-{good}",
        "average": f"{good + 1}-{avg}",
        "below_average": f">{avg}",
        "thresholds": (exc, good, avg),
    }


def get_max_hr_expected() -> float:
    age = get_age()
    return MALE_BENCHMARKS["max_hr"]["formula"](age)


def get_hrv_benchmarks() -> dict:
    key = get_age_group_key()
    exc, good, avg = MALE_BENCHMARKS["hrv_sdnn"][key]
    return {
        "excellent": f">{exc}",
        "good": f"{good}-{exc}",
        "average": f"{avg}-{good}",
        "below_average": f"<{avg}",
        "thresholds": (exc, good, avg),
    }


def get_pace_benchmarks() -> dict:
    key = get_age_group_key()
    exc, good, avg = MALE_BENCHMARKS["running_pace_5k"][key]
    return {
        "excellent": f"<{exc:.1f}",
        "good": f"{exc:.1f}-{good:.1f}",
        "average": f"{good:.1f}-{avg:.1f}",
        "below_average": f">{avg:.1f}",
        "thresholds": (exc, good, avg),
    }


def estimate_fitness_age(resting_hr: float, pace_min_per_mile: float) -> int:
    """
    Estimate biological fitness age based on resting HR and running pace.
    Lower resting HR and faster pace = younger fitness age.
    """
    age = get_age()

    # Resting HR contribution: each bpm below 65 = -0.5 years, above = +0.5
    hr_offset = (resting_hr - 65) * 0.5

    # Pace contribution: each min/mile below 8.5 = -1 year, above = +1
    pace_offset = (pace_min_per_mile - 8.5) * 1.0

    fitness_age = age + hr_offset + pace_offset
    return max(18, min(80, int(round(fitness_age))))
