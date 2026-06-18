import os
import pandas as pd
import duckdb
from pathlib import Path
from .extract import extract_zip, get_xml_path
from .workouts import parse_workouts
from .records import parse_all_records

DB_NAME = "health_data.duckdb"

# All dataset names
DATASET_NAMES = ["workouts", "heart_rate", "resting_hr", "hrv", "sleep"]

# Date column used for incremental detection per table
DATE_COLUMNS = {
    "workouts": "StartDate",
    "heart_rate": "startDate",
    "resting_hr": "startDate",
    "hrv": "startDate",
    "sleep": "startDate",
}


def _db_path(base_dir: str) -> str:
    return os.path.join(base_dir, DB_NAME)


def _get_connection(base_dir: str) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(_db_path(base_dir))


def _table_exists(con: duckdb.DuckDBPyConnection, table: str) -> bool:
    result = con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name = ?", [table]
    ).fetchone()
    return result[0] > 0


def _get_max_date(con: duckdb.DuckDBPyConnection, table: str, date_col: str):
    """Get the maximum date in a table, or None if table is empty/missing."""
    if not _table_exists(con, table):
        return None
    result = con.execute(f'SELECT MAX("{date_col}") FROM {table}').fetchone()
    return result[0] if result[0] is not None else None


def _needs_update(con: duckdb.DuckDBPyConnection, base_dir: str, zip_path: str) -> bool:
    """Check if DB needs to be populated: missing file, empty, or zip is newer."""
    db = _db_path(base_dir)
    if not os.path.exists(db):
        return True
    # Check that at least one data table exists and has rows
    all_empty = True
    for name in DATASET_NAMES:
        if _table_exists(con, name):
            count = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
            if count > 0:
                all_empty = False
                break
    if all_empty:
        return True
    return os.path.getmtime(zip_path) > os.path.getmtime(db)


def _store_dataset(con, name: str, df_new: pd.DataFrame, date_col: str):
    """Store a dataset into DuckDB, appending only new records if table exists."""
    if df_new.empty:
        return

    max_date = _get_max_date(con, name, date_col)

    if max_date is not None:
        if hasattr(df_new[date_col].dtype, "tz") and df_new[date_col].dtype.tz is not None:
            max_date_ts = pd.Timestamp(max_date, tz=df_new[date_col].dtype.tz)
        else:
            max_date_ts = pd.Timestamp(max_date)
        df_append = df_new[df_new[date_col] > max_date_ts]
    else:
        df_append = df_new

    if not df_append.empty:
        if _table_exists(con, name):
            con.execute(f"INSERT INTO {name} SELECT * FROM df_append")
        else:
            con.execute(f"CREATE TABLE {name} AS SELECT * FROM df_append")
    elif not _table_exists(con, name):
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM df_new WHERE 1=0")


def load_or_parse(base_dir: str, progress_callback=None) -> dict[str, pd.DataFrame]:
    """
    Load data from DuckDB. If export.zip is newer, incrementally parse only new records.
    Single-pass parsing for records (HR, HRV, sleep) + one pass for workouts.
    Returns dict with keys: workouts, heart_rate, resting_hr, hrv, sleep.
    """
    zip_path = os.path.join(base_dir, "export.zip")
    if not os.path.exists(zip_path):
        raise FileNotFoundError(
            f"No export.zip found in {base_dir}. "
            "Please place your Apple Health export.zip in the app directory."
        )

    con = _get_connection(base_dir)

    # If no update needed, just read from DuckDB
    if not _needs_update(con, base_dir, zip_path):
        if progress_callback:
            progress_callback("Loading from database...")
        result = {}
        for name in DATASET_NAMES:
            if _table_exists(con, name):
                result[name] = con.execute(f"SELECT * FROM {name}").fetchdf()
            else:
                result[name] = pd.DataFrame()
        con.close()
        return result

    # Extract zip
    if progress_callback:
        progress_callback("Extracting export.zip...")
    xml_path = extract_zip(zip_path, base_dir)

    # Parse workouts (separate pass — different XML element)
    if progress_callback:
        progress_callback("Parsing workouts...")
    df_workouts = parse_workouts(xml_path)
    _store_dataset(con, "workouts", df_workouts, DATE_COLUMNS["workouts"])

    # Parse all record types in a SINGLE pass through the XML
    if progress_callback:
        progress_callback("Parsing health records (HR, HRV, sleep)... single pass through 3M+ records")
    record_dfs = parse_all_records(xml_path, progress_callback)

    for name in ["heart_rate", "resting_hr", "hrv", "sleep"]:
        df = record_dfs.get(name, pd.DataFrame())
        _store_dataset(con, name, df, DATE_COLUMNS[name])

    # Read all tables back
    result = {}
    for name in DATASET_NAMES:
        if _table_exists(con, name):
            result[name] = con.execute(f"SELECT * FROM {name}").fetchdf()
        else:
            result[name] = pd.DataFrame()

    # Touch the DB file to mark it as up-to-date with the zip
    os.utime(_db_path(base_dir), None)
    con.close()
    return result
