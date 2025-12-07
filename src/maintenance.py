"""Periodic maintenance tasks for database integrity"""

import logging
import time
from datetime import datetime
from typing import cast

from src.monitoring import get_monitoring
from src.resilience import (
    check_database_integrity,
    cleanup_invalid_indexes,
    cleanup_orphaned_indexes,
    cleanup_stale_advisory_locks,
    get_active_operations,
)
from src.type_definitions import JSONDict, JSONValue

logger = logging.getLogger(__name__)

# Load config for maintenance tasks toggle
try:
    from src.config_loader import ConfigLoader

    _config_loader: ConfigLoader | None = ConfigLoader()
except Exception:
    _config_loader = None


def is_maintenance_tasks_enabled() -> bool:
    """Check if maintenance tasks are enabled"""
    if _config_loader is None:
        return True  # Default enabled
    return _config_loader.get_bool("operational.maintenance_tasks.enabled", True)


# Last maintenance run time
_last_maintenance_run: float = 0.0
_maintenance_interval = 3600  # 1 hour

# Last run times for individual maintenance tasks (module-level variables)
_last_pattern_learning: float = 0.0
_last_statistics_refresh: float = 0.0
_last_workload_analysis: float = 0.0
_last_fk_check: float = 0.0
_last_mv_check: float = 0.0
_last_predictive_maintenance: float = 0.0
_last_ml_training: float = 0.0
_last_xgboost_training: float = 0.0

# Get maintenance interval from config if available
try:
    from src.production_config import get_config

    _prod_config = get_config()
    _maintenance_interval = _prod_config.get_int("MAINTENANCE_INTERVAL", 3600)
except (ImportError, ValueError):
    pass  # Use default if config not available


def run_maintenance_tasks(force: bool = False) -> JSONDict:
    """
    Run periodic maintenance tasks to ensure database integrity.

    Tasks:
    - Check database integrity
    - Clean up orphaned indexes
    - Clean up invalid indexes
    - Clean up stale advisory locks
    - Check for stale operations
    - Log bypass status (for user visibility)

    Args:
        force: If True, run even if interval hasn't passed

    Returns:
        dict with maintenance results
    """
    if not is_maintenance_tasks_enabled():
        return {"skipped": True, "reason": "maintenance_tasks_disabled"}

    global _last_maintenance_run

    # Log bypass status periodically for user visibility
    try:
        from src.bypass_status import log_bypass_status

        log_bypass_status(include_details=False)  # Less verbose for periodic logs
    except Exception as e:
        logger.debug(f"Could not log bypass status: {e}")

    current_time = time.time()
    time_since_last = current_time - _last_maintenance_run

    if not force and time_since_last < _maintenance_interval:
        logger.debug(f"Skipping maintenance (last run {time_since_last:.0f}s ago)")
        return {"skipped": True, "reason": "interval_not_passed"}

    logger.info("Running maintenance tasks...")
    _last_maintenance_run = current_time

    cleanup_dict: JSONDict = {}
    results: JSONDict = {
        "timestamp": datetime.now().isoformat(),
        "integrity_check": {},
        "cleanup": cleanup_dict,
        "status": "success",
    }

    monitoring = get_monitoring()

    try:
        # 1. Check database integrity
        integrity_results = check_database_integrity()
        results["integrity_check"] = integrity_results

        if integrity_results.get("status") != "healthy":
            issues_val = integrity_results.get("issues", [])
            issues_list = issues_val if isinstance(issues_val, list) else []
            logger.warning(f"Database integrity check found issues: {issues_list}")
            monitoring.alert(
                "warning", f"Database integrity issues detected: {len(issues_list)} issues"
            )

        # 2. Clean up orphaned indexes
        orphaned = cleanup_orphaned_indexes()
        if orphaned:
            logger.info(f"Cleaned up {len(orphaned)} orphaned indexes")
            monitoring.alert("info", f"Cleaned up {len(orphaned)} orphaned indexes")
        cleanup_dict["orphaned_indexes"] = len(orphaned)

        # 3. Clean up invalid indexes
        invalid = cleanup_invalid_indexes()
        if invalid:
            logger.info(f"Cleaned up {len(invalid)} invalid indexes")
            monitoring.alert("warning", f"Cleaned up {len(invalid)} invalid indexes")
        cleanup_dict["invalid_indexes"] = len(invalid)

        # 4. Clean up stale advisory locks
        stale_locks = cleanup_stale_advisory_locks()
        if stale_locks > 0:
            logger.info(f"Cleaned up {stale_locks} stale advisory locks")
            monitoring.alert("info", f"Cleaned up {stale_locks} stale advisory locks")
        cleanup_dict["stale_advisory_locks"] = stale_locks

        # 5. Check for stale operations
        active_ops = get_active_operations()
        stale_ops = []
        for op in active_ops:
            if isinstance(op, dict):
                duration_val = op.get("duration")
                if isinstance(duration_val, (int, float)) and float(duration_val) > 600:
                    stale_ops.append(op)
        if stale_ops:
            logger.warning(f"Found {len(stale_ops)} stale operations: {stale_ops}")
            monitoring.alert("warning", f"Found {len(stale_ops)} stale operations")
        cleanup_dict["stale_operations"] = len(stale_ops)

        # 6. Clean up unused indexes (if enabled)
        try:
            from src.index_cleanup import find_unused_indexes

            # Check if index cleanup is enabled
            cleanup_enabled = (
                _config_loader.get_bool("features.index_cleanup.enabled", True)
                if _config_loader
                else True
            )
            if cleanup_enabled:
                min_scans = (
                    _config_loader.get_int("features.index_cleanup.min_scans", 10)
                    if _config_loader
                    else 10
                )
                days_unused = (
                    _config_loader.get_int("features.index_cleanup.days_unused", 7)
                    if _config_loader
                    else 7
                )

                unused_indexes = find_unused_indexes(min_scans=min_scans, days_unused=days_unused)
                if unused_indexes:
                    logger.info(f"Found {len(unused_indexes)} unused indexes")
                    cleanup_dict["unused_indexes_found"] = len(unused_indexes)

                    # Check if automatic cleanup is enabled
                    auto_cleanup_enabled = (
                        _config_loader.get_bool("features.index_cleanup.auto_cleanup", False)
                        if _config_loader
                        else False
                    )

                    if auto_cleanup_enabled:
                        # Perform automatic cleanup (non-dry-run)
                        from src.index_cleanup import cleanup_unused_indexes

                        try:
                            removed = cleanup_unused_indexes(
                                min_scans=min_scans,
                                days_unused=days_unused,
                                dry_run=False,
                            )
                            cleanup_dict["unused_indexes_removed"] = len(removed)
                            logger.info(f"Automatically removed {len(removed)} unused indexes")
                        except Exception as cleanup_error:
                            logger.error(f"Automatic cleanup failed: {cleanup_error}")
                            cleanup_dict["unused_indexes_cleanup_error"] = str(cleanup_error)
                    else:
                        # Note: Actual cleanup requires explicit call to cleanup_unused_indexes(dry_run=False)
                        # This is intentional - cleanup is destructive and should be manual or scheduled separately
                        cleanup_dict["unused_indexes_note"] = (
                            "Automatic cleanup disabled - use cleanup_unused_indexes() to remove"
                        )
        except Exception as e:
            logger.debug(f"Could not check for unused indexes: {e}")

        # 7. Monitor index health (if enabled)
        try:
            from src.index_health import find_bloated_indexes, monitor_index_health

            # Check if index health monitoring is enabled
            health_enabled = (
                _config_loader.get_bool("features.index_health.enabled", True)
                if _config_loader
                else True
            )
            if health_enabled:
                bloat_threshold = (
                    _config_loader.get_float("features.index_health.bloat_threshold", 20.0)
                    if _config_loader
                    else 20.0
                )
                min_size_mb = (
                    _config_loader.get_float("features.index_health.min_size_mb", 1.0)
                    if _config_loader
                    else 1.0
                )

                health_data = monitor_index_health(
                    bloat_threshold_percent=bloat_threshold, min_size_mb=min_size_mb
                )
                if health_data.get("indexes"):
                    summary = health_data.get("summary", {})
                    logger.info(
                        f"Index health: {summary.get('healthy', 0)} healthy, "
                        f"{summary.get('bloated', 0)} bloated, "
                        f"{summary.get('underutilized', 0)} underutilized"
                    )
                    cleanup_dict["index_health"] = summary

                    # Check for bloated indexes
                    bloated = find_bloated_indexes(
                        bloat_threshold_percent=bloat_threshold, min_size_mb=min_size_mb
                    )
                    if bloated:
                        logger.info(f"Found {len(bloated)} bloated indexes that may need REINDEX")
                        cleanup_dict["bloated_indexes_found"] = len(bloated)
                        # Note: Actual REINDEX requires explicit call to reindex_bloated_indexes(dry_run=False)
                        # This is intentional - REINDEX is resource-intensive and should be scheduled carefully
        except Exception as e:
            logger.debug(f"Could not monitor index health: {e}")

        # 8. Learn query patterns from history (if enabled)
        try:
            from src.query_pattern_learning import learn_from_fast_queries, learn_from_slow_queries

            # Check if pattern learning is enabled
            pattern_learning_enabled = (
                _config_loader.get_bool("features.pattern_learning.enabled", True)
                if _config_loader
                else True
            )
            if pattern_learning_enabled:
                # Learn patterns every hour (configurable)
                global _last_pattern_learning
                current_time = time.time()
                pattern_interval = (
                    _config_loader.get_int("features.pattern_learning.interval", 3600)
                    if _config_loader
                    else 3600
                )

                if current_time - _last_pattern_learning >= pattern_interval:
                    logger.info("Learning query patterns from history...")
                    slow_patterns = learn_from_slow_queries(time_window_hours=24, min_occurrences=3)
                    fast_patterns = learn_from_fast_queries(
                        time_window_hours=24, min_occurrences=10
                    )

                    cleanup_dict["pattern_learning"] = {
                        "slow_patterns": slow_patterns.get("summary", {}).get("total_patterns", 0),
                        "fast_patterns": fast_patterns.get("summary", {}).get("total_patterns", 0),
                    }

                    _last_pattern_learning = current_time
                    logger.info(
                        f"Learned {slow_patterns.get('summary', {}).get('total_patterns', 0)} slow patterns "
                        f"and {fast_patterns.get('summary', {}).get('total_patterns', 0)} fast patterns"
                    )

                    # ✅ INTEGRATION: XGBoost Model Retraining (arXiv:1603.02754)
                    # Retrain XGBoost model after learning new patterns
                    try:
                        from src.algorithms.xgboost_classifier import (
                            get_xgboost_config,
                            is_xgboost_enabled,
                            train_model,
                        )

                        if is_xgboost_enabled():
                            config = get_xgboost_config()
                            retrain_interval = config.get("retrain_interval_hours", 24)

                            # Check if it's time to retrain (every retrain_interval hours)
                            global _last_xgboost_training
                            hours_since_training = (current_time - _last_xgboost_training) / 3600.0
                            if hours_since_training >= retrain_interval:
                                logger.info("Retraining XGBoost model with new patterns...")
                                trained = train_model(force_retrain=True)
                                if trained:
                                    _last_xgboost_training = current_time
                                    cleanup_dict["xgboost_retraining"] = {
                                        "status": "success",
                                        "model_version": "updated",
                                    }
                                    logger.info("XGBoost model retrained successfully")
                                else:
                                    cleanup_dict["xgboost_retraining"] = {
                                        "status": "failed",
                                        "reason": "insufficient_data",
                                    }
                                    logger.warning(
                                        "XGBoost model retraining failed (insufficient data)"
                                    )
                    except Exception as e:
                        logger.debug(f"XGBoost retraining failed: {e}")
        except Exception as e:
            logger.debug(f"Could not learn query patterns: {e}")

        # 9. Refresh statistics (if enabled)
        try:
            from src.statistics_refresh import (
                get_statistics_refresh_config,
                refresh_stale_statistics,
            )

            stats_config = get_statistics_refresh_config()
            if stats_config["enabled"]:
                # Check if we should refresh statistics
                # Only refresh if interval has passed (configurable, default: daily)
                global _last_statistics_refresh
                current_time = time.time()
                stats_interval = stats_config["interval_hours"] * 3600

                if current_time - _last_statistics_refresh >= stats_interval:
                    logger.info("Refreshing stale statistics...")
                    stats_result = refresh_stale_statistics(
                        stale_threshold_hours=stats_config["stale_threshold_hours"],
                        min_table_size_mb=stats_config["min_table_size_mb"],
                        dry_run=False,  # Actually refresh
                        limit=10,  # Limit to 10 tables per run to avoid overload
                    )

                    cleanup_dict["statistics_refresh"] = {
                        "stale_tables_found": stats_result.get("stale_tables_found", 0),
                        "tables_analyzed": len(stats_result.get("tables_analyzed", [])),
                        "success": stats_result.get("success", False),
                    }

                    if stats_result.get("stale_tables_found", 0) > 0:
                        logger.info(
                            f"Statistics refresh: Found {stats_result.get('stale_tables_found', 0)} "
                            f"stale tables, analyzed {len(stats_result.get('tables_analyzed', []))}"
                        )

                    _last_statistics_refresh = current_time
        except Exception as e:
            logger.debug(f"Could not refresh statistics: {e}")

        # 10. Check for redundant indexes (if enabled)
        try:
            from src.redundant_index_detection import find_redundant_indexes

            redundant_enabled = (
                _config_loader.get_bool("features.redundant_index_detection.enabled", True)
                if _config_loader
                else True
            )
            if redundant_enabled:
                redundant = find_redundant_indexes(schema_name="public")
                if redundant:
                    logger.info(f"Found {len(redundant)} redundant index pairs")
                    cleanup_dict["redundant_indexes_found"] = len(redundant)
                    # Note: Actual cleanup requires explicit action
        except Exception as e:
            logger.debug(f"Could not check for redundant indexes: {e}")

        # 11. Analyze workload (if enabled)
        try:
            from src.workload_analysis import analyze_workload

            workload_enabled = (
                _config_loader.get_bool("features.workload_analysis.enabled", True)
                if _config_loader
                else True
            )
            if workload_enabled:
                # Analyze workload periodically (every 6 hours)
                global _last_workload_analysis
                current_time = time.time()
                workload_interval = 6 * 3600  # 6 hours

                if current_time - _last_workload_analysis >= workload_interval:
                    logger.info("Analyzing workload...")
                    workload_result = analyze_workload(time_window_hours=24)
                    if workload_result.get("overall"):
                        cleanup_dict["workload_analysis"] = workload_result["overall"]
                        logger.info(
                            f"Workload analysis: {workload_result['overall'].get('workload_type', 'unknown')} "
                            f"({workload_result['overall'].get('read_ratio', 0):.1%} reads)"
                        )
                    _last_workload_analysis = current_time
        except Exception as e:
            logger.debug(f"Could not analyze workload: {e}")

        # 12. Check for foreign keys without indexes (if enabled)
        try:
            from src.foreign_key_suggestions import suggest_foreign_key_indexes

            fk_suggestions_enabled = (
                _config_loader.get_bool("features.foreign_key_suggestions.enabled", True)
                if _config_loader
                else True
            )
            if fk_suggestions_enabled:
                # Check for FK indexes periodically (every 6 hours)
                global _last_fk_check
                current_time = time.time()
                fk_check_interval = 6 * 3600  # 6 hours

                if current_time - _last_fk_check >= fk_check_interval:
                    logger.info("Checking for foreign keys without indexes...")
                    fk_suggestions = suggest_foreign_key_indexes(schema_name="public")
                    if fk_suggestions:
                        cleanup_dict["foreign_key_suggestions"] = {
                            "count": len(fk_suggestions),
                            "suggestions": cast(
                                list[JSONValue],
                                [cast(JSONDict, item) for item in fk_suggestions[:5]],
                            ),  # Limit to first 5 for summary
                        }
                        logger.info(
                            f"Found {len(fk_suggestions)} foreign keys without indexes "
                            "(high priority for JOIN performance)"
                        )
                    _last_fk_check = current_time
        except Exception as e:
            logger.debug(f"Could not check for foreign key indexes: {e}")

        # 13. Check for hanging concurrent index builds (if enabled)
        try:
            from src.concurrent_index_monitoring import (
                check_hanging_builds,
                get_concurrent_monitoring_status,
            )

            concurrent_monitoring_enabled = (
                _config_loader.get_bool("features.concurrent_index_monitoring.enabled", True)
                if _config_loader
                else True
            )
            if concurrent_monitoring_enabled:
                hanging_builds = check_hanging_builds()
                if hanging_builds:
                    logger.warning(f"Found {len(hanging_builds)} hanging concurrent index builds")
                    cleanup_dict["hanging_concurrent_builds"] = len(hanging_builds)
                    for build in hanging_builds:
                        monitoring.alert(
                            "warning",
                            f"Hanging concurrent index build: {build['index_name']} "
                            f"(duration: {build['duration_hours']:.1f}h)",
                        )

                # Get monitoring status
                monitoring_status = get_concurrent_monitoring_status()
                cleanup_dict["concurrent_index_monitoring"] = {
                    "active_builds": monitoring_status.get("active_builds_count", 0),
                    "hanging_builds": monitoring_status.get("hanging_builds_count", 0),
                }
        except Exception as e:
            logger.debug(f"Could not check concurrent index builds: {e}")

        # 14. Check materialized views (if enabled)
        try:
            from src.materialized_view_support import (
                find_materialized_views,
                suggest_materialized_view_indexes,
            )

            mv_support_enabled = (
                _config_loader.get_bool("features.materialized_view_support.enabled", True)
                if _config_loader
                else True
            )
            if mv_support_enabled:
                # Check materialized views periodically (every 12 hours)
                global _last_mv_check
                current_time = time.time()
                mv_check_interval = 12 * 3600  # 12 hours

                if current_time - _last_mv_check >= mv_check_interval:
                    logger.info("Checking materialized views...")
                    mvs = find_materialized_views(schema_name="public")
                    if mvs:
                        suggestions = suggest_materialized_view_indexes(schema_name="public")
                        cleanup_dict["materialized_views"] = {
                            "count": len(mvs),
                            "index_suggestions": len(suggestions),
                        }
                        if suggestions:
                            logger.info(
                                f"Found {len(mvs)} materialized views, "
                                f"{len(suggestions)} index suggestions"
                            )
                    _last_mv_check = current_time
        except Exception as e:
            logger.debug(f"Could not check materialized views: {e}")

        # 15. Report safeguard metrics (if enabled)
        try:
            from src.safeguard_monitoring import get_safeguard_metrics, get_safeguard_status

            safeguard_metrics = get_safeguard_metrics()
            safeguard_status = get_safeguard_status()

            cleanup_dict["safeguard_metrics"] = safeguard_metrics
            cleanup_dict["safeguard_status"] = safeguard_status.get("overall_status", "unknown")

            # Log summary
            if safeguard_metrics["index_creation"]["attempts"] > 0:
                success_rate = safeguard_metrics["index_creation"]["success_rate"]
                logger.info(
                    f"Safeguard metrics: Index creation success rate: {success_rate:.1%}, "
                    f"Rate limit triggers: {safeguard_metrics['rate_limiting']['triggers']}, "
                    f"CPU throttles: {safeguard_metrics['cpu_throttling']['triggers']}"
                )
        except Exception as e:
            logger.debug(f"Could not get safeguard metrics: {e}")

        # 13. Advanced index lifecycle - predictive maintenance (Phase 3)
        try:
            from src.index_lifecycle_advanced import run_predictive_maintenance

            predictive_enabled = (
                _config_loader.get_bool("features.predictive_maintenance.enabled", True)
                if _config_loader
                else True
            )
            if predictive_enabled:
                # Run predictive maintenance (daily, configurable)
                global _last_predictive_maintenance
                current_time = time.time()
                predictive_interval = (
                    _config_loader.get_int("features.predictive_maintenance.interval", 86400)
                    if _config_loader
                    else 86400
                )  # 24 hours

                if current_time - _last_predictive_maintenance >= predictive_interval:
                    logger.info("Running predictive maintenance...")
                    predictive_report = run_predictive_maintenance(
                        bloat_threshold_percent=20.0, prediction_days=7
                    )
                    cleanup_dict["predictive_maintenance"] = {
                        "predicted_reindex_needs": len(
                            predictive_report.get("predicted_reindex_needs", [])
                        ),
                        "recommendations": len(predictive_report.get("recommendations", [])),
                    }
                    _last_predictive_maintenance = current_time
        except Exception as e:
            logger.debug(f"Could not run predictive maintenance: {e}")

        # 14. Train ML query interception model (Phase 3)
        try:
            from src.ml_query_interception import train_classifier_from_history

            ml_training_enabled = (
                _config_loader.get_bool("features.ml_interception.training_enabled", True)
                if _config_loader
                else True
            )
            if ml_training_enabled:
                global _last_ml_training
                current_time = time.time()
                ml_training_interval = (
                    _config_loader.get_int("features.ml_interception.training_interval", 86400)
                    if _config_loader
                    else 86400
                )  # 24 hours

                if current_time - _last_ml_training >= ml_training_interval:
                    logger.info("Training ML query interception model...")
                    training_result = train_classifier_from_history(
                        time_window_hours=24, min_samples=50
                    )
                    if training_result.get("status") == "success":
                        cleanup_dict["ml_training"] = {
                            "accuracy": training_result.get("accuracy", 0.0),
                            "samples": training_result.get("samples", 0),
                        }
                        logger.info(
                            f"ML model trained: accuracy {training_result.get('accuracy', 0.0):.1%}, "
                            f"{training_result.get('samples', 0)} samples"
                        )
                    _last_ml_training = current_time
        except Exception as e:
            logger.debug(f"Could not train ML model: {e}")

        logger.info("Maintenance tasks completed successfully")

    except Exception as e:
        logger.error(f"Maintenance tasks failed: {e}")
        results["status"] = "error"
        results["error"] = str(e)
        monitoring.alert("error", f"Maintenance tasks failed: {e}")

    return results


def schedule_maintenance(interval_seconds: int = 3600):
    """
    Schedule periodic maintenance tasks.

    Args:
        interval_seconds: Interval between maintenance runs (default: 1 hour)
    """
    global _maintenance_interval
    _maintenance_interval = interval_seconds
    logger.info(f"Maintenance scheduled to run every {interval_seconds}s")


def get_maintenance_status() -> dict[str, JSONValue]:
    """
    Get status of maintenance system.

    Returns:
        dict with maintenance status
    """
    global _last_maintenance_run, _maintenance_interval

    time_since_last = time.time() - _last_maintenance_run if _last_maintenance_run > 0 else None

    status: JSONDict = {
        "last_run": datetime.fromtimestamp(_last_maintenance_run).isoformat()
        if _last_maintenance_run > 0
        else None,
        "time_since_last": time_since_last,
        "interval_seconds": _maintenance_interval,
        "next_run_in": max(0, _maintenance_interval - time_since_last) if time_since_last else 0,
    }
    return status
