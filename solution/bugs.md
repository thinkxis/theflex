Bug #1 — cache key collision. 
backend/app/services/cache.py

The Redis cache key is f"revenue:{property_id}" — it doesn't include tenant_id. 

Your seed data has prop-001 existing for both tenants 
(tenant-a = "Beach House Alpha", tenant-b = "Mountain Lodge Beta"). 

So whichever tenant asks for prop-001 first populates the cache, and the other tenant gets served that cached data for the next 5 minutes. 
That's exactly Ocean Rentals' "revenue that looks like another company's" report.






Bug 2 — Money handled as float (finance's "off by a few cents")
backend/app/api/v1/dashboard.py

total_revenue_float = float(revenue_data['total']) 
converts an exact Decimal into a binary float, which can't represent values like 333.333 exactly. 

The frontend then re-rounds it again (Math.round(total*100)/100) — two lossy conversions compounding. 
(The frontend even already has a dormant "Precision Mismatch Detected" warning built in for this — a tell that this was the intended bug.)






Bug 3 — Timezone-naive month boundaries (Client A's March mismatch)
backend/app/services/reservations.py

calculate_monthly_revenue builds month boundaries with naive datetime(year, month, 1) — no awareness of the property's local timezone (Paris/New York), even though properties.

timezone exists in the schema for exactly this purpose. 
A reservation like 2024-02-29 23:30:00+00 is Feb in UTC 
but already March 1st in Europe/Paris — so a UTC-boundary query and a property-local-boundary query disagree on which month it belongs to. 

That's the discrepancy between your system and Sunset Properties' own (timezone-aware) records.