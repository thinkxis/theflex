bash

python3 verify_fixes.py
Output

======================================================================
BUG 1: Cross-tenant cache key collision
======================================================================
OLD key for tenant-a/prop-001: revenue:prop-001
OLD key for tenant-b/prop-001: revenue:prop-001
  -> COLLISION: True  (tenant B gets tenant A's cached data!)
NEW key for tenant-a/prop-001: revenue:tenant-a:prop-001
NEW key for tenant-b/prop-001: revenue:tenant-b:prop-001
  -> Collision: False  (fixed)

======================================================================
BUG 2: Money as float vs Decimal (finance's 'off by a few cents')
======================================================================
OLD: float(str(a)) + float(str(b)) = 666.667  (binary float can't represent these exactly)
NEW: (a + b) as Decimal, quantized to cents = 666.67  (exact)

Full reservation set - exact Decimal sum: 2250.000
OLD (float, then frontend Math.round(x*100)/100 again): 2250.0
NEW (Decimal-rounded to the cent BEFORE float conversion): 2250.0

======================================================================
BUG 3: Timezone-naive month boundaries (March mismatch)
======================================================================
Reservation check_in_date (stored in UTC): 2024-02-29 23:30:00+00:00
OLD naive UTC boundary treats March as starting: 2024-03-01 00:00:00+00:00
  -> Is this reservation counted in March (OLD)? False
Reservation in property's local time (Europe/Paris): 2024-03-01 00:30:00+01:00
NEW Paris-local March boundary, converted to UTC: 2024-02-29 23:00:00+00:00
  -> Is this reservation counted in March (NEW, matches client's own books)? True