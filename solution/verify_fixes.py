"""
Standalone demonstration of the three bugs + fixes, without needing Docker/DB.
Run: python3 verify_fixes.py
"""
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from zoneinfo import ZoneInfo

print("=" * 70)
print("BUG 1: Cross-tenant cache key collision")
print("=" * 70)

# prop-001 exists for BOTH tenant-a and tenant-b (see database/seed.sql)
def old_cache_key(property_id, tenant_id):
    return f"revenue:{property_id}"

def new_cache_key(property_id, tenant_id):
    return f"revenue:{tenant_id}:{property_id}"

old_a = old_cache_key("prop-001", "tenant-a")
old_b = old_cache_key("prop-001", "tenant-b")
print(f"OLD key for tenant-a/prop-001: {old_a}")
print(f"OLD key for tenant-b/prop-001: {old_b}")
print(f"  -> COLLISION: {old_a == old_b}  (tenant B gets tenant A's cached data!)")

new_a = new_cache_key("prop-001", "tenant-a")
new_b = new_cache_key("prop-001", "tenant-b")
print(f"NEW key for tenant-a/prop-001: {new_a}")
print(f"NEW key for tenant-b/prop-001: {new_b}")
print(f"  -> Collision: {new_a == new_b}  (fixed)")

print()
print("=" * 70)
print("BUG 2: Money as float vs Decimal (finance's 'off by a few cents')")
print("=" * 70)

# Reservation amounts are stored as NUMERIC(10,3) -- sub-cent precision is
# intentional in this schema (see database/schema.sql comment). Summing many
# of these and then bouncing through float (backend `float(...)`, then the
# frontend doing ANOTHER `Math.round(x * 100) / 100`) is where drift creeps
# in over many properties/requests. A clean minimal repro of the underlying
# float issue:
a, b = Decimal("333.333"), Decimal("333.334")
print(f"OLD: float(str(a)) + float(str(b)) = {float(str(a)) + float(str(b))!r}  "
      f"(binary float can't represent these exactly)")
print(f"NEW: (a + b) as Decimal, quantized to cents = "
      f"{(a + b).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}  (exact)")

amounts = [Decimal("333.333"), Decimal("333.333"), Decimal("333.334"), Decimal("1250.000")]
decimal_total = sum(amounts)
print(f"\nFull reservation set - exact Decimal sum: {decimal_total}")

old_float = float(str(decimal_total))
print(f"OLD (float, then frontend Math.round(x*100)/100 again): {old_float!r}")

new_decimal = decimal_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
new_float = float(new_decimal)
print(f"NEW (Decimal-rounded to the cent BEFORE float conversion): {new_float!r}")

print()
print("=" * 70)
print("BUG 3: Timezone-naive month boundaries (March mismatch)")
print("=" * 70)

check_in_utc = datetime(2024, 2, 29, 23, 30, tzinfo=ZoneInfo("UTC"))
print(f"Reservation check_in_date (stored in UTC): {check_in_utc}")

# OLD: naive UTC month boundary
old_march_start = datetime(2024, 3, 1, tzinfo=ZoneInfo("UTC"))
print(f"OLD naive UTC boundary treats March as starting: {old_march_start}")
print(f"  -> Is this reservation counted in March (OLD)? {check_in_utc >= old_march_start}")

# NEW: property-local (Europe/Paris) month boundary, converted to UTC
paris = ZoneInfo("Europe/Paris")
new_march_start_local = datetime(2024, 3, 1, tzinfo=paris)
new_march_start_utc = new_march_start_local.astimezone(ZoneInfo("UTC"))
local_check_in = check_in_utc.astimezone(paris)
print(f"Reservation in property's local time (Europe/Paris): {local_check_in}")
print(f"NEW Paris-local March boundary, converted to UTC: {new_march_start_utc}")
print(f"  -> Is this reservation counted in March (NEW, matches client's own books)? "
      f"{check_in_utc >= new_march_start_utc}")