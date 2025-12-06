"""Verification functions for comprehensive simulation testing

This module provides verification functions to test all product features
during comprehensive simulation runs.
"""

import json
import logging

from psycopg2.extras import RealDictCursor

from src.db import get_connection
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


def verify_mutation_log(tenant_ids: TenantIDList | None = None, min_indexes: int = 0) -> VerificationResult:
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

    results: VerificationResult = {
        'passed': True,
        'errors': [],
        'warnings': [],
        'details': {}
    }

    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                # Count CREATE_INDEX mutations
                if tenant_ids:
                    placeholders = ','.join(['%s'] * len(tenant_ids))
                    cursor.execute(f"""
                        SELECT COUNT(*) as count
                        FROM mutation_log
                        WHERE mutation_type = 'CREATE_INDEX'
                        AND tenant_id IN ({placeholders})
                    """, tenant_ids)
                else:
                    cursor.execute("""
                        SELECT COUNT(*) as count
                        FROM mutation_log
                        WHERE mutation_type = 'CREATE_INDEX'
                    """)

                result = cursor.fetchone()
                index_mutations = result['count'] if result else 0

                # Get sample mutations to verify details
                if tenant_ids:
                    placeholders = ','.join(['%s'] * len(tenant_ids))
                    cursor.execute(f"""
                        SELECT tenant_id, table_name, field_name, details_json, created_at
                        FROM mutation_log
                        WHERE mutation_type = 'CREATE_INDEX'
                        AND tenant_id IN ({placeholders})
                        ORDER BY created_at DESC
                        LIMIT 10
                    """, tenant_ids)
                else:
                    cursor.execute("""
                        SELECT tenant_id, table_name, field_name, details_json, created_at
                        FROM mutation_log
                        WHERE mutation_type = 'CREATE_INDEX'
                        ORDER BY created_at DESC
                        LIMIT 10
                    """)

                sample_mutations = cursor.fetchall()

                # Verify minimum count
                if index_mutations < min_indexes:
                    results['warnings'].append(
                        f"Expected at least {min_indexes} CREATE_INDEX mutations, found {index_mutations}"
                    )

                # Verify mutation details
                mutations_with_details = 0
                mutations_with_tenant = 0
                for mutation in sample_mutations:
                    if mutation['details_json']:
                        try:
                            details = json.loads(mutation['details_json']) if isinstance(mutation['details_json'], str) else mutation['details_json']
                            if 'queries' in details or 'build_cost' in details or 'query_cost' in details:
                                mutations_with_details += 1
                        except (json.JSONDecodeError, TypeError):
                            pass

                    if mutation['tenant_id'] is not None:
                        mutations_with_tenant += 1

                results['details'] = {
                    'total_index_mutations': index_mutations,
                    'sample_mutations_checked': len(sample_mutations),
                    'mutations_with_details': mutations_with_details,
                    'mutations_with_tenant': mutations_with_tenant
                }

                # Check if details are present
                if mutations_with_details < len(sample_mutations) * 0.8:  # 80% should have details
                    results['warnings'].append(
                        f"Only {mutations_with_details}/{len(sample_mutations)} mutations have complete details"
                    )

                # Check tenant awareness
                if mutations_with_tenant < len(sample_mutations) * 0.8:  # 80% should be tenant-aware
                    results['warnings'].append(
                        f"Only {mutations_with_tenant}/{len(sample_mutations)} mutations are tenant-aware"
                    )

                print(f"  [OK] Found {index_mutations} CREATE_INDEX mutations")
                print(f"  [OK] Verified {len(sample_mutations)} sample mutations")
                print(f"  [OK] {mutations_with_details}/{len(sample_mutations)} have complete details")
                print(f"  [OK] {mutations_with_tenant}/{len(sample_mutations)} are tenant-aware")

            finally:
                cursor.close()

    except Exception as e:
        results['passed'] = False
        results['errors'].append(f"Error verifying mutation log: {e}")
        logger.error(f"Error verifying mutation log: {e}", exc_info=True)
        print(f"  [ERROR] Error: {e}")

    if results['warnings']:
        print(f"  [WARNING] Warnings: {len(results['warnings'])}")
        for warning in results['warnings']:
            print(f"     - {warning}")

    if results['errors']:
        print(f"  [ERROR] Errors: {len(results['errors'])}")
        for error in results['errors']:
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

    results: VerificationResult = {
        'passed': True,
        'errors': [],
        'warnings': [],
        'details': {}
    }

    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                # Check expression profiles for each tenant
                tenants_with_profiles = 0
                total_fields_enabled = 0
                sample_tenants = tenant_ids[:min(5, len(tenant_ids))]  # Check first 5 tenants

                for tenant_id in sample_tenants:
                    # Check if tenant has expression profile entries
                    cursor.execute("""
                        SELECT COUNT(*) as count
                        FROM expression_profile
                        WHERE tenant_id = %s
                    """, (tenant_id,))
                    result = cursor.fetchone()
                    profile_count = result['count'] if result else 0

                    if profile_count > 0:
                        tenants_with_profiles += 1
                        total_fields_enabled += profile_count

                        # Check enabled fields
                        enabled_fields = get_enabled_fields(tenant_id)
                        if enabled_fields:
                            # Verify a sample field is enabled
                            # get_enabled_fields returns a list of dicts with table_name and field_name
                            if len(enabled_fields) > 0:
                                sample_field = enabled_fields[0]
                                sample_table = sample_field['table_name']
                                sample_field_name = sample_field['field_name']
                                is_enabled = is_field_enabled(tenant_id, sample_table, sample_field_name)
                                if not is_enabled:
                                    results['warnings'].append(
                                        f"Tenant {tenant_id}: Field {sample_table}.{sample_field_name} should be enabled but isn't"
                                    )

                results['details'] = {
                    'tenants_checked': len(sample_tenants),
                    'tenants_with_profiles': tenants_with_profiles,
                    'total_fields_enabled': total_fields_enabled,
                    'avg_fields_per_tenant': total_fields_enabled / len(sample_tenants) if sample_tenants else 0
                }

                # Verify all tenants have profiles
                if tenants_with_profiles < len(sample_tenants):
                    results['warnings'].append(
                        f"Only {tenants_with_profiles}/{len(sample_tenants)} tenants have expression profiles"
                    )

                print(f"  [OK] Checked {len(sample_tenants)} tenants")
                print(f"  [OK] {tenants_with_profiles} tenants have expression profiles")
                print(f"  [OK] Total {total_fields_enabled} fields enabled across tenants")

            finally:
                cursor.close()

    except Exception as e:
        results['passed'] = False
        results['errors'].append(f"Error verifying expression profiles: {e}")
        logger.error(f"Error verifying expression profiles: {e}", exc_info=True)
        print(f"  [ERROR] Error: {e}")

    if results['warnings']:
        print(f"  [WARNING] Warnings: {len(results['warnings'])}")
        for warning in results['warnings']:
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

    results: VerificationResult = {
        'passed': True,
        'errors': [],
        'warnings': [],
        'details': {}
    }

    try:
        # Check maintenance window
        try:
            from src.maintenance_window import (
                is_in_maintenance_window,
                is_maintenance_window_enabled,
            )
            maintenance_enabled = is_maintenance_window_enabled()
            in_window = is_in_maintenance_window()
            results['details']['maintenance_window'] = {
                'enabled': maintenance_enabled,
                'in_window': in_window
            }
            print(f"  [OK] Maintenance window: {'enabled' if maintenance_enabled else 'disabled'}")
            print(f"  [OK] Currently in window: {in_window}")
        except Exception as e:
            results['warnings'].append(f"Could not check maintenance window: {e}")

        # Check rate limiter
        try:
            from src.rate_limiter import check_index_creation_rate_limit
            allowed, retry_after = check_index_creation_rate_limit('test_table')
            results['details']['rate_limiter'] = {
                'allowed': allowed,
                'retry_after': retry_after
            }
            print(f"  [OK] Rate limiter: {'active' if not allowed or retry_after > 0 else 'available'}")
        except Exception as e:
            results['warnings'].append(f"Could not check rate limiter: {e}")

        # Check CPU throttle
        try:
            from src.cpu_throttle import should_throttle_index_creation
            throttle_result = should_throttle_index_creation()
            if isinstance(throttle_result, tuple) and len(throttle_result) >= 2:
                should_throttle = bool(throttle_result[0]) if isinstance(throttle_result[0], bool) else False
                reason = str(throttle_result[1]) if throttle_result[1] is not None else None
            else:
                should_throttle = False
                reason = None
            # Match VerificationDetails TypedDict requirement: dict[str, bool | str]
            cpu_throttle_dict: dict[str, bool | str] = {
                'should_throttle': should_throttle,
                'reason': reason if reason is not None else ''
            }
            details_dict = results.get('details', {})
            if isinstance(details_dict, dict):
                details_dict['cpu_throttle'] = cpu_throttle_dict
                results['details'] = details_dict
            print(f"  [OK] CPU throttle: {'active' if should_throttle else 'available'}")
            if reason:
                print(f"     Reason: {reason}")
        except Exception as e:
            results['warnings'].append(f"Could not check CPU throttle: {e}")

        # Check write performance
        try:
            from src.write_performance import can_create_index_for_table
            can_create, reason = can_create_index_for_table('contacts')
            results['details']['write_performance'] = {
                'can_create': can_create,
                'reason': reason
            }
            print(f"  [OK] Write performance check: {'passed' if can_create else 'blocked'}")
            if reason:
                print(f"     Reason: {reason}")
        except Exception as e:
            results['warnings'].append(f"Could not check write performance: {e}")

    except Exception as e:
        results['passed'] = False
        results['errors'].append(f"Error verifying production safeguards: {e}")
        logger.error(f"Error verifying production safeguards: {e}", exc_info=True)
        print(f"  [ERROR] Error: {e}")

    if results['warnings']:
        print(f"  [WARNING] Warnings: {len(results['warnings'])}")
        for warning in results['warnings']:
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

    results: VerificationResult = {
        'passed': True,
        'errors': [],
        'warnings': [],
        'details': {}
    }

    try:
        # Get system status
        status = get_system_status()

        results['details'] = {
            'system_enabled': status.get('summary', {}).get('system_enabled', False),
            'any_bypass_active': status.get('summary', {}).get('any_bypass_active', False),
            'features': status.get('features', {})
        }

        print(f"  [OK] System enabled: {results['details']['system_enabled']}")
        print(f"  [OK] Any bypass active: {results['details']['any_bypass_active']}")

        # Check feature statuses
        features = results['details'].get('features', {})
        for feature_name, feature_status in features.items():
            enabled = feature_status.get('enabled', False)
            bypassed = feature_status.get('bypassed', False)
            status_str = 'enabled' if enabled and not bypassed else 'bypassed' if bypassed else 'disabled'
            print(f"  [OK] {feature_name}: {status_str}")

    except Exception as e:
        results['passed'] = False
        results['errors'].append(f"Error verifying bypass system: {e}")
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

    results: VerificationResult = {
        'passed': True,
        'errors': [],
        'warnings': [],
        'details': {}
    }

    try:
        # Check database health
        try:
            db_health = check_database_health()
            # Convert TypedDict to dict format expected by VerificationDetails
            db_health_dict: dict[str, str | float | None] = {
                'status': db_health.get('status', 'unknown'),
                'latency_ms': db_health.get('latency_ms'),
                'error': db_health.get('error')
            }
            results['details']['database_health'] = db_health_dict
            db_status = db_health.get('status', 'unknown')
            print(f"  [OK] Database health: {db_status}")
        except Exception as e:
            results['warnings'].append(f"Could not check database health: {e}")

        # Check system health (comprehensive)
        try:
            system_health = comprehensive_health_check()
            # Convert TypedDict to dict format expected by VerificationDetails
            # Use JSONValue to allow all valid JSON types
            components_val = system_health.get('components', {})
            warnings_val = system_health.get('warnings', [])
            errors_val = system_health.get('errors', [])
            
            # Convert to JSONValue-compatible types
            # Explicitly cast to satisfy mypy's variance checking
            components_json: JSONValue = components_val if isinstance(components_val, dict) else {}  # type: ignore[assignment]
            warnings_json: JSONValue = warnings_val if isinstance(warnings_val, list) else []  # type: ignore[assignment]
            errors_json: JSONValue = errors_val if isinstance(errors_val, list) else []  # type: ignore[assignment]
            
            system_health_dict: dict[str, JSONValue] = {
                'timestamp': system_health.get('timestamp', 0.0),
                'overall_status': system_health.get('overall_status', 'unknown'),
                'message': system_health.get('message', ''),
                'components': components_json,
                'warnings': warnings_json,
                'errors': errors_json
            }
            results['details']['system_health'] = system_health_dict
            sys_status = system_health.get('overall_status', 'unknown')
            print(f"  [OK] System health: {sys_status}")
        except Exception as e:
            results['warnings'].append(f"Could not check system health: {e}")

    except Exception as e:
        results['passed'] = False
        results['errors'].append(f"Error verifying health checks: {e}")
        logger.error(f"Error verifying health checks: {e}", exc_info=True)
        print(f"  [ERROR] Error: {e}")

    if results['warnings']:
        print(f"  [WARNING] Warnings: {len(results['warnings'])}")
        for warning in results['warnings']:
            print(f"     - {warning}")

    return results


def verify_all_features(tenant_ids: TenantIDList | None = None, min_indexes: int = 0) -> ComprehensiveVerificationResults:
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
    expression_profiles_result = verify_expression_profiles(tenant_ids) if tenant_ids else VerificationResult(passed=True, errors=[], warnings=[], details={})
    production_safeguards_result = verify_production_safeguards()
    bypass_system_result = verify_bypass_system()
    health_checks_result = verify_health_checks()

    all_results: ComprehensiveVerificationResults = {
        'mutation_log': mutation_log_result,
        'expression_profiles': expression_profiles_result,
        'production_safeguards': production_safeguards_result,
        'bypass_system': bypass_system_result,
        'health_checks': health_checks_result,
        'summary': {'all_passed': False, 'total_errors': 0, 'total_warnings': 0}  # Will be updated below
    }

    # Calculate overall status
    verification_results = [
        all_results['mutation_log'],
        all_results['expression_profiles'],
        all_results['production_safeguards'],
        all_results['bypass_system'],
        all_results['health_checks']
    ]
    all_passed = all(result.get('passed', False) for result in verification_results)
    total_errors = sum(len(result.get('errors', [])) for result in verification_results)
    total_warnings = sum(len(result.get('warnings', [])) for result in verification_results)

    print("\n" + "=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)
    print(f"Overall Status: {'[OK] PASSED' if all_passed else '[ERROR] FAILED'}")
    print(f"Total Errors: {total_errors}")
    print(f"Total Warnings: {total_warnings}")
    print("\nFeature Status:")
    mutation_log_result = all_results['mutation_log']
    expression_profiles_result = all_results['expression_profiles']
    production_safeguards_result = all_results['production_safeguards']
    bypass_system_result = all_results['bypass_system']
    health_checks_result = all_results['health_checks']

    for feature_name, result in [
        ('mutation_log', mutation_log_result),
        ('expression_profiles', expression_profiles_result),
        ('production_safeguards', production_safeguards_result),
        ('bypass_system', bypass_system_result),
        ('health_checks', health_checks_result)
    ]:
        status = '[OK] PASSED' if result.get('passed', False) else '[ERROR] FAILED'
        errors = len(result.get('errors', []))
        warnings = len(result.get('warnings', []))
        print(f"  {feature_name}: {status} ({errors} errors, {warnings} warnings)")

    all_results['summary'] = {
        'all_passed': all_passed,
        'total_errors': total_errors,
        'total_warnings': total_warnings
    }

    return all_results

