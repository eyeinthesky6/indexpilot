"""Path utilities for reports and logs"""

from pathlib import Path


def get_reports_dir() -> Path:
    """Get the reports directory, creating it if needed"""
    reports_dir = Path('docs/audit/toolreports')
    reports_dir.mkdir(parents=True, exist_ok=True)
    return reports_dir


def get_logs_dir() -> Path:
    """Get the logs directory, creating it if needed"""
    logs_dir = Path('docs/audit/toolreports/logs')
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def get_report_path(filename: str) -> Path:
    """Get full path for a report file"""
    return get_reports_dir() / filename


def get_log_path(filename: str) -> Path:
    """Get full path for a log file"""
    return get_logs_dir() / filename

