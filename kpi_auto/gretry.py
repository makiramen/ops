"""Retry Google API calls on 429/5xx (Sheets read quota is 60/min per user; the site sheet loop exceeds it)."""
import time
from googleapiclient.http import HttpRequest
from googleapiclient.errors import HttpError
_orig = HttpRequest.execute
def _execute(self, *a, **k):
    for i in range(10):
        try:
            return _orig(self, *a, **k)
        except HttpError as e:
            if getattr(e.resp, 'status', 0) in (429, 500, 502, 503) and i < 9:
                time.sleep(min(70, 15 * (i + 1))); continue
            raise
HttpRequest.execute = _execute
