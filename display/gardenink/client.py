from __future__ import annotations
import json
import logging
import time
from datetime import timedelta
from urllib import request, error, parse
from .config import Settings
from .model import utcnow, timestamp, iso, WindowAccumulator, window_bounds

LOG = logging.getLogger(__name__)
MAX_BODY = 8 * 1024 * 1024

class APIError(RuntimeError):
    pass

class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # A token must never be forwarded to an unexpected host. Configure the final URL.
        raise APIError('The station redirected the API request; configure its final base URL')

class Client:
    def __init__(self, settings: Settings, token: str = '', opener=None):
        self.settings = settings
        self.token = token
        # A local display must not send LAN API traffic through an environment proxy.
        self.opener = opener or request.build_opener(request.ProxyHandler({}), NoRedirect())

    def get(self, endpoint: str, params=None, health: bool = False):
        url = self.settings.base_url + '/api/v1/' + endpoint
        if params: url += '?' + parse.urlencode(params)
        headers = {'Accept': 'application/json', 'Cache-Control': 'no-cache',
                   'User-Agent': 'GardenInk/2.0 (read-only OpenObservatory display)'}
        if self.token: headers['Authorization'] = 'Bearer ' + self.token
        req = request.Request(url, headers=headers, method='GET')
        try:
            response = self.opener.open(req, timeout=self.settings.request_timeout_seconds)
        except error.HTTPError as exc:
            if health and exc.code == 503:
                response = exc  # OpenObservatory returns valid critical-health JSON with 503.
            elif exc.code in (401, 403):
                exc.close()
                raise APIError('Authentication refused; set OO_API_TOKEN or token.txt') from None
            else:
                code = exc.code
                exc.close()
                raise APIError('API returned HTTP %d for %s' % (code, endpoint)) from None
        except (error.URLError, TimeoutError, OSError):
            raise APIError('Cannot reach the station; check its URL, LAN/Wi-Fi and service') from None
        try:
            with response:
                body = response.read(MAX_BODY + 1)
            if len(body) > MAX_BODY: raise APIError('API response exceeded the 8 MiB safety limit')
            payload = json.loads(body.decode('utf-8'))
        except (TimeoutError, OSError):
            raise APIError('The API response was interrupted or timed out') from None
        except (UnicodeError, json.JSONDecodeError):
            raise APIError('Expected JSON from the API, not a web/login page; check base_url') from None
        if not isinstance(payload, dict): raise APIError('Expected a JSON object from ' + endpoint)
        return payload

    def fetch(self) -> dict:
        """One read-only, bounded scan per displayed hour, reduced page by page.

        A new scan observes human review changes to earlier records as well as
        newly inserted detections. It avoids the v1 per-minute rescan and its
        four-page ceiling without introducing a stale append-only review cache.
        """
        started = time.monotonic()
        health_error = ''
        try:
            health = self.get('health', health=True)
            if not isinstance(health.get('capture', {}), dict) or not isinstance(health.get('pause', {}), dict):
                raise APIError('Malformed capture/health response')
        except APIError as exc:
            health, health_error = {}, str(exc)
        local_now = utcnow()
        clock_skew = False
        try:
            now = timestamp(health['checked_at'])
            clock_skew = abs((local_now - now).total_seconds()) > 300
        except (KeyError, ValueError, TypeError):
            now = local_now
        today_start, hour_start = window_bounds(now, self.settings.timezone)
        start, until = min(today_start, hour_start), now
        today = WindowAccumulator(today_start, now, self.settings.min_score, self.settings.timezone)
        hour = WindowAccumulator(hour_start, now, self.settings.min_score, self.settings.timezone)
        seen = set()
        previous_oldest = oldest_seen = None
        complete = False
        reason = 'Configured page budget reached'
        pages = 0
        required = {'id','event_start_utc','source_kind','is_live_source','taxonomic_group'}
        for page_no in range(self.settings.max_pages):
            # Always make at least one detections request. Later work is bounded.
            if page_no and time.monotonic() - started >= self.settings.fetch_budget_seconds:
                reason = 'Fetch time budget reached'
                break
            try:
                payload = self.get('detections', {
                    'since': iso(start), 'until': iso(until), 'group': 'bird',
                    'identified_only': 'true', 'include_synthetic': 'false',
                    # Filtering this on the server would hide human-confirmed or
                    # corrected records whose ORIGINAL model score was low.
                    'min_score': 0, 'limit': self.settings.page_size,
                })
            except APIError as exc:
                if not pages:
                    raise
                reason = 'Later page could not be fetched: ' + str(exc)
                LOG.warning('%s; retaining the explicitly partial current scan', reason)
                break
            pages += 1
            batch = payload.get('detections')
            if not isinstance(batch, list):
                raise APIError('The API has no detections array')
            if len(batch) > self.settings.page_size:
                raise APIError('The API ignored the requested page limit')
            oldest = None
            prior_time = None
            for row in batch:
                if not isinstance(row, dict) or not required <= set(row):
                    raise APIError('This deployment lacks expected detection identity/source fields')
                key = row.get('id')
                if not isinstance(key, str) or not key:
                    raise APIError('The API returned a missing or malformed detection ID')
                try:
                    when = timestamp(row['event_start_utc'])
                except (ValueError, TypeError):
                    raise APIError('The API returned an invalid detection timestamp') from None
                if not start <= when < until:
                    raise APIError('The API did not honour the requested detection time bounds')
                if prior_time is not None and when > prior_time:
                    raise APIError('The API no longer sorts detections newest first; cannot paginate safely')
                prior_time = when
                oldest = when if oldest is None else min(oldest, when)
                if key not in seen:
                    seen.add(key)
                    today.add(row)
                    hour.add(row)
            if oldest is not None:
                oldest_seen = oldest if oldest_seen is None else min(oldest_seen, oldest)
            truncated = payload.get('truncated', len(batch) >= self.settings.page_size)
            if not isinstance(truncated, bool):
                raise APIError('Malformed truncated flag')
            LOG.debug('API page %d: %d rows, %d distinct IDs, truncated=%s',
                      pages, len(batch), len(seen), truncated)
            if not truncated:
                complete, reason = True, ''
                break
            if oldest is None:
                reason = 'API claimed a truncated page without usable records'
                break
            if previous_oldest is not None and oldest >= previous_oldest:
                reason = 'Timestamp tie exceeds one API page; some records may be missing'
                break
            previous_oldest = oldest
            # Until is exclusive. One-microsecond overlap avoids silently skipping
            # the tied cohort at a page boundary. Seen IDs are deduplicated.
            until = oldest + timedelta(microseconds=1)
        # Descending pages prove completeness for a newer window when the oldest
        # returned timestamp is STRICTLY earlier than that window's inclusive start.
        # Thus a partial day need not incorrectly mark a fully scanned hour partial.
        day_complete = complete or (oldest_seen is not None and oldest_seen < today_start)
        hour_complete = complete or (oldest_seen is not None and oldest_seen < hour_start)
        day_result = today.finish(not day_complete, reason)
        hour_result = hour.finish(not hour_complete, reason)
        summary = dict(day_result)  # v1 fields remain aliases for TODAY for tooling.
        summary.update({'schema_version': 2, 'today': day_result, 'last_hour': hour_result,
                        'health': health, 'health_error': health_error, 'clock_skew': clock_skew,
                        'fetched_at': iso(local_now), 'offline': False, 'cached': False,
                        'demo': False, 'cache_identity': self.settings.identity(),
                        'scan': {'pages': pages, 'unique_rows': len(seen),
                                 'complete': complete, 'reason': reason,
                                 'oldest_seen': iso(oldest_seen) if oldest_seen else None,
                                 'elapsed_seconds': round(time.monotonic() - started, 2)}})
        return summary
