import zipfile
import os
from pathlib import Path


def extract_zip(zip_path: str, extract_to: str = None) -> str:
    """Extract export.zip and return the path to export.xml."""
    if extract_to is None:
        extract_to = os.path.dirname(zip_path)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_to)

    return get_xml_path(extract_to)


def get_xml_path(base_dir: str) -> str:
    """Find export.xml in the extracted directory."""
    candidates = [
        os.path.join(base_dir, "apple_health_export", "export.xml"),
        os.path.join(base_dir, "export.xml"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    raise FileNotFoundError(
        f"Could not find export.xml in {base_dir}. "
        "Expected at apple_health_export/export.xml"
    )
