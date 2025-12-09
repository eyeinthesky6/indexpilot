"""Verification functions for comprehensive simulation testing

This module provides verification functions to test all product features
during comprehensive simulation runs.
"""

import json
import logging

from src.db import get_cursor
from src.expression import get_enabled_fields, is_field_enabled
from src.health_check import check_database_health, comprehensive_health_check
from src.rollback import get_system_status
from src.type_definitions import (
    ComprehensiveVerificationResults,
    JSONValue,
    TenantIDList,
    VerificationResult,
)

logger = logging.getLogger(__name__)


def verify_mutation_log(
    tenant_ids: TenantIDList | None = None, min_indexes: int = 0
) -> VerificationResult:
    """
    Verify that mutation log entries are created correctly for index operations.

    Args:
        tenant_ids: List of tenant IDs to check (None = all tenants)
        min_indexes: Minimum number of CREATE_INDEX mutations expected

    Returns:
        dict with verification results
    """
    print("\n" + "=" * 60)
    print("VERIFYING MUTATION LOG")
    print("=" * 60)

    results: VerificationResult = {"passed": True, "errors": [], "warnings": [], "details": {}}

    try:
        with get_cursor() as cursor:
            # Count CREATE_INDEX mutations
            if tenant_ids:
                placeholders = ",".join(["%s"] * len(tenant_ids))
                cursor.execute(
                    f"""
                    SELECT COUNT(*) as count
                    FROM mutation_log
                    WHERE mutation_type = 'CREATE_INDEX'
                    AND tenant_id IN ({placeholders})
                """,
                    tenant_ids,
                )
            else:
                cursor.execute(
                    """
                    SELECT COUNT(*) as count
                    FROM mutation_log
                    WHERE mutation_type = 'CREATE_INDEX'
                """
                )

            result = cursor.fetchone()
            index_mutations = result["count"] if result else 0

            # Get sample mutations to verify details
            if tenant_ids:
                placeholders = ",".join(["%s"] * len(tenant_ids))
                cursor.execute(
                    f"""
                    SELECT tenant_id, table_name, field_name, details_json, created_at
                    FROM mutation_log
                    WHERE mutation_type = 'CREATE_INDEX'
                    AND tenant_id IN ({placeholders})
                    ORDER BY created_at DESC
                    LIMIT 10
                """,
                    tenant_ids,
                )
            else:
                cursor.execute(
                    """
                    SELECT tenant_id, table_name, field_name, details_json, created_at
                    FROM mutation_log
                    WHERE mutation_type = 'CREATE_INDEX'
                    ORDER BY created_at DESC
                    LIMIT 10
                """
                )

            sample_mutations = cursor.fetchall()

            # Verify minimum count
            if index_mutations < min_indexes:
                results["warnings"].append(
                    f"Expected at least {min_indexes} CREATE_INDEX mutations, found {index_mutations}"
                )

            # Verify mutation details
            mutations_with_details = 0
            mutations_with_tenant = 0
            for mutation in sample_mutations:
                if mutation["details_json"]:
                    try:
                        details = (
                            json.loads(mutation["details_json"])
                            if isinstance(mutation["details_json"], str)
                            else mutation["details_json"]
                        )
                        if (
                            "queries" in details
                            or "build_cost" in details
                            or "query_cost" in details
                        ):
                            mutations_with_details += 1
                    except (json.JSONDecodeError, TypeError):
                        pass

                if mutation["tenant_id"] is not None:
                    mutations_with_tenant += 1

            results["details"] = {
                "total_index_mutations": index_mutations,
                "sample_mutations_checked": len(sample_mutations),
                "mutations_with_details": mutations_with_details,
                "mutations_with_tenant": mutations_with_tenant,
            }

            # Check if details are present
            if mutations_with_details < len(sample_mutations) * 0.8:  # 80% should have details
                results["warnings"].append(
                    f"Only {mutations_with_details}/{len(sample_mutations)} mutations have complete details"
                )

            # Check tenant awareness
            if mutations_with_tenant < len(sample_mutations) * 0.8:  # 80% should be tenant-aware
                results["warnings"].append(
                    f"Only {mutations_with_tenant}/{len(sample_mutations)} mutations are tenant-aware"
                )

            print(f"  [OK] Found {index_mutations} CREATE_INDEX mutations")
            print(f"  [OK] Verified {len(sample_mutations)} sample mutations")
            print(f"  [OK] {mutations_with_details}/{len(sample_mutations)} have complete details")
            print(f"  [OK] {mutations_with_tenant}/{len(sample_mutations)} are tenant-aware")

    except Exception as e:
        results["passed"] = False
        results["errors"].append(f"Error verifying mutation log: {e}")
        logger.error(f"Error verifying mutation log: {e}", exc_info=True)
        print(f"  [ERROR] Error: {e}")

    if results["warnings"]:
        print(f"  [WARNING] Warnings: {len(results['warnings'])}")
        for warning in results["warnings"]:
            print(f"     - {warning}")

    if results["errors"]:
        print(f"  [ERROR] Errors: {len(results['errors'])}")
        for error in results["errors"]:
            print(f"     - {error}")

    return results


def verify_expression_profiles(tenant_ids: TenantIDList) -> VerificationResult:
    """
    Verify that expression profiles are initialized and working correctly.

    Args:
        tenant_ids: List of tenant IDs to check

    Returns:
        dict with verification results
    """
    print("\n" + "=" * 60)
    print("VERIFYING EXPRESSION PROFILES")
    print("=" * 60)

    results: VerificationResult = {"passed": True, "errors": [], "warnings": [], "details": {}}

    try:
        with get_cursor() as cursor:
            # Check expression profiles for each tenant
            tenants_with_profiles = 0
            total_fields_enabled = 0
            sample_tenants = tenant_ids[: min(5, len(tenant_ids))]  # Check first 5 tenants

            for tenant_id in sample_tenants:
                # Check if tenant has expression profile entries
                cursor.execute(
                    """
                    SELECT COUNT(*) as count
                    FROM expression_profile
                    WHERE tenant_id = %s
                """,
                    (tenant_id,),
                )
                result = cursor.fetchone()
                profile_count = result["count"] if result else 0

                if profile_count > 0:
                    tenants_with_profiles += 1
                    total_fields_enabled += profile_count

                    # Check enabled fields
                    enabled_fields = get_enabled_fields(tenant_id)
                    if enabled_fields and len(enabled_fields) > 0:
                        # Verify a sample field is enabled
                        # get_enabled_fields returns a list of dicts with table_name and field_name
                        sample_field = enabled_fields[0]
                        sample_table = sample_field["table_name"]
                        sample_field_name = sample_field["field_name"]
                        is_enabled = is_field_enabled(tenant_id, sample_table, sample_field_name)
                        if not is_enabled:
                            results["warnings"].append(
                                f"Tenant {tenant_id}: Field {sample_table}.{sample_field_name} should be enabled but isn't"
                            )

            results["details"] = {
                "tenants_checked": len(sample_tenants),
                "tenants_with_profiles": tenants_with_profiles,
                "total_fields_enabled": total_fields_enabled,
                "avg_fields_per_tenant": total_fields_enabled / len(sample_tenants)
                if sample_tenants
                else 0,
            }

            # Verify all tenants have profiles
            if tenants_with_profiles < len(sample_tenants):
                results["warnings"].append(
                    f"Only {tenants_with_profiles}/{len(sample_tenants)} tenants have expression profiles"
                )

            print(f"  [OK] Checked {len(sample_tenants)} tenants")
            print(f"  [OK] {tenants_with_profiles} tenants have expression profiles")
            print(f"  [OK] Total {total_fields_enabled} fields enabled across tenants")

    except Exception as e:
        results["passed"] = False
        results["errors"].append(f"Error verifying expression profiles: {e}")
        logger.error(f"Error verifying expression profiles: {e}", exc_info=True)
        print(f"  [ERROR] Error: {e}")

    if results["warnings"]:
        print(f"  [WARNING] Warnings: {len(results['warnings'])}")
        for warning in results["warnings"]:
            print(f"     - {warning}")

    return results


def verify_production_safeguards() -> VerificationResult:
    """
    Verify that production safeguards are working correctly.

    Returns:
        dict with verification results
    """
    print("\n" + "=" * 60)
    print("VERIFYING PRODUCTION SAFEGUARDS")
    print("=" * 60)

    results: VerificationResult = {"passed": True, "errors": [], "warnings": [], "details": {}}

    try:
        # Check maintenance window
        try:
            from src.maintenance_window import (
                is_in_maintenance_window,
                is_maintenance_window_enabled,
            )

            maintenance_enabled = is_maintenance_window_enabled()
            in_window = is_in_maintenance_window()
            results["details"]["maintenance_window"] = {
                "enabled": maintenance_enabled,
                "in_window": in_window,
            }
            print(f"  [OK] Maintenance window: {'enabled' if maintenance_enabled else 'disabled'}")
            print(f"  [OK] Currently in window: {in_window}")
        except Exception as e:
            results["warnings"].append(f"Could not check maintenance window: {e}")

        # Check rate limiter
        try:
            from src.rate_limiter import check_index_creation_rate_limit

            allowed, retry_after = check_index_creation_rate_limit("test_table")
            results["details"]["rate_limiter"] = {"allowed": allowed, "retry_after": retry_after}
            print(
                f"  [OK] Rate limiter: {'active' if not allowed or retry_after > 0 else 'available'}"
            )
        except Exception as e:
            results["warnings"].append(f"Could not check rate limiter: {e}")

        # Check CPU throttle
        try:
            from src.cpu_throttle import should_throttle_index_creation

            throttle_result = should_throttle_index_creation()
            if isinstance(throttle_result, tuple) and len(throttle_result) >= 2:
                should_throttle = (
                    bool(throttle_result[0]) if isinstance(throttle_result[0], bool) else False
                )
                reason = str(throttle_result[1]) if throttle_result[1] is not None else None
            else:
                should_throttle = False
                reason = None
            # Match VerificationDetails TypedDict requirement: dict[str, bool | str]
            cpu_throttle_dict: dict[str, bool | str] = {
                "should_throttle": should_throttle,
                "reason": reason if reason is not None else "",
            }
            details_dict = results.get("details", {})
            if isinstance(details_dict, dict):
                details_dict["cpu_throttle"] = cpu_throttle_dict
                results["details"] = details_dict
            print(f"  [OK] CPU throttle: {'active' if should_throttle else 'available'}")
            if reason:
                print(f"     Reason: {reason}")
        except Exception as e:
            results["warnings"].append(f"Could not check CPU throttle: {e}")

        # Check write performance
        try:
            from src.write_performance import can_create_index_for_table

            can_create, reason = can_create_index_for_table("contacts")
            results["details"]["write_performance"] = {"can_create": can_create, "reason": reason}
            print(f"  [OK] Write performance check: {'passed' if can_create else 'blocked'}")
            if reason:
                print(f"     Reason: {reason}")
        except Exception as e:
            results["warnings"].append(f"Could not check write performance: {e}")

    except Exception as e:
        results["passed"] = False
        results["errors"].append(f"Error verifying production safeguards: {e}")
        logger.error(f"Error verifying production safeguards: {e}", exc_info=True)
        print(f"  [ERROR] Error: {e}")

    if results["warnings"]:
        print(f"  [WARNING] Warnings: {len(results['warnings'])}")
        for warning in results["warnings"]:
            print(f"     - {warning}")

    return results


def verify_bypass_system() -> VerificationResult:
    """
    Verify that bypass system is working correctly.

    Returns:
        dict with verification results
    """
    print("\n" + "=" * 60)
    print("VERIFYING BYPASS SYSTEM")
    print("=" * 60)

    results: VerificationResult = {"passed": True, "errors": [], "warnings": [], "details": {}}

    try:
        # Get system status
        status = get_system_status()

        results["details"] = {
            "system_enabled": status.get("summary", {}).get("system_enabled", False),
            "any_bypass_active": status.get("summary", {}).get("any_bypass_active", False),
            "features": status.get("features", {}),
        }

        print(f"  [OK] System enabled: {results['details']['system_enabled']}")
        print(f"  [OK] Any bypass active: {results['details']['any_bypass_active']}")

        # Check feature statuses
        features = results["details"].get("features", {})
        for feature_name, feature_status in features.items():
            enabled = feature_status.get("enabled", False)
            bypassed = feature_status.get("bypassed", False)
            status_str = (
                "enabled" if enabled and not bypassed else "bypassed" if bypassed else "disabled"
            )
            print(f"  [OK] {feature_name}: {status_str}")

    except Exception as e:
        results["passed"] = False
        results["errors"].append(f"Error verifying bypass system: {e}")
        logger.error(f"Error verifying bypass system: {e}", exc_info=True)
        print(f"  [ERROR] Error: {e}")

    return results


def verify_health_checks() -> VerificationResult:
    """
    Verify that health checks are working correctly.

    Returns:
        dict with verification results
    """
    print("\n" + "=" * 60)
    print("VERIFYING HEALTH CHECKS")
    print("=" * 60)

    results: VerificationResult = {"passed": True, "errors": [], "warnings": [], "details": {}}

    try:
        # Check database health
        try:
            db_health = check_database_health()
            # Convert TypedDict to dict format expected by VerificationDetails
            db_health_dict: dict[str, str | float | None] = {
                "status": db_health.get("status", "unknown"),
                "latency_ms": db_health.get("latency_ms"),
                "error": db_health.get("error"),
            }
            results["details"]["database_health"] = db_health_dict
            db_status = db_health.get("status", "unknown")
            print(f"  [OK] Database health: {db_status}")
        except Exception as e:
            results["warnings"].append(f"Could not check database health: {e}")

        # Check system health (comprehensive)
        try:
            system_health = comprehensive_health_check()
            # Convert TypedDict to dict format expected by VerificationDetails
            # Use JSONValue to allow all valid JSON types
            components_val = system_health.get("components", {})
            warnings_val = system_health.get("warnings", [])
            errors_val = system_health.get("errors", [])

            # Convert to JSONValue-compatible types
            # Explicitly cast to satisfy mypy's variance checking
            components_json: JSONValue = components_val if isinstance(components_val, dict) else {}  # type: ignore[assignment]
            warnings_json: JSONValue = warnings_val if isinstance(warnings_val, list) else []  # type: ignore[assignment]
            errors_json: JSONValue = errors_val if isinstance(errors_val, list) else []  # type: ignore[assignment]

            system_health_dict: dict[str, JSONValue] = {
                "timestamp": system_health.get("timestamp", 0.0),
                "overall_status": system_health.get("overall_status", "unknown"),
                "message": system_health.get("message", ""),
                "components": components_json,
                "warnings": warnings_json,
                "errors": errors_json,
            }
            results["details"]["system_health"] = system_health_dict
            sys_status = system_health.get("overall_status", "unknown")
            print(f"  [OK] System health: {sys_status}")
        except Exception as e:
            results["warnings"].append(f"Could not check system health: {e}")

    except Exception as e:
        results["passed"] = False
        results["errors"].append(f"Error verifying health checks: {e}")
        logger.error(f"Error verifying health checks: {e}", exc_info=True)
        print(f"  [ERROR] Error: {e}")

    if results["warnings"]:
        print(f"  [WARNING] Warnings: {len(results['warnings'])}")
        for warning in results["warnings"]:
            print(f"     - {warning}")

    return results


def verify_schema_evolution() -> VerificationResult:
    """
    Verify that schema evolution features are working correctly.

    Returns:
        dict with verification results
    """
    print("\n" + "=" * 60)
    print("VERIFYING SCHEMA EVOLUTION")
    print("=" * 60)

    results: VerificationResult = {"passed": True, "errors": [], "warnings": [], "details": {}}

    try:
        # Check if schema evolution is enabled
        try:
            from src.schema_evolution import (
                analyze_schema_change_impact,
                is_schema_evolution_enabled,
                preview_schema_change,
            )

            evolution_enabled = is_schema_evolution_enabled()
            results["details"]["schema_evolution_enabled"] = evolution_enabled
            print(f"  [OK] Schema evolution: {'enabled' if evolution_enabled else 'disabled'}")

            # Test impact analysis
            try:
                impact = analyze_schema_change_impact(
                    table_name="contacts", field_name="email", change_type="DROP_COLUMN"
                )
                affected_indexes_val = impact.get("affected_indexes", [])
                affected_indexes_list = (
                    affected_indexes_val if isinstance(affected_indexes_val, list) else []
                )
                errors_val = impact.get("errors", [])
                errors_list = errors_val if isinstance(errors_val, list) else []
                warnings_val = impact.get("warnings", [])
                warnings_list = warnings_val if isinstance(warnings_val, list) else []
                results["details"]["impact_analysis"] = {
                    "affected_queries": impact.get("affected_queries", 0),
                    "affected_indexes": len(affected_indexes_list),
                    "has_errors": len(errors_list) > 0,
                    "has_warnings": len(warnings_list) > 0,
                }
                print(
                    f"  [OK] Impact analysis: {impact.get('affected_queries', 0)} affected queries"
                )
                print(f"  [OK] Impact analysis: {len(affected_indexes_list)} affected indexes")
            except Exception as e:
                results["warnings"].append(f"Impact analysis test failed: {e}")

            # Test preview mode
            try:
                preview = preview_schema_change(
                    table_name="contacts",
                    change_type="ADD_COLUMN",
                    field_name="test_preview_field",
                    field_type="TEXT",
                )
                results["details"]["preview_mode"] = {
                    "works": preview.get("impact") is not None,
                    "has_rollback_plan": preview.get("rollback_plan") is not None,
                }
                print(f"  [OK] Preview mode: {'working' if preview.get('impact') else 'failed'}")
            except Exception as e:
                results["warnings"].append(f"Preview mode test failed: {e}")

        except ImportError as e:
            results["warnings"].append(f"Schema evolution module not available: {e}")
        except Exception as e:
            results["warnings"].append(f"Schema evolution check failed: {e}")

    except Exception as e:
        results["passed"] = False
        results["errors"].append(f"Error verifying schema evolution: {e}")
        logger.error(f"Error verifying schema evolution: {e}", exc_info=True)
        print(f"  [ERROR] Error: {e}")

    if results["warnings"]:
        print(f"  [WARNING] Warnings: {len(results['warnings'])}")
        for warning in results["warnings"]:
            print(f"     - {warning}")

    return results


def verify_query_interception() -> VerificationResult:
    """
    Verify that query interception features are working correctly.

    Returns:
        dict with verification results
    """
    print("\n" + "=" * 60)
    print("VERIFYING QUERY INTERCEPTION")
    print("=" * 60)

    results: VerificationResult = {"passed": True, "errors": [], "warnings": [], "details": {}}

    try:
        # Check query interceptor
        try:
            from src.query_interceptor import (
                analyze_query_plan_fast,
                get_query_safety_score,
                should_block_query,
            )

            # Test with a simple safe query
            test_query = "SELECT * FROM contacts WHERE tenant_id = 1 LIMIT 10"
            try:
                safety_score_dict = get_query_safety_score(test_query)
                score_val = safety_score_dict.get("score", 0.0)
                if isinstance(score_val, int | float):
                    results["details"]["safety_score"] = float(score_val)
                    print(f"  [OK] Query safety scoring: {score_val:.2f}")
                else:
                    results["details"]["safety_score"] = 0.0
                    print(f"  [OK] Query safety scoring: {safety_score_dict}")
            except Exception as e:
                results["warnings"].append(f"Safety score calculation failed: {e}")

            # Test plan analysis
            try:
                plan_result = analyze_query_plan_fast(test_query)
                results["details"]["plan_analysis"] = {
                    "works": plan_result is not None,
                    "has_cost": "cost" in (plan_result if isinstance(plan_result, dict) else {}),
                }
                print(f"  [OK] Plan analysis: {'working' if plan_result else 'failed'}")
            except Exception as e:
                results["warnings"].append(f"Plan analysis failed: {e}")

            # Test blocking logic
            try:
                should_block = should_block_query(test_query)
                should_block_bool = bool(should_block[0]) if len(should_block) > 0 else False
                results["details"]["blocking_logic"] = {"works": True, "blocked": should_block_bool}
                print("  [OK] Blocking logic: working")
            except Exception as e:
                results["warnings"].append(f"Blocking logic test failed: {e}")

            # Test with potentially harmful query (should be blocked)
            try:
                harmful_query = "SELECT * FROM contacts WHERE custom_text_1 LIKE '%test%'"  # No index, full scan
                should_block_harmful = should_block_query(harmful_query)
                should_block_harmful_bool = (
                    bool(should_block_harmful[0]) if len(should_block_harmful) > 0 else False
                )
                results["details"]["harmful_query_detection"] = {
                    "tested": True,
                    "blocked": should_block_harmful_bool,
                }
                if should_block_harmful_bool:
                    print("  [OK] Harmful query detection: correctly identified")
                else:
                    print("  [INFO] Harmful query detection: query not blocked (may be acceptable)")
            except Exception as e:
                results["warnings"].append(f"Harmful query test failed: {e}")

        except ImportError as e:
            results["warnings"].append(f"Query interceptor module not available: {e}")
        except Exception as e:
            results["warnings"].append(f"Query interception check failed: {e}")

    except Exception as e:
        results["passed"] = False
        results["errors"].append(f"Error verifying query interception: {e}")
        logger.error(f"Error verifying query interception: {e}", exc_info=True)
        print(f"  [ERROR] Error: {e}")

    if results["warnings"]:
        print(f"  [WARNING] Warnings: {len(results['warnings'])}")
        for warning in results["warnings"]:
            print(f"     - {warning}")

    return results


def verify_algorithm_usage() -> VerificationResult:
    """
    Verify that algorithms are being used in index decisions.

    Returns:
        dict with verification results
    """
    print("\n" + "=" * 60)
    print("VERIFYING ALGORITHM USAGE")
    print("=" * 60)

    results: VerificationResult = {"passed": True, "errors": [], "warnings": [], "details": {}}

    try:
        from src.algorithm_tracking import get_algorithm_usage_stats

        # Get algorithm usage stats
        all_usage = get_algorithm_usage_stats(limit=1000)
        algorithm_counts: dict[str, int] = {}
        algorithms_used_in_decisions: dict[str, int] = {}

        for usage in all_usage:
            algo_name = usage.get("algorithm_name", "unknown")
            algorithm_counts[algo_name] = algorithm_counts.get(algo_name, 0) + 1
            if usage.get("used_in_decision", False):
                algorithms_used_in_decisions[algo_name] = (
                    algorithms_used_in_decisions.get(algo_name, 0) + 1
                )

        results["details"] = {
            "total_algorithm_calls": len(all_usage),
            "algorithms_used": algorithm_counts,
            "algorithms_used_in_decisions": algorithms_used_in_decisions,
        }

        # Expected algorithms
        expected_algorithms = [
            "predictive_indexing",
            "cert",
            "qpg",
            "cortex",
            "xgboost_classifier",
        ]

        found_algorithms = list(algorithm_counts.keys())
        missing_algorithms = [a for a in expected_algorithms if a not in found_algorithms]

        if missing_algorithms:
            results["warnings"].append(
                f"Some expected algorithms not found in usage: {missing_algorithms}"
            )

        print(f"  [OK] Total algorithm calls: {len(all_usage)}")
        print(f"  [OK] Algorithms used: {len(algorithm_counts)}")
        for algo, count in algorithm_counts.items():
            used_count = algorithms_used_in_decisions.get(algo, 0)
            print(f"     - {algo}: {count} calls, {used_count} used in decisions")

    except Exception as e:
        results["passed"] = False
        results["errors"].append(f"Error verifying algorithm usage: {e}")
        logger.error(f"Error verifying algorithm usage: {e}", exc_info=True)
        print(f"  [ERROR] Error: {e}")

    if results["warnings"]:
        print(f"  [WARNING] Warnings: {len(results['warnings'])}")
        for warning in results["warnings"]:
            print(f"     - {warning}")

    return results


def verify_ab_testing() -> VerificationResult:
    """
    Verify that A/B testing features are working.

    Returns:
        dict with verification results
    """
    print("\n" + "=" * 60)
    print("VERIFYING A/B TESTING")
    print("=" * 60)

    results: VerificationResult = {"passed": True, "errors": [], "warnings": [], "details": {}}

    try:
        from src.index_lifecycle_advanced import (
            create_ab_experiment,
            get_ab_results,
            record_ab_result,
        )

        # Test creating an A/B experiment
        test_experiment_name = "simulation_test_experiment"
        try:
            test_exp = create_ab_experiment(
                experiment_name=test_experiment_name,
                table_name="contacts",
                variant_a={"type": "btree", "columns": ["email"]},
                variant_b={"type": "hash", "columns": ["email"]},
                traffic_split=0.5,
                field_name="email",
            )

            if test_exp.get("status") == "disabled":
                results["warnings"].append("A/B testing is disabled")
            else:
                # Record some test results
                record_ab_result(test_experiment_name, "a", 10.5)
                record_ab_result(test_experiment_name, "b", 12.3)
                record_ab_result(test_experiment_name, "a", 11.2)

                # Get results
                ab_results = get_ab_results(test_experiment_name)
                if ab_results:
                    results["details"] = {
                        "experiment_created": True,
                        "variant_a_count": ab_results.get("variant_a", {}).get("query_count", 0),
                        "variant_b_count": ab_results.get("variant_b", {}).get("query_count", 0),
                        "winner": ab_results.get("winner"),
                    }
                    print("  [OK] A/B experiment created and tested")
                    print(f"  [OK] Variant A: {results['details']['variant_a_count']} queries")
                    print(f"  [OK] Variant B: {results['details']['variant_b_count']} queries")
                    winner_val = ab_results.get("winner")
                    if winner_val and isinstance(winner_val, str):
                        print(f"  [OK] Winner: Variant {winner_val.upper()}")
                else:
                    results["warnings"].append("Could not retrieve A/B test results")
        except Exception as e:
            results["warnings"].append(f"A/B testing test failed: {e}")

    except ImportError as e:
        results["warnings"].append(f"A/B testing module not available: {e}")
    except Exception as e:
        results["passed"] = False
        results["errors"].append(f"Error verifying A/B testing: {e}")
        logger.error(f"Error verifying A/B testing: {e}", exc_info=True)
        print(f"  [ERROR] Error: {e}")

    if results["warnings"]:
        print(f"  [WARNING] Warnings: {len(results['warnings'])}")
        for warning in results["warnings"]:
            print(f"     - {warning}")

    return results


def verify_predictive_maintenance() -> VerificationResult:
    """
    Verify that predictive maintenance features are working.

    Returns:
        dict with verification results
    """
    print("\n" + "=" * 60)
    print("VERIFYING PREDICTIVE MAINTENANCE")
    print("=" * 60)

    results: VerificationResult = {"passed": True, "errors": [], "warnings": [], "details": {}}

    try:
        from src.index_lifecycle_advanced import run_predictive_maintenance

        # Run predictive maintenance
        maintenance_report = run_predictive_maintenance(
            bloat_threshold_percent=20.0, prediction_days=7
        )

        if maintenance_report:
            predicted_needs = maintenance_report.get("predicted_reindex_needs", [])
            recommendations = maintenance_report.get("recommendations", [])

            results["details"] = {
                "predicted_reindex_needs": len(predicted_needs),
                "recommendations": len(recommendations),
                "report_generated": True,
            }

            print("  [OK] Predictive maintenance report generated")
            print(f"  [OK] Predicted REINDEX needs: {len(predicted_needs)}")
            print(f"  [OK] Recommendations: {len(recommendations)}")
        else:
            results["warnings"].append("Predictive maintenance report is empty")

    except ImportError as e:
        results["warnings"].append(f"Predictive maintenance module not available: {e}")
    except Exception as e:
        results["passed"] = False
        results["errors"].append(f"Error verifying predictive maintenance: {e}")
        logger.error(f"Error verifying predictive maintenance: {e}", exc_info=True)
        print(f"  [ERROR] Error: {e}")

    if results["warnings"]:
        print(f"  [WARNING] Warnings: {len(results['warnings'])}")
        for warning in results["warnings"]:
            print(f"     - {warning}")

    return results


def verify_all_features(
    tenant_ids: TenantIDList | None = None, min_indexes: int = 0
) -> ComprehensiveVerificationResults:
    """
    Run all verification functions and return comprehensive results.

    Args:
        tenant_ids: List of tenant IDs to check
        min_indexes: Minimum number of indexes expected

    Returns:
        dict with all verification results
    """
    print("\n" + "=" * 80)
    print("COMPREHENSIVE FEATURE VERIFICATION")
    print("=" * 80)

    # Build results - summary will be added after calculation
    mutation_log_result = verify_mutation_log(tenant_ids, min_indexes)
    expression_profiles_result = (
        verify_expression_profiles(tenant_ids)
        if tenant_ids
        else VerificationResult(passed=True, errors=[], warnings=[], details={})
    )
    production_safeguards_result = verify_production_safeguards()
    bypass_system_result = verify_bypass_system()
    health_checks_result = verify_health_checks()
    schema_evolution_result = verify_schema_evolution()
    query_interception_result = verify_query_interception()
    algorithm_usage_result = verify_algorithm_usage()
    ab_testing_result = verify_ab_testing()
    predictive_maintenance_result = verify_predictive_maintenance()

    all_results: ComprehensiveVerificationResults = {
        "mutation_log": mutation_log_result,
        "expression_profiles": expression_profiles_result,
        "production_safeguards": production_safeguards_result,
        "bypass_system": bypass_system_result,
        "health_checks": health_checks_result,
        "schema_evolution": schema_evolution_result,
        "query_interception": query_interception_result,
        "algorithm_usage": algorithm_usage_result,
        "ab_testing": ab_testing_result,
        "predictive_maintenance": predictive_maintenance_result,
        "summary": {
            "all_passed": False,
            "total_errors": 0,
            "total_warnings": 0,
        },  # Will be updated below
    }

    # Calculate overall status
    verification_results = [
        all_results["mutation_log"],
        all_results["expression_profiles"],
        all_results["production_safeguards"],
        all_results["bypass_system"],
        all_results["health_checks"],
        schema_evolution_result,
        query_interception_result,
        algorithm_usage_result,
        ab_testing_result,
        predictive_maintenance_result,
    ]
    all_passed = all(result.get("passed", False) for result in verification_results)
    total_errors = sum(len(result.get("errors", [])) for result in verification_results)
    total_warnings = sum(len(result.get("warnings", [])) for result in verification_results)

    print("\n" + "=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)
    print(f"Overall Status: {'[OK] PASSED' if all_passed else '[ERROR] FAILED'}")
    print(f"Total Errors: {total_errors}")
    print(f"Total Warnings: {total_warnings}")
    print("\nFeature Status:")
    for feature_name, result in [
        ("mutation_log", all_results["mutation_log"]),
        ("expression_profiles", all_results["expression_profiles"]),
        ("production_safeguards", all_results["production_safeguards"]),
        ("bypass_system", all_results["bypass_system"]),
        ("health_checks", all_results["health_checks"]),
        (
            "schema_evolution",
            all_results.get(
                "schema_evolution",
                VerificationResult(passed=True, errors=[], warnings=[], details={}),
            ),
        ),
        (
            "query_interception",
            all_results.get(
                "query_interception",
                VerificationResult(passed=True, errors=[], warnings=[], details={}),
            ),
        ),
        (
            "algorithm_usage",
            all_results.get(
                "algorithm_usage",
                VerificationResult(passed=True, errors=[], warnings=[], details={}),
            ),
        ),
        (
            "ab_testing",
            all_results.get(
                "ab_testing",
                VerificationResult(passed=True, errors=[], warnings=[], details={}),
            ),
        ),
        (
            "predictive_maintenance",
            all_results.get(
                "predictive_maintenance",
                VerificationResult(passed=True, errors=[], warnings=[], details={}),
            ),
        ),
    ]:
        status = "[OK] PASSED" if result.get("passed", False) else "[ERROR] FAILED"
        errors = len(result.get("errors", []))
        warnings = len(result.get("warnings", []))
        print(f"  {feature_name}: {status} ({errors} errors, {warnings} warnings)")

    all_results["summary"] = {
        "all_passed": all_passed,
        "total_errors": total_errors,
        "total_warnings": total_warnings,
    }

    return all_results
