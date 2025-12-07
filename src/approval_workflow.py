"""Approval workflow for index creation (backend)"""

import logging
from typing import Any

from psycopg2.extras import RealDictCursor

from src.config_loader import ConfigLoader
from src.db import get_connection

logger = logging.getLogger(__name__)

# Load config
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    _config_loader = ConfigLoader()


def is_approval_workflow_enabled() -> bool:
    """Check if approval workflow is enabled"""
    return _config_loader.get_bool("features.approval_workflow.enabled", False)


def get_approval_config() -> dict[str, Any]:
    """Get approval workflow configuration"""
    return {
        "enabled": is_approval_workflow_enabled(),
        "require_approval": _config_loader.get_bool(
            "features.approval_workflow.require_approval", False
        ),
        "auto_approve_threshold": _config_loader.get_float(
            "features.approval_workflow.auto_approve_threshold", 0.9
        ),  # Auto-approve if confidence > 90%
        "notification_enabled": _config_loader.get_bool(
            "features.approval_workflow.notification_enabled", False
        ),
    }


def create_approval_request(
    index_name: str,
    table_name: str,
    field_name: str,
    index_sql: str,
    reason: str,
    confidence: float,
    tenant_id: int | None = None,
) -> dict[str, Any]:
    """
    Create an approval request for index creation.

    Args:
        index_name: Name of the index
        table_name: Table name
        field_name: Field name
        index_sql: SQL for creating the index
        reason: Reason for index creation
        confidence: Confidence score (0.0-1.0)
        tenant_id: Tenant ID (optional)

    Returns:
        dict with approval request info
    """
    if not is_approval_workflow_enabled():
        return {"approved": True, "reason": "approval_workflow_disabled"}

    config = get_approval_config()

    # Auto-approve if confidence is high enough
    if confidence >= config.get("auto_approve_threshold", 0.9):
        return {
            "approved": True,
            "reason": f"auto_approved_high_confidence_{confidence:.2f}",
            "confidence": confidence,
        }

    # Check if approval is required
    if not config.get("require_approval", False):
        return {"approved": True, "reason": "approval_not_required"}

    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                # Ensure approval_requests table exists
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS approval_requests (
                        id SERIAL PRIMARY KEY,
                        index_name VARCHAR(255) NOT NULL,
                        table_name VARCHAR(255) NOT NULL,
                        field_name VARCHAR(255) NOT NULL,
                        index_sql TEXT NOT NULL,
                        reason TEXT,
                        confidence FLOAT,
                        tenant_id INTEGER,
                        status VARCHAR(50) DEFAULT 'pending',
                        requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        approved_at TIMESTAMP,
                        approved_by VARCHAR(255),
                        rejected_at TIMESTAMP,
                        rejected_by VARCHAR(255),
                        rejection_reason TEXT
                    )
                    """
                )

                # Create approval request
                cursor.execute(
                    """
                    INSERT INTO approval_requests (
                        index_name, table_name, field_name, index_sql,
                        reason, confidence, tenant_id, status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
                    RETURNING id, requested_at
                    """,
                    (index_name, table_name, field_name, index_sql, reason, confidence, tenant_id),
                )

                result = cursor.fetchone()
                request_id = result["id"] if result else None
                requested_at = result["requested_at"] if result else None

                conn.commit()

                # Send notification if enabled
                if config.get("notification_enabled", False) and request_id is not None:
                    try:
                        if isinstance(request_id, (int, str)):
                            request_id_int = int(request_id)
                            _send_approval_notification(
                                request_id_int, index_name, table_name, confidence
                            )
                    except Exception as e:
                        logger.debug(f"Could not send approval notification: {e}")

                return {
                    "approved": False,
                    "request_id": request_id,
                    "status": "pending",
                    "requested_at": requested_at.isoformat() if requested_at else None,
                    "reason": "awaiting_approval",
                }

            except Exception as e:
                conn.rollback()
                logger.error(f"Failed to create approval request: {e}")
                # Fall back to auto-approve on error
                return {"approved": True, "reason": "approval_system_error"}
            finally:
                cursor.close()

    except Exception as e:
        logger.error(f"Failed to create approval request: {e}")
        # Fall back to auto-approve on error
        return {"approved": True, "reason": "approval_system_error"}


def approve_index_creation(request_id: int, approved_by: str) -> bool:
    """
    Approve an index creation request.

    Args:
        request_id: Approval request ID
        approved_by: User who approved

    Returns:
        True if successful
    """
    if not is_approval_workflow_enabled():
        return False

    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    UPDATE approval_requests
                    SET status = 'approved',
                        approved_at = CURRENT_TIMESTAMP,
                        approved_by = %s
                    WHERE id = %s
                      AND status = 'pending'
                    """,
                    (approved_by, request_id),
                )

                if cursor.rowcount > 0:
                    conn.commit()
                    logger.info(f"Index creation request {request_id} approved by {approved_by}")
                    return True
                else:
                    conn.rollback()
                    return False

            except Exception as e:
                conn.rollback()
                logger.error(f"Failed to approve request {request_id}: {e}")
                return False
            finally:
                cursor.close()

    except Exception as e:
        logger.error(f"Failed to approve request {request_id}: {e}")
        return False


def reject_index_creation(request_id: int, rejected_by: str, reason: str) -> bool:
    """
    Reject an index creation request.

    Args:
        request_id: Approval request ID
        rejected_by: User who rejected
        reason: Rejection reason

    Returns:
        True if successful
    """
    if not is_approval_workflow_enabled():
        return False

    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    UPDATE approval_requests
                    SET status = 'rejected',
                        rejected_at = CURRENT_TIMESTAMP,
                        rejected_by = %s,
                        rejection_reason = %s
                    WHERE id = %s
                      AND status = 'pending'
                    """,
                    (rejected_by, reason, request_id),
                )

                if cursor.rowcount > 0:
                    conn.commit()
                    logger.info(
                        f"Index creation request {request_id} rejected by {rejected_by}: {reason}"
                    )
                    return True
                else:
                    conn.rollback()
                    return False

            except Exception as e:
                conn.rollback()
                logger.error(f"Failed to reject request {request_id}: {e}")
                return False
            finally:
                cursor.close()

    except Exception as e:
        logger.error(f"Failed to reject request {request_id}: {e}")
        return False


def get_pending_approvals(tenant_id: int | None = None) -> list[dict[str, Any]]:
    """
    Get list of pending approval requests.

    Args:
        tenant_id: Tenant ID (None = all tenants)

    Returns:
        List of pending approval requests
    """
    if not is_approval_workflow_enabled():
        return []

    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                if tenant_id:
                    cursor.execute(
                        """
                        SELECT *
                        FROM approval_requests
                        WHERE status = 'pending'
                          AND tenant_id = %s
                        ORDER BY requested_at DESC
                        """,
                        (tenant_id,),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT *
                        FROM approval_requests
                        WHERE status = 'pending'
                        ORDER BY requested_at DESC
                        """
                    )

                results = cursor.fetchall()
                return [dict(row) for row in results]

            finally:
                cursor.close()

    except Exception as e:
        logger.error(f"Failed to get pending approvals: {e}")
        return []


def check_approval_status(index_name: str) -> dict[str, Any] | None:
    """
    Check approval status for an index.

    Args:
        index_name: Index name

    Returns:
        dict with approval status or None if not found
    """
    if not is_approval_workflow_enabled():
        return None

    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cursor.execute(
                    """
                    SELECT *
                    FROM approval_requests
                    WHERE index_name = %s
                    ORDER BY requested_at DESC
                    LIMIT 1
                    """,
                    (index_name,),
                )

                result = cursor.fetchone()
                if result:
                    return dict(result)

            finally:
                cursor.close()

    except Exception as e:
        logger.debug(f"Could not check approval status for {index_name}: {e}")

    return None


def _send_approval_notification(
    request_id: int, index_name: str, table_name: str, confidence: float
):
    """
    Send approval notification via monitoring adapter.

    Args:
        request_id: Request ID
        index_name: Index name
        table_name: Table name
        confidence: Confidence score
    """
    # Log to application logger
    notification_message = (
        f"Approval request {request_id} for index {index_name} "
        f"on {table_name} (confidence: {confidence:.2f})"
    )
    logger.info(f"Approval notification: {notification_message}")

    # Send via monitoring adapter (if configured)
    try:
        from src.monitoring import get_monitoring

        monitoring = get_monitoring()
        alert_level = "info" if confidence >= 0.9 else "warning"
        monitoring.alert(
            alert_level,
            notification_message,
            metric="approval_request",
            value=confidence,
        )
    except Exception as e:
        # Don't fail if monitoring adapter not available
        logger.debug(f"Could not send approval notification via monitoring adapter: {e}")

    # Also log to audit trail
    try:
        from src.audit import log_audit_event

        log_audit_event(
            "APPROVAL_REQUEST",
            table_name=table_name,
            details={
                "request_id": request_id,
                "index_name": index_name,
                "confidence": confidence,
                "action": "approval_request_created",
            },
            severity="info",
        )
    except Exception as e:
        logger.debug(f"Could not log approval request to audit trail: {e}")
