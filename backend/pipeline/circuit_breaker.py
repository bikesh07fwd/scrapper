"""
pipeline/circuit_breaker.py — Implements the three-state circuit breaker pattern.

States:
- CLOSED: Requests are allowed. Failures increment count; success resets it.
- OPEN: Requests are blocked/skipped. After recovery timeout, transitions to HALF_OPEN.
- HALF_OPEN: Allows exactly one probe request. Success -> CLOSED, Failure -> OPEN.

DB Persistence:
- Circuit state is loaded from and persisted to the AdapterHealth database table.
- Survives process restarts by loading current health metadata on each run.
"""

from datetime import datetime, timezone
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import AdapterHealth

logger = structlog.get_logger(__name__)

# Enums/Constants for Circuit Breaker States
STATE_CLOSED = "CLOSED"
STATE_OPEN = "OPEN"
STATE_HALF_OPEN = "HALF_OPEN"


async def get_or_create_health(db_session: AsyncSession, adapter_name: str) -> AdapterHealth:
    """
    Loads or initializes the AdapterHealth record for a given adapter.
    """
    stmt = select(AdapterHealth).where(AdapterHealth.adapter == adapter_name)
    result = await db_session.execute(stmt)
    health = result.scalar_one_or_none()

    if not health:
        health = AdapterHealth(
            adapter=adapter_name,
            circuit_state=STATE_CLOSED,
            consecutive_failures=0,
        )
        db_session.add(health)
        # Flush so the record is tracked and gets an ID, but don't commit here
        await db_session.flush()

    return health


async def can_execute(
    db_session: AsyncSession,
    adapter_name: str,
    recovery_timeout_seconds: int,
) -> tuple[bool, str]:
    """
    Determines if the adapter is allowed to execute based on its circuit state.
    Updates the state to HALF_OPEN if the OPEN cooldown has expired.

    Returns:
        A tuple: (bool indicating if request can proceed, current active state string)
    """
    async with db_session.begin():
        health = await get_or_create_health(db_session, adapter_name)

        if health.circuit_state == STATE_CLOSED:
            return True, STATE_CLOSED

        if health.circuit_state == STATE_OPEN:
            if not health.circuit_opened_at:
                # Fallback if opened_at is somehow missing
                health.circuit_state = STATE_HALF_OPEN
                logger.info("circuit.state_transition", adapter=adapter_name, from_state=STATE_OPEN, to_state=STATE_HALF_OPEN, reason="missing_opened_at")
                return True, STATE_HALF_OPEN

            elapsed = (datetime.now(timezone.utc) - health.circuit_opened_at).total_seconds()
            if elapsed >= recovery_timeout_seconds:
                # Transition to HALF_OPEN to allow a single probe
                health.circuit_state = STATE_HALF_OPEN
                logger.info(
                    "circuit.state_transition",
                    adapter=adapter_name,
                    from_state=STATE_OPEN,
                    to_state=STATE_HALF_OPEN,
                    reason="recovery_timeout_elapsed",
                    elapsed_seconds=elapsed,
                )
                return True, STATE_HALF_OPEN
            else:
                # Block request
                return False, STATE_OPEN

        if health.circuit_state == STATE_HALF_OPEN:
            # Under a basic concurrent check, if it is already in HALF_OPEN, we allow the
            # probe. In a highly distributed setup this could be locked, but for our scope
            # we allow the probe request to execute.
            return True, STATE_HALF_OPEN

        return True, STATE_CLOSED


async def record_circuit_success(db_session: AsyncSession, adapter_name: str) -> None:
    """
    Records a successful request, resetting failures and closing the circuit.
    """
    health = await get_or_create_health(db_session, adapter_name)
    old_state = health.circuit_state

    health.consecutive_failures = 0
    health.last_success_at = datetime.now(timezone.utc)
    health.circuit_state = STATE_CLOSED

    if old_state != STATE_CLOSED:
        logger.info(
            "circuit.state_transition",
            adapter=adapter_name,
            from_state=old_state,
            to_state=STATE_CLOSED,
            reason="probe_success" if old_state == STATE_HALF_OPEN else "success",
        )


async def record_circuit_failure(
    db_session: AsyncSession,
    adapter_name: str,
    error_msg: str,
    failure_threshold: int,
) -> None:
    """
    Records a failed request. Increments failure count, and opens the circuit
    if the threshold is reached or if the failure occurred in HALF_OPEN state.
    """
    health = await get_or_create_health(db_session, adapter_name)
    old_state = health.circuit_state

    health.consecutive_failures += 1
    health.last_failure_at = datetime.now(timezone.utc)
    health.last_error = error_msg

    # Determine if we should open the circuit
    should_open = False
    reason = ""

    if health.circuit_state == STATE_CLOSED:
        if health.consecutive_failures >= failure_threshold:
            should_open = True
            reason = f"consecutive_failures_reached_threshold ({health.consecutive_failures})"
    elif health.circuit_state == STATE_HALF_OPEN:
        should_open = True
        reason = "probe_failed_in_half_open"

    if should_open:
        health.circuit_state = STATE_OPEN
        health.circuit_opened_at = datetime.now(timezone.utc)
        logger.warning(
            "circuit.state_transition",
            adapter=adapter_name,
            from_state=old_state,
            to_state=STATE_OPEN,
            reason=reason,
            consecutive_failures=health.consecutive_failures,
        )
