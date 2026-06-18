import pandas as pd
from lxml import etree


# Types we care about
_RECORD_TYPES = {
    "HKQuantityTypeIdentifierHeartRate": "heart_rate",
    "HKQuantityTypeIdentifierRestingHeartRate": "resting_hr",
    "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": "hrv",
    "HKCategoryTypeIdentifierSleepAnalysis": "sleep",
}


def parse_all_records(xml_path: str, progress_callback=None) -> dict[str, pd.DataFrame]:
    """
    Single-pass parser that extracts all record types we need in one scan.
    Returns dict with keys: heart_rate, resting_hr, hrv, sleep.
    """
    buckets = {name: [] for name in _RECORD_TYPES.values()}
    context = etree.iterparse(xml_path, events=("end",), tag="Record")

    for i, (_, record) in enumerate(context):
        rtype = record.get("type", "")
        bucket_name = _RECORD_TYPES.get(rtype)

        if bucket_name is None:
            record.clear()
            while record.getprevious() is not None:
                del record.getparent()[0]
            continue

        if bucket_name == "sleep":
            data = {
                "value": record.get("value", "").replace("HKCategoryValueSleepAnalysis", ""),
                "sourceName": record.get("sourceName", ""),
                "startDate": record.get("startDate", ""),
                "endDate": record.get("endDate", ""),
            }
        else:
            data = {
                "value": record.get("value", ""),
                "unit": record.get("unit", ""),
                "sourceName": record.get("sourceName", ""),
                "startDate": record.get("startDate", ""),
                "endDate": record.get("endDate", ""),
            }

        buckets[bucket_name].append(data)

        record.clear()
        while record.getprevious() is not None:
            del record.getparent()[0]

        if progress_callback and i % 100000 == 0:
            progress_callback(f"  ...scanned {i:,} records")

    # Convert to DataFrames
    result = {}
    for name, records in buckets.items():
        df = pd.DataFrame(records)
        if not df.empty:
            df["startDate"] = pd.to_datetime(df["startDate"], format="%Y-%m-%d %H:%M:%S %z", utc=True)
            df["endDate"] = pd.to_datetime(df["endDate"], format="%Y-%m-%d %H:%M:%S %z", utc=True)
            if name == "sleep":
                df["duration_hours"] = (df["endDate"] - df["startDate"]).dt.total_seconds() / 3600
            else:
                df["value"] = pd.to_numeric(df["value"], errors="coerce")
        result[name] = df

    return result


# Keep individual parsers for backwards compatibility (they now just call the single-pass)
def parse_heart_rate(xml_path: str, progress_callback=None) -> pd.DataFrame:
    return parse_all_records(xml_path, progress_callback).get("heart_rate", pd.DataFrame())


def parse_resting_heart_rate(xml_path: str, progress_callback=None) -> pd.DataFrame:
    return parse_all_records(xml_path, progress_callback).get("resting_hr", pd.DataFrame())


def parse_hrv(xml_path: str, progress_callback=None) -> pd.DataFrame:
    return parse_all_records(xml_path, progress_callback).get("hrv", pd.DataFrame())


def parse_sleep(xml_path: str, progress_callback=None) -> pd.DataFrame:
    return parse_all_records(xml_path, progress_callback).get("sleep", pd.DataFrame())
