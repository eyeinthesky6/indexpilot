"""Schedule index creation to spread CPU load"""

import logging
import time
from datetime import datetime, timedelta

from src.cpu_throttle import should_throttle_index_creation
from src.rollback import is_system_enabled
from src.type_definitions import JSONDict

logger = logging.getLogger(__name__)


class IndexScheduler:
    """Schedule index creation to avoid CPU spikes"""

    def __init__(self, max_indexes_per_hour=5, preferred_hours=None):
        """
        Initialize scheduler.

        Args:
            max_indexes_per_hour: Maximum indexes to create per hour
            preferred_hours: List of preferred hours (0-23) for index creation
                           (e.g., [2, 3, 4] for 2-4 AM)
        """
        self.max_indexes_per_hour = max_indexes_per_hour
        self.preferred_hours = preferred_hours or list(range(2, 6))  # Default: 2-6 AM
        self.pending_indexes = []
        self.created_this_hour = 0
        self.last_hour_reset = datetime.now().replace(minute=0, second=0, microsecond=0)

    def is_preferred_time(self):
        """Check if current time is in preferred hours for index creation"""
        current_hour = datetime.now().hour
        return current_hour in self.preferred_hours

    def can_create_index_now(self):
        """Check if we can create an index now (rate limiting)"""
        # Reset counter if new hour
        now = datetime.now()
        if now >= self.last_hour_reset + timedelta(hours=1):
            self.created_this_hour = 0
            self.last_hour_reset = now.replace(minute=0, second=0, microsecond=0)

        # Check rate limit
        if self.created_this_hour >= self.max_indexes_per_hour:
            return (
                False,
                f"Rate limit: {self.created_this_hour}/{self.max_indexes_per_hour} indexes this hour",
            )

        # Check CPU throttling
        should_throttle, reason, _wait_seconds = should_throttle_index_creation()
        if should_throttle:
            return False, f"CPU throttled: {reason}"

        # Prefer off-peak hours
        if not self.is_preferred_time():
            # Allow during non-preferred hours, but log it
            logger.info(f"Creating index outside preferred hours (current: {datetime.now().hour})")

        return True, None

    def schedule_index_creation(self, indexes_to_create):
        """
        Schedule index creation with rate limiting and CPU awareness.

        Args:
            indexes_to_create: List of index creation tasks

        Returns:
            List of indexes actually created
        """
        if not is_system_enabled():
            logger.info("Index scheduling skipped: system is disabled")
            return []

        created = []
        skipped = []

        for index_task in indexes_to_create:
            can_create, reason = self.can_create_index_now()

            if not can_create:
                logger.info(f"Skipping index creation: {reason}")
                skipped.append({"index": index_task, "reason": reason})
                continue

            try:
                # Create index (this will also check CPU throttling)
                # Note: This is a simplified version - in production, you'd call
                # the actual index creation function
                logger.info(f"Creating scheduled index: {index_task}")
                self.created_this_hour += 1
                created.append(index_task)

                # Small delay between indexes to avoid CPU spikes
                time.sleep(5.0)
            except Exception as e:
                logger.error(f"Failed to create scheduled index {index_task}: {e}")
                skipped.append({"index": index_task, "reason": f"creation_failed: {e}"})

        return created, skipped


def create_indexes_with_scheduling(
    time_window_hours=24, min_query_threshold=100, max_per_batch=3, delay_between_batches=300
):
    """
    Create indexes with scheduling to spread CPU load.

    Args:
        time_window_hours: Time window for query analysis
        min_query_threshold: Minimum queries to consider
        max_per_batch: Maximum indexes to create in one batch
        delay_between_batches: Delay between batches (seconds)

    Returns:
        Summary of created/skipped indexes
    """
    if not is_system_enabled():
        logger.info("Index creation skipped: system is disabled")
        return {"created": [], "skipped": []}

    # Analyze which indexes should be created
    from src.auto_indexer import (
        estimate_build_cost,
        estimate_query_cost_without_index,
        should_create_index,
    )
    from src.stats import get_field_usage_stats, get_table_row_count

    field_stats = get_field_usage_stats(time_window_hours)

    indexes_to_create = []
    for stat in field_stats:
        if stat["total_queries"] < min_query_threshold:
            continue

        table_name = stat["table_name"]
        field_name = stat["field_name"]
        row_count = get_table_row_count(table_name)

        # Get table size info for enhanced decision making
        from src.auto_indexer import get_field_selectivity
        from src.stats import get_table_size_info

        table_size_info = get_table_size_info(table_name)
        field_selectivity = get_field_selectivity(table_name, field_name)

        # Use standard index type for initial estimation
        build_cost = estimate_build_cost(table_name, field_name, row_count, index_type="standard")
        query_cost = estimate_query_cost_without_index(
            table_name, field_name, row_count, use_real_plans=True
        )

        should_create, confidence, reason = should_create_index(
            build_cost, stat["total_queries"], query_cost, table_size_info, field_selectivity
        )

        if should_create:
            indexes_to_create.append(
                {
                    "table": table_name,
                    "field": field_name,
                    "queries": stat["total_queries"],
                    "confidence": confidence,
                }
            )

    if not indexes_to_create:
        logger.info("No indexes to create")
        return {"created": [], "skipped": []}

    logger.info(f"Found {len(indexes_to_create)} indexes to create, scheduling in batches...")

    # Create indexes in batches
    scheduler = IndexScheduler(max_indexes_per_hour=5)
    all_created: list[JSONDict] = []
    all_skipped: list[JSONDict] = []

    for i in range(0, len(indexes_to_create), max_per_batch):
        batch = indexes_to_create[i : i + max_per_batch]
        logger.info(f"Processing batch {i // max_per_batch + 1} ({len(batch)} indexes)...")

        # Check if we can create indexes now
        can_create, reason = scheduler.can_create_index_now()
        if not can_create:
            logger.info(f"Batch delayed: {reason}")
            all_skipped.extend([{"index": idx, "reason": reason} for idx in batch])
            continue

        # Create indexes in this batch
        for index_task in batch:
            try:
                # Use the actual index creation function from lock_manager
                from src.auto_indexer import create_smart_index, get_optimization_strategy
                from src.lock_manager import create_index_with_lock_management
                from src.query_patterns import detect_query_patterns
                from src.stats import get_table_row_count, get_table_size_info

                table_name = index_task["table"]
                field_name = index_task["field"]

                # Get table metadata for smart index creation
                row_count = get_table_row_count(table_name)
                table_size_info = get_table_size_info(table_name)
                query_patterns = detect_query_patterns(table_name, field_name)
                strategy = get_optimization_strategy(table_name, row_count, table_size_info)

                # Create smart index SQL
                index_sql, index_name, _index_type = create_smart_index(
                    table_name, field_name, row_count, query_patterns, strategy
                )

                # Create index with lock management and CPU throttling
                success = create_index_with_lock_management(
                    table_name, field_name, index_sql, timeout=300, respect_cpu_throttle=True
                )

                if success:
                    all_created.append(
                        {
                            "table": table_name,
                            "field": field_name,
                            "index_name": index_name,
                            "queries": index_task.get("queries", 0),
                        }
                    )
                    logger.info(f"Successfully created scheduled index: {index_name}")
                else:
                    all_skipped.append({"index": index_task, "reason": "cpu_throttled_or_failed"})
            except Exception as e:
                logger.error(f"Failed to create index in batch: {e}")
                all_skipped.append({"index": index_task, "reason": f"creation_failed: {e}"})

        # Delay between batches
        if i + max_per_batch < len(indexes_to_create):
            logger.info(f"Waiting {delay_between_batches}s before next batch...")
            time.sleep(delay_between_batches)

    return {
        "created": all_created,
        "skipped": all_skipped,
        "total_candidates": len(indexes_to_create),
    }
