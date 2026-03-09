from __future__ import annotations

from datetime import datetime, timezone

# Python 3.11+ exposes datetime.UTC; fall back to timezone.utc on 3.10.
UTC = getattr(datetime, "UTC", timezone.utc)
