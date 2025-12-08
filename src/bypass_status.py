"""Bypass status display and user visibility"""

import logging

from src.type_definitions import JSONValue

logger = logging.getLogger(__name__)


def log_bypass_status(include_details: bool = True):
    """
    Log current bypass status for user visibility.

    Args:
        include_details: If True, include detailed status for each feature
    """
    try:
        from src.rollback import get_system_status

        status = get_system_status()

        summary = status.get("summary", {})
        if summary.get("any_bypass_active"):
            logger.warning("=" * 70)
            logger.warning("⚠️  BYPASS SYSTEM STATUS - ACTIVE BYPASSES DETECTED")
            logger.warning("=" * 70)

            # System-level bypasses
            bypass_levels = status.get("bypass_levels", {})
            if bypass_levels.get("level_3_system", {}).get("bypassed"):
                reason = bypass_levels["level_3_system"].get("reason", "No reason provided")
                logger.warning(f"🔴 Level 3 (System Bypass): ACTIVE - {reason}")

            if bypass_levels.get("level_4_startup", {}).get("skip_initialization"):
                reason = bypass_levels["level_4_startup"].get("reason", "No reason provided")
                logger.warning(f"🔴 Level 4 (Startup Bypass): ACTIVE - {reason}")

            # Feature-level bypasses
            effective = status.get("effective_status", {})
            config = status.get("config_status", {})

            if include_details:
                logger.warning("\nFeature Status (Effective):")
                for feature, enabled in effective.items():
                    status_icon = "✅" if enabled else "❌"
                    feature_name = feature.replace("_", " ").title()
                    logger.warning(
                        f"  {status_icon} {feature_name}: {'ENABLED' if enabled else 'DISABLED'}"
                    )

                    # Show reason if disabled
                    if not enabled and feature in config:
                        reason = config[feature].get("reason", "")
                        if reason:
                            logger.warning(f"     Reason: {reason}")

            # Runtime overrides
            runtime = status.get("runtime_overrides", {})
            runtime_checks = [
                not runtime.get("system", True),
                not runtime.get("stats_collection", True),
                not runtime.get("expression_checks", True),
                not runtime.get("mutation_logging", True),
            ]
            has_runtime_overrides = any(runtime_checks)

            if has_runtime_overrides:
                logger.warning("\n⚠️  Runtime Overrides Active (via API calls)")
                for key, value in runtime.items():
                    if not value:
                        logger.warning(f"  - {key.replace('_', ' ').title()}: DISABLED")

            logger.warning("=" * 70)
            logger.warning(
                "💡 To check status: from src.rollback import get_system_status; print(get_system_status())"
            )
            logger.warning("=" * 70)
        else:
            logger.info("✅ All system features enabled - No bypasses active")

    except Exception as e:
        logger.error(f"Failed to log bypass status: {e}")


def get_bypass_status_summary() -> dict[str, JSONValue]:
    """
    Get a human-readable summary of bypass status.

    Returns:
        dict: Summary with active bypasses and warnings
    """
    try:
        from src.rollback import get_system_status

        status = get_system_status()

        summary = status.get("summary", {})
        effective = status.get("effective_status", {})
        bypass_levels = status.get("bypass_levels", {})

        active_bypasses = []
        warnings = []

        # Check system-level bypasses
        if bypass_levels.get("level_3_system", {}).get("bypassed"):
            reason = bypass_levels["level_3_system"].get("reason", "No reason")
            active_bypasses.append(f"System Bypass (Level 3): {reason}")
            warnings.append("⚠️  Complete system bypass is active - all features disabled")

        if bypass_levels.get("level_4_startup", {}).get("skip_initialization"):
            reason = bypass_levels["level_4_startup"].get("reason", "No reason")
            active_bypasses.append(f"Startup Bypass (Level 4): {reason}")
            warnings.append("⚠️  System initialization was skipped")

        # Check feature-level bypasses
        for feature, enabled in effective.items():
            if not enabled:
                feature_name = feature.replace("_", " ").title()
                config_info = status.get("config_status", {}).get(feature, {})
                reason = config_info.get("reason", "No reason provided")
                active_bypasses.append(f"{feature_name}: {reason}")

        from src.type_definitions import JSONDict

        # Convert lists to JSONValue-compatible format (str is a valid JSONValue)
        active_bypasses_json: list[JSONValue] = list(active_bypasses)
        warnings_json: list[JSONValue] = list(warnings)

        result: JSONDict = {
            "any_bypass_active": summary.get("any_bypass_active", False),
            "system_fully_bypassed": summary.get("system_fully_bypassed", False),
            "active_bypasses": active_bypasses_json,
            "warnings": warnings_json,
            "effective_status": effective,
        }
        return result
    except Exception as e:
        return {"error": f"Failed to get bypass status: {e}", "any_bypass_active": False}


def format_bypass_status_for_display() -> str:
    """
    Format bypass status as a readable string for display.

    Returns:
        str: Formatted status message
    """
    summary = get_bypass_status_summary()

    if not summary.get("any_bypass_active"):
        return "✅ All system features enabled - No bypasses active"

    lines = ["⚠️  ACTIVE BYPASSES:"]
    lines.append("=" * 60)

    active_bypasses_val = summary.get("active_bypasses", [])
    if isinstance(active_bypasses_val, list):
        for bypass in active_bypasses_val:
            if isinstance(bypass, str):
                lines.append(f"  • {bypass}")

    warnings_val = summary.get("warnings")
    if warnings_val and isinstance(warnings_val, list):
        lines.append("\n⚠️  WARNINGS:")
        for warning in warnings_val:
            if isinstance(warning, str):
                lines.append(f"  {warning}")

    lines.append("=" * 60)

    return "\n".join(lines)
