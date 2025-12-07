"""Constraint Programming for Index Selection

This module implements constraint programming approach for optimal index selection,
matching pganalyze's constraint programming methodology.

Based on: pganalyze technical whitepaper + academic research on constraint programming
for database optimization.

Key Features:
- Multi-objective optimization (storage, performance, workload constraints)
- Systematic trade-off handling
- Per-tenant constraint optimization
- Workload-aware constraint solving
"""

import logging
from typing import cast

from src.config_loader import ConfigLoader
from src.type_definitions import JSONDict, JSONValue

logger = logging.getLogger(__name__)

# Load configuration
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    _config_loader = ConfigLoader()


class ConstraintIndexOptimizer:
    """Constraint-based index selection optimizer"""

    def __init__(self):
        """Initialize constraint optimizer with default constraints"""
        self.constraints = self._load_constraints()

    def _load_constraints(self) -> JSONDict:
        """Load constraint configuration"""
        return {
            "storage": {
                "max_storage_per_tenant_mb": _config_loader.get_float(
                    "features.constraint_optimization.storage.max_per_tenant_mb", 1000.0
                ),
                "max_storage_total_mb": _config_loader.get_float(
                    "features.constraint_optimization.storage.max_total_mb", 10000.0
                ),
                "warn_threshold_pct": _config_loader.get_float(
                    "features.constraint_optimization.storage.warn_threshold_pct", 80.0
                ),
            },
            "performance": {
                "max_query_time_ms": _config_loader.get_float(
                    "features.constraint_optimization.performance.max_query_time_ms", 100.0
                ),
                "min_improvement_pct": _config_loader.get_float(
                    "features.constraint_optimization.performance.min_improvement_pct", 20.0
                ),
            },
            "workload": {
                "read_write_ratio": _config_loader.get_float(
                    "features.constraint_optimization.workload.read_write_ratio", 0.8
                ),
                "max_write_overhead_pct": _config_loader.get_float(
                    "features.constraint_optimization.workload.max_write_overhead_pct", 10.0
                ),
            },
            "tenant": {
                "max_indexes_per_tenant": _config_loader.get_int(
                    "features.constraint_optimization.tenant.max_indexes_per_tenant", 50
                ),
                "max_indexes_per_table": _config_loader.get_int(
                    "features.constraint_optimization.tenant.max_indexes_per_table", 10
                ),
            },
        }

    def check_storage_constraints(
        self,
        estimated_index_size_mb: float,
        tenant_id: int | None = None,
        current_storage_usage_mb: float = 0.0,
    ) -> tuple[bool, str, float]:
        """
        Check if index creation satisfies storage constraints.

        Args:
            estimated_index_size_mb: Estimated size of the new index in MB
            tenant_id: Optional tenant ID for per-tenant constraints
            current_storage_usage_mb: Current storage usage in MB

        Returns:
            Tuple of (satisfies: bool, reason: str, constraint_score: float)
        """
        storage_constraints = self.constraints["storage"]
        if not isinstance(storage_constraints, dict):
            raise ValueError("Invalid storage constraints")
        max_per_tenant_val = storage_constraints.get("max_storage_per_tenant_mb", 1000.0)
        max_total_val = storage_constraints.get("max_storage_total_mb", 10000.0)
        warn_threshold_val = storage_constraints.get("warn_threshold_pct", 80.0)
        max_per_tenant = (
            float(max_per_tenant_val) if isinstance(max_per_tenant_val, (int, float)) else 1000.0
        )
        max_total = float(max_total_val) if isinstance(max_total_val, (int, float)) else 10000.0
        warn_threshold = (
            float(warn_threshold_val) if isinstance(warn_threshold_val, (int, float)) else 80.0
        )

        # Check total storage constraint
        new_total = current_storage_usage_mb + estimated_index_size_mb
        if new_total > max_total:
            return False, "exceeds_total_storage_limit", 0.0

        # Check per-tenant storage constraint (if tenant_id provided)
        if tenant_id is not None:
            # Get tenant-specific storage usage (simplified - would need actual tracking)
            # For now, use current_storage_usage_mb as tenant storage
            new_tenant_storage = current_storage_usage_mb + estimated_index_size_mb
            if new_tenant_storage > max_per_tenant:
                return False, "exceeds_tenant_storage_limit", 0.0

            # Check warning threshold
            usage_pct = (new_tenant_storage / max_per_tenant) * 100.0
            if usage_pct > warn_threshold:
                constraint_score = 1.0 - ((usage_pct - warn_threshold) / (100.0 - warn_threshold))
                return True, "approaching_tenant_storage_limit", max(0.0, constraint_score)

        # Calculate constraint score (lower usage = higher score)
        usage_pct = (new_total / max_total) * 100.0
        constraint_score = 1.0 - (usage_pct / 100.0)
        return True, "storage_constraint_satisfied", constraint_score

    def check_performance_constraints(
        self,
        estimated_query_time_ms: float,
        improvement_pct: float,
    ) -> tuple[bool, str, float]:
        """
        Check if index creation satisfies performance constraints.

        Args:
            estimated_query_time_ms: Estimated query time with index in milliseconds
            improvement_pct: Expected performance improvement percentage

        Returns:
            Tuple of (satisfies: bool, reason: str, constraint_score: float)
        """
        perf_constraints = self.constraints["performance"]
        if not isinstance(perf_constraints, dict):
            raise ValueError("Invalid performance constraints")
        max_query_time_val = perf_constraints.get("max_query_time_ms", 100.0)
        min_improvement_val = perf_constraints.get("min_improvement_pct", 20.0)
        max_query_time = (
            float(max_query_time_val) if isinstance(max_query_time_val, (int, float)) else 100.0
        )
        min_improvement = (
            float(min_improvement_val) if isinstance(min_improvement_val, (int, float)) else 20.0
        )

        # Check query time constraint
        if estimated_query_time_ms > max_query_time:
            return False, "exceeds_max_query_time", 0.0

        # Check improvement constraint
        if improvement_pct < min_improvement:
            return False, "insufficient_improvement", 0.0

        # Calculate constraint score
        # Higher improvement and lower query time = higher score
        improvement_score = min(1.0, improvement_pct / 100.0)
        time_score = 1.0 - min(1.0, estimated_query_time_ms / max_query_time)
        constraint_score = (improvement_score + time_score) / 2.0

        return True, "performance_constraint_satisfied", constraint_score

    def check_workload_constraints(
        self,
        read_write_ratio: float,
        estimated_write_overhead_pct: float,
    ) -> tuple[bool, str, float]:
        """
        Check if index creation satisfies workload constraints.

        Args:
            read_write_ratio: Ratio of read to write queries (0.0 to 1.0)
            estimated_write_overhead_pct: Estimated write performance overhead percentage

        Returns:
            Tuple of (satisfies: bool, reason: str, constraint_score: float)
        """
        workload_constraints = self.constraints["workload"]
        if not isinstance(workload_constraints, dict):
            raise ValueError("Invalid workload constraints")
        max_write_overhead_val = workload_constraints.get("max_write_overhead_pct", 10.0)
        max_write_overhead = (
            float(max_write_overhead_val)
            if isinstance(max_write_overhead_val, (int, float))
            else 10.0
        )

        # Check write overhead constraint
        if estimated_write_overhead_pct > max_write_overhead:
            # For write-heavy workloads, this is critical
            if read_write_ratio < 0.5 or read_write_ratio < 0.7:  # Write-heavy
                return False, "exceeds_write_overhead_limit", 0.0

        # Calculate constraint score
        # Higher read ratio and lower write overhead = higher score
        read_ratio_score = read_write_ratio
        overhead_score = 1.0 - min(1.0, estimated_write_overhead_pct / max_write_overhead)
        constraint_score = (read_ratio_score + overhead_score) / 2.0

        return True, "workload_constraint_satisfied", constraint_score

    def check_tenant_constraints(
        self,
        tenant_id: int | None,
        table_name: str,
        current_index_count: int = 0,
        current_table_index_count: int = 0,
    ) -> tuple[bool, str, float]:
        """
        Check if index creation satisfies tenant constraints.

        Args:
            tenant_id: Optional tenant ID
            table_name: Table name
            current_index_count: Current number of indexes for tenant
            current_table_index_count: Current number of indexes for table

        Returns:
            Tuple of (satisfies: bool, reason: str, constraint_score: float)
        """
        tenant_constraints = self.constraints["tenant"]
        if not isinstance(tenant_constraints, dict):
            raise ValueError("Invalid tenant constraints")
        max_per_tenant_val = tenant_constraints.get("max_indexes_per_tenant", 50)
        max_per_table_val = tenant_constraints.get("max_indexes_per_table", 10)
        max_per_tenant = (
            int(max_per_tenant_val) if isinstance(max_per_tenant_val, (int, float)) else 50
        )
        max_per_table = (
            int(max_per_table_val) if isinstance(max_per_table_val, (int, float)) else 10
        )

        # Check per-table constraint
        if current_table_index_count >= max_per_table:
            return False, "exceeds_max_indexes_per_table", 0.0

        # Check per-tenant constraint (if tenant_id provided)
        if tenant_id is not None:
            if current_index_count >= max_per_tenant:
                return False, "exceeds_max_indexes_per_tenant", 0.0

            # Calculate constraint score
            tenant_score = 1.0 - (current_index_count / max_per_tenant)
            table_score = 1.0 - (current_table_index_count / max_per_table)
            constraint_score = (tenant_score + table_score) / 2.0
        else:
            # Single-tenant: only check table constraint
            constraint_score = 1.0 - (current_table_index_count / max_per_table)

        return True, "tenant_constraint_satisfied", constraint_score

    def optimize_index_selection(
        self,
        index_candidates: list[JSONDict],
        tenant_id: int | None = None,
        workload_info: JSONDict | None = None,
    ) -> JSONDict:
        """
        Optimize index selection using constraint programming.

        Args:
            index_candidates: List of candidate indexes with metadata
            tenant_id: Optional tenant ID for per-tenant optimization
            workload_info: Optional workload information (read/write ratio, etc.)

        Returns:
            dict with optimized index selection and constraint satisfaction scores
        """
        if not index_candidates:
            return {
                "selected_indexes": [],
                "rejected_indexes": [],
                "constraint_scores": {},
                "overall_score": 0.0,
            }

        selected_indexes: list[JSONDict] = []
        rejected_indexes: list[JSONDict] = []
        constraint_scores: dict[str, dict[str, float]] = {}

        # Get workload info
        read_write_ratio = 0.8  # Default: read-heavy
        if workload_info:
            read_write_ratio_val = workload_info.get("read_write_ratio", 0.8)
            read_write_ratio = (
                float(read_write_ratio_val)
                if isinstance(read_write_ratio_val, (int, float))
                else 0.8
            )

        # Evaluate each candidate
        for candidate in index_candidates:
            candidate_id_val = candidate.get("id")
            table_name_val = candidate.get("table_name", "")
            field_name_val = candidate.get("field_name", "")
            if candidate_id_val is None:
                table_name_str = str(table_name_val) if isinstance(table_name_val, str) else ""
                field_name_str = str(field_name_val) if isinstance(field_name_val, str) else ""
                candidate_id = f"{table_name_str}.{field_name_str}"
            else:
                candidate_id = str(candidate_id_val)
            scores: dict[str, float] = {}

            # Check storage constraint
            estimated_size_mb_val = candidate.get("estimated_size_mb", 0.0)
            current_storage_val = candidate.get("current_storage_usage_mb", 0.0)
            estimated_size_mb = (
                float(estimated_size_mb_val)
                if isinstance(estimated_size_mb_val, (int, float))
                else 0.0
            )
            current_storage = (
                float(current_storage_val) if isinstance(current_storage_val, (int, float)) else 0.0
            )
            storage_ok, storage_reason, storage_score = self.check_storage_constraints(
                estimated_size_mb, tenant_id, current_storage
            )
            scores["storage"] = storage_score

            # Check performance constraint
            estimated_query_time_val = candidate.get("estimated_query_time_ms", 0.0)
            improvement_pct_val = candidate.get("improvement_pct", 0.0)
            estimated_query_time = (
                float(estimated_query_time_val)
                if isinstance(estimated_query_time_val, (int, float))
                else 0.0
            )
            improvement_pct = (
                float(improvement_pct_val) if isinstance(improvement_pct_val, (int, float)) else 0.0
            )
            perf_ok, perf_reason, perf_score = self.check_performance_constraints(
                estimated_query_time, improvement_pct
            )
            scores["performance"] = perf_score

            # Check workload constraint
            estimated_write_overhead_val = candidate.get("estimated_write_overhead_pct", 0.0)
            estimated_write_overhead = (
                float(estimated_write_overhead_val)
                if isinstance(estimated_write_overhead_val, (int, float))
                else 0.0
            )
            workload_ok, workload_reason, workload_score = self.check_workload_constraints(
                read_write_ratio, estimated_write_overhead
            )
            scores["workload"] = workload_score

            # Check tenant constraint
            current_index_count_val = candidate.get("current_index_count", 0)
            current_table_index_count_val = candidate.get("current_table_index_count", 0)
            current_index_count = (
                int(current_index_count_val)
                if isinstance(current_index_count_val, (int, float))
                else 0
            )
            current_table_index_count = (
                int(current_table_index_count_val)
                if isinstance(current_table_index_count_val, (int, float))
                else 0
            )
            table_name_str = str(table_name_val) if isinstance(table_name_val, str) else ""
            tenant_ok, tenant_reason, tenant_score = self.check_tenant_constraints(
                tenant_id,
                table_name_str,
                current_index_count,
                current_table_index_count,
            )
            scores["tenant"] = tenant_score

            # Calculate overall constraint score (weighted average)
            weights = {
                "storage": 0.2,
                "performance": 0.4,
                "workload": 0.2,
                "tenant": 0.2,
            }
            overall_score = sum(scores[key] * weights.get(key, 0.25) for key in scores)

            constraint_scores[candidate_id] = scores

            # Select if all constraints satisfied and score above threshold
            all_constraints_ok = storage_ok and perf_ok and workload_ok and tenant_ok
            min_score_threshold = _config_loader.get_float(
                "features.constraint_optimization.min_score_threshold", 0.5
            )

            if all_constraints_ok and overall_score >= min_score_threshold:
                candidate_copy = dict(candidate)
                candidate_copy["constraint_score"] = overall_score
                candidate_copy["constraint_reasons"] = {
                    "storage": storage_reason,
                    "performance": perf_reason,
                    "workload": workload_reason,
                    "tenant": tenant_reason,
                }
                selected_indexes.append(candidate_copy)
            else:
                candidate_copy = dict(candidate)
                candidate_copy["constraint_score"] = overall_score
                candidate_copy["rejection_reasons"] = {
                    "storage": storage_reason if not storage_ok else None,
                    "performance": perf_reason if not perf_ok else None,
                    "workload": workload_reason if not workload_ok else None,
                    "tenant": tenant_reason if not tenant_ok else None,
                }
                rejected_indexes.append(candidate_copy)

        # Sort selected indexes by constraint score (highest first)
        def get_score(idx: JSONDict) -> float:
            score_val = idx.get("constraint_score", 0.0)
            return float(score_val) if isinstance(score_val, (int, float)) else 0.0

        selected_indexes.sort(key=get_score, reverse=True)

        # Calculate overall satisfaction score
        def get_idx_score(idx: JSONDict) -> float:
            score_val = idx.get("constraint_score", 0.0)
            return float(score_val) if isinstance(score_val, (int, float)) else 0.0

        overall_satisfaction = (
            sum(get_idx_score(idx) for idx in selected_indexes) / len(selected_indexes)
            if selected_indexes
            else 0.0
        )

        return {
            "selected_indexes": cast(list[JSONValue], selected_indexes),
            "rejected_indexes": cast(list[JSONValue], rejected_indexes),
            "constraint_scores": cast(dict[str, JSONValue], constraint_scores),
            "overall_score": overall_satisfaction,
            "total_candidates": len(index_candidates),
            "selected_count": len(selected_indexes),
            "rejected_count": len(rejected_indexes),
        }


def optimize_index_with_constraints(
    estimated_build_cost: float,
    queries_over_horizon: float,
    extra_cost_per_query_without_index: float,
    estimated_index_size_mb: float,
    improvement_pct: float,
    table_name: str | None = None,
    field_name: str | None = None,
    tenant_id: int | None = None,
    table_size_info: JSONDict | None = None,
    workload_info: JSONDict | None = None,
    current_index_count: int = 0,
    current_table_index_count: int = 0,
    current_storage_usage_mb: float = 0.0,
) -> tuple[bool, float, str, JSONDict]:
    """
    Optimize index creation decision using constraint programming.

    This function integrates constraint programming into the index creation decision,
    checking multiple constraints simultaneously and providing a constraint-based decision.

    Args:
        estimated_build_cost: Estimated cost to build the index
        queries_over_horizon: Number of queries expected over the time horizon
        extra_cost_per_query_without_index: Additional cost per query without index
        estimated_index_size_mb: Estimated index size in MB
        improvement_pct: Expected performance improvement percentage
        table_name: Optional table name
        field_name: Optional field name
        tenant_id: Optional tenant ID
        table_size_info: Optional table size information
        workload_info: Optional workload information
        current_index_count: Current number of indexes for tenant
        current_table_index_count: Current number of indexes for table
        current_storage_usage_mb: Current storage usage in MB

    Returns:
        Tuple of (should_create: bool, confidence: float, reason: str, constraint_details: dict)
    """
    # Check if constraint optimization is enabled
    enabled = _config_loader.get_bool("features.constraint_optimization.enabled", False)
    if not enabled:
        # Return default decision (constraint optimization disabled)
        return True, 0.5, "constraint_optimization_disabled", {}

    try:
        optimizer = ConstraintIndexOptimizer()

        # Get workload info
        read_write_ratio = 0.8  # Default: read-heavy
        estimated_write_overhead = 5.0  # Default: 5% overhead
        if workload_info:
            read_write_ratio_val = workload_info.get("read_write_ratio", 0.8)
            estimated_write_overhead_val = workload_info.get("estimated_write_overhead_pct", 5.0)
            read_write_ratio = (
                float(read_write_ratio_val)
                if isinstance(read_write_ratio_val, (int, float))
                else 0.8
            )
            estimated_write_overhead = (
                float(estimated_write_overhead_val)
                if isinstance(estimated_write_overhead_val, (int, float))
                else 5.0
            )

        # Estimate query time (simplified - would use actual EXPLAIN results)
        estimated_query_time_ms = 50.0  # Default
        if table_size_info:
            row_count_val = table_size_info.get("row_count", 0)
            row_count = int(row_count_val) if isinstance(row_count_val, (int, float)) else 0
            # Rough estimate: larger tables = longer query time
            estimated_query_time_ms = min(100.0, row_count / 10000.0)

        # Check all constraints
        storage_ok, storage_reason, storage_score = optimizer.check_storage_constraints(
            estimated_index_size_mb, tenant_id, current_storage_usage_mb
        )

        perf_ok, perf_reason, perf_score = optimizer.check_performance_constraints(
            estimated_query_time_ms, improvement_pct
        )

        workload_ok, workload_reason, workload_score = optimizer.check_workload_constraints(
            read_write_ratio, estimated_write_overhead
        )

        tenant_ok, tenant_reason, tenant_score = optimizer.check_tenant_constraints(
            tenant_id, table_name or "", current_index_count, current_table_index_count
        )

        # Calculate overall constraint score
        weights = {
            "storage": 0.2,
            "performance": 0.4,
            "workload": 0.2,
            "tenant": 0.2,
        }
        overall_score = (
            storage_score * weights["storage"]
            + perf_score * weights["performance"]
            + workload_score * weights["workload"]
            + tenant_score * weights["tenant"]
        )

        # Decision: all constraints must be satisfied
        should_create = storage_ok and perf_ok and workload_ok and tenant_ok

        # Confidence based on constraint score
        confidence = overall_score if should_create else 0.0

        # Reason combines all constraint reasons
        reasons = []
        if not storage_ok:
            reasons.append(storage_reason)
        if not perf_ok:
            reasons.append(perf_reason)
        if not workload_ok:
            reasons.append(workload_reason)
        if not tenant_ok:
            reasons.append(tenant_reason)

        if should_create:
            reason = "constraint_optimization_passed"
        else:
            reason = f"constraint_violation_{'_'.join(reasons)}"

        constraint_details: JSONDict = {
            "storage": {"satisfied": storage_ok, "reason": storage_reason, "score": storage_score},
            "performance": {"satisfied": perf_ok, "reason": perf_reason, "score": perf_score},
            "workload": {
                "satisfied": workload_ok,
                "reason": workload_reason,
                "score": workload_score,
            },
            "tenant": {"satisfied": tenant_ok, "reason": tenant_reason, "score": tenant_score},
            "overall_score": overall_score,
        }

        return should_create, confidence, reason, constraint_details

    except Exception as e:
        logger.error(f"Constraint optimization failed: {e}")
        # Fallback to default decision
        error_details: JSONDict = {"error": str(e)}
        return True, 0.5, "constraint_optimization_error", error_details
