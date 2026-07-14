"""Compatibility wrapper for conservative existing-index overlap review."""

import logging
from typing import Any

from src.config_loader import ConfigLoader
from src.workload_dna import build_index_sprawl_report

logger = logging.getLogger(__name__)

try:
    _config_loader = ConfigLoader()
except Exception as exc:
    logger.error("Failed to initialize ConfigLoader: %s, using defaults", exc)
    _config_loader = ConfigLoader()


def is_redundant_index_detection_enabled() -> bool:
    """Return whether the compatibility overlap inventory is enabled."""
    return _config_loader.get_bool("operational.redundant_index_detection.enabled", True)


def find_redundant_indexes(schema_name: str = "public") -> list[dict[str, Any]]:
    """Return conservative overlap findings without declaring redundancy.

    The historical function name remains for callers. Results deliberately use
    ``is_redundant=False`` and ``safe_to_drop=False`` because catalog shape and
    cumulative scan counters cannot prove that an index is removable.
    """
    if not is_redundant_index_detection_enabled():
        logger.debug("Existing-index overlap review is disabled")
        return []

    try:
        report = build_index_sprawl_report(schema=schema_name)
    except Exception as exc:
        logger.error("Failed to inspect existing-index overlap: %s", exc)
        return []

    findings = []
    for finding in report.get("findings", []):
        left = dict(finding.get("left", {}))
        right = dict(finding.get("right", {}))
        findings.append(
            {
                "is_redundant": False,
                "safe_to_drop": False,
                "finding_type": finding.get("type"),
                "table": f"{finding.get('schema')}.{finding.get('table')}",
                "left_index": left.get("name"),
                "left_columns": left.get("columns", []),
                "left_scans": left.get("index_scans", 0),
                "left_size_bytes": left.get("index_size_bytes", 0),
                "right_index": right.get("name"),
                "right_columns": right.get("columns", []),
                "right_scans": right.get("index_scans", 0),
                "right_size_bytes": right.get("index_size_bytes", 0),
                "constraint_protected": bool(finding.get("constraint_protected", False)),
                "action": "manual_review",
                "reason": (
                    "Comparable catalog shapes overlap; usage windows, constraints, and the full "
                    "workload still require operator review."
                ),
            }
        )
    return findings


def suggest_index_consolidation(
    schema_name: str = "public",
) -> list[dict[str, Any]]:
    """Return manual-review items and never executable consolidation advice."""
    suggestions = []
    for finding in find_redundant_indexes(schema_name=schema_name):
        suggestions.append(
            {
                "action": "manual_review",
                "safe_to_drop": False,
                "table": finding["table"],
                "indexes": [finding.get("left_index"), finding.get("right_index")],
                "finding_type": finding.get("finding_type"),
                "reason": finding["reason"],
                "space_savings_mb": 0.0,
            }
        )

    if suggestions:
        logger.info("Generated %s conservative overlap review items", len(suggestions))
    return suggestions
