"""
BUG 3 FIX (timezone-naive month boundaries — Client A's March mismatch):
calculate_monthly_revenue previously built month boundaries with naive
datetime(year, month, 1) — no awareness of the property's local timezone,
even though properties.timezone exists in the schema for exactly this
purpose. A reservation at 2024-02-29 23:30:00+00 is still February in UTC
but already March 1st in Europe/Paris, so a UTC-boundary query disagreed
with the property's own (timezone-aware) books.

Fix: look up the property's timezone, build the month boundaries in that
local timezone, then convert them to UTC before querying (since
check_in_date is stored in UTC). This makes "which month a reservation
belongs to" match the property's local calendar, not the server's UTC one.
"""
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "UTC"


async def _get_property_timezone(property_id: str, db_session=None) -> str:
    """Looks up the property's timezone; falls back to UTC if unavailable."""
    if db_session is None:
        return DEFAULT_TIMEZONE
    try:
        from sqlalchemy import text
        query = text("SELECT timezone FROM properties WHERE id = :property_id")
        result = await db_session.execute(query, {"property_id": property_id})
        row = result.fetchone()
        if row and row.timezone:
            return row.timezone
    except Exception as e:
        print(f"Could not resolve timezone for {property_id}, defaulting to UTC: {e}")
    return DEFAULT_TIMEZONE


async def calculate_monthly_revenue(
    property_id: str, tenant_id: str, month: int, year: int, db_session=None
) -> Decimal:
    """
    Calculates revenue for a specific month, using the property's own local
    timezone to define the month boundary (instead of naive UTC).
    """
    tz_name = await _get_property_timezone(property_id, db_session)
    tz = ZoneInfo(tz_name)

    start_local = datetime(year, month, 1, tzinfo=tz)
    if month < 12:
        end_local = datetime(year, month + 1, 1, tzinfo=tz)
    else:
        end_local = datetime(year + 1, 1, 1, tzinfo=tz)

    # check_in_date is stored in UTC, so convert the local boundaries to UTC
    # before querying against it.
    start_utc = start_local.astimezone(ZoneInfo("UTC"))
    end_utc = end_local.astimezone(ZoneInfo("UTC"))

    print(f"DEBUG: Querying revenue for {property_id} ({tz_name}) from {start_utc} to {end_utc}")

    query = """
        SELECT SUM(total_amount) as total
        FROM reservations
        WHERE property_id = $1
        AND tenant_id = $2
        AND check_in_date >= $3
        AND check_in_date < $4
    """

    if db_session is not None:
        result = await db_session.fetch_val(query, property_id, tenant_id, start_utc, end_utc)
        return Decimal(str(result)) if result is not None else Decimal('0')

    # No live DB session wired up yet.
    return Decimal('0')


async def calculate_total_revenue(property_id: str, tenant_id: str) -> Dict[str, Any]:
    """
    Aggregates revenue from the database, scoped to a single tenant so a
    property_id collision across tenants can never leak another tenant's
    numbers (complements the tenant-scoped cache key fix in cache.py).
    """
    try:
        from app.core.database_pool import DatabasePool

        db_pool = DatabasePool()
        await db_pool.initialize()

        if db_pool.session_factory:
            async with db_pool.get_session() as session:
                from sqlalchemy import text

                query = text("""
                    SELECT
                        property_id,
                        SUM(total_amount) as total_revenue,
                        COUNT(*) as reservation_count
                    FROM reservations
                    WHERE property_id = :property_id AND tenant_id = :tenant_id
                    GROUP BY property_id
                """)

                result = await session.execute(query, {
                    "property_id": property_id,
                    "tenant_id": tenant_id
                })
                row = result.fetchone()

                if row:
                    total_revenue = Decimal(str(row.total_revenue))
                    return {
                        "property_id": property_id,
                        "tenant_id": tenant_id,
                        "total": str(total_revenue),
                        "currency": "USD",
                        "count": row.reservation_count
                    }
                else:
                    return {
                        "property_id": property_id,
                        "tenant_id": tenant_id,
                        "total": "0.00",
                        "currency": "USD",
                        "count": 0
                    }
        else:
            raise Exception("Database pool not available")

    except Exception as e:
        print(f"Database error for {property_id} (tenant: {tenant_id}): {e}")

        # Property-specific mock data, scoped per tenant so two tenants
        # sharing a property_id (e.g. prop-001) never see each other's
        # figures even in the fallback path.
        mock_data = {
            'tenant-a': {
                'prop-001': {'total': '1000.00', 'count': 3},
                'prop-002': {'total': '4975.50', 'count': 4},
            },
            'tenant-b': {
                'prop-001': {'total': '3256.00', 'count': 3},
                'prop-003': {'total': '6100.50', 'count': 2},
                'prop-004': {'total': '1776.50', 'count': 4},
            },
        }

        mock_property_data = mock_data.get(tenant_id, {}).get(
            property_id, {'total': '0.00', 'count': 0}
        )

        return {
            "property_id": property_id,
            "tenant_id": tenant_id,
            "total": mock_property_data['total'],
            "currency": "USD",
            "count": mock_property_data['count']
        }