"""
BUG 2 FIX (money handled as float — finance's "off by a few cents"):
Previously `float(revenue_data['total'])` converted an exact Decimal
straight into a binary float, which can't represent values like 333.333
exactly. The frontend then re-rounded that already-imprecise float again
(Math.round(total * 100) / 100), compounding the error.

Fix: quantize the Decimal to the cent BEFORE converting to float. Rounding
happens once, on the exact Decimal, so the float that leaves the API is
already correct to the cent — the frontend's Math.round becomes a no-op
instead of a second lossy conversion.
"""
from decimal import Decimal, ROUND_HALF_UP
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from app.services.cache import get_revenue_summary
from app.core.auth import authenticate_request as get_current_user

router = APIRouter()


@router.get("/dashboard/summary")
async def get_dashboard_summary(
    property_id: str,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:

    tenant_id = getattr(current_user, "tenant_id", "default_tenant") or "default_tenant"

    revenue_data = await get_revenue_summary(property_id, tenant_id)

    # Quantize the exact Decimal to the cent first, then convert to float.
    total_revenue_decimal = Decimal(str(revenue_data['total'])).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )
    total_revenue_float = float(total_revenue_decimal)

    return {
        "property_id": revenue_data['property_id'],
        "total_revenue": total_revenue_float,
        "currency": revenue_data['currency'],
        "reservations_count": revenue_data['count']
    }