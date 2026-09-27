from __future__ import annotations
import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent

@dataclass
class Settings:
    base_url: str = ""
    title: str = "The garden"
    timezone: str = "Europe/London"
    lookback_hours: int = 6  # legacy compatibility; v2 uses local today + trailing hour
    min_score: float = 0.75
    poll_seconds: int = 3600  # legacy compatibility; fetches are tied to refreshes
    refresh_seconds: int = 3600
    heartbeat_seconds: int = 3600  # legacy compatibility
    layout: str = "journal"
    rotate_layouts: bool = False
    gallery_hours: list[int] = field(default_factory=lambda: [10, 14])
    rotation: int = 90
    artwork_mode: str = "colour"
    page_size: int = 500
    max_pages: int = 64
    fetch_budget_seconds: int = 180
    request_timeout_seconds: int = 10
    busy_timeout_seconds: int = 120
    spi_speed_hz: int = 4000000
    cache_max_age_hours: int = 24
    api_token_env: str = "OO_API_TOKEN"
    api_token_file: str = "token.txt"
    night_mode: bool = True
    latitude: float | None = None
    longitude: float | None = None
    bat_min_score: float = 0.5
    night_bird_ratio: float = 0.25
    night_bird_quiet_count: int = 2
    night_bat_count: int = 10
    night_bat_bins: int = 3
    night_coverage_fraction: float = 0.9
    night_max_pages: int = 128

    def validate(self, require_url: bool = True) -> 'Settings':
        for key in ('base_url','timezone','layout','artwork_mode','api_token_env','api_token_file'):
            if not isinstance(getattr(self,key), str):
                raise ValueError('%s must be a string' % key)
        if require_url or self.base_url:
            self.base_url = normalise_url(self.base_url)
        try:
            ZoneInfo(self.timezone)
        except (KeyError, TypeError) as exc:
            raise ValueError("Unknown IANA timezone: %s" % self.timezone) from exc
        limits = {
            'lookback_hours': (1, 168), 'min_score': (0.0, 1.0),
            'poll_seconds': (30, 3600), 'refresh_seconds': (180, 86400),
            'heartbeat_seconds': (180, 86400), 'page_size': (1, 500),
            'max_pages': (1, 256), 'fetch_budget_seconds': (10, 600), 'request_timeout_seconds': (1, 120),
            'busy_timeout_seconds': (30, 300), 'spi_speed_hz': (100000, 4000000),
            'cache_max_age_hours': (1, 168),
            'bat_min_score': (0, 1), 'night_bird_ratio': (0, 1),
            'night_bird_quiet_count': (0, 1000), 'night_bat_count': (1, 10000),
            'night_bat_bins': (1, 6), 'night_coverage_fraction': (0.5, 1),
            'night_max_pages': (1, 512),
        }
        for key, (lo, hi) in limits.items():
            val = getattr(self, key)
            if isinstance(val, bool) or not isinstance(val, (int, float)) or not lo <= val <= hi:
                raise ValueError('%s must be between %s and %s' % (key, lo, hi))
            if key not in ('min_score', 'bat_min_score', 'night_bird_ratio', 'night_coverage_fraction') and not isinstance(val, int):
                raise ValueError('%s must be an integer' % key)

        if self.layout not in ('journal', 'gallery'):
            raise ValueError('layout must be journal or gallery')
        if self.rotation not in (90, 270):
            raise ValueError('rotation must be 90 or 270 for this portrait screen')
        if self.artwork_mode not in ('colour', 'ink'):
            raise ValueError('artwork_mode must be colour or ink')
        if not isinstance(self.rotate_layouts, bool):
            raise ValueError('rotate_layouts must be true or false')
        if (not isinstance(self.gallery_hours, list) or
                any(type(hour) is not int or not 0 <= hour <= 23 for hour in self.gallery_hours) or
                len(set(self.gallery_hours)) != len(self.gallery_hours)):
            raise ValueError('gallery_hours must be a list of distinct local hours from 0 to 23')
        if not isinstance(self.night_mode, bool):
            raise ValueError('night_mode must be true or false')
        import math
        for key, bound in (('latitude', 90), ('longitude', 180)):
            value = getattr(self, key)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                                      or not math.isfinite(value) or not -bound <= value <= bound):
                raise ValueError('%s must be a finite coordinate' % key)
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError('Set both latitude and longitude, or neither')
        if not isinstance(self.title, str) or not 1 <= len(self.title) <= 50:
            raise ValueError('title must contain 1–50 characters')
        return self

    def token(self, config_path: Path) -> str:
        value = os.environ.get(self.api_token_env, '').strip()
        if not value and self.api_token_file:
            p = Path(self.api_token_file).expanduser()
            if not p.is_absolute(): p = config_path.parent / p
            if p.exists(): value = p.read_text(encoding='utf-8').strip()
        if '\r' in value or '\n' in value:
            raise ValueError('The API token must be a single line')
        return value

    def identity(self) -> str:
        import hashlib
        value = ['hourly-v2', self.base_url, self.timezone, self.min_score,
                 self.page_size, self.max_pages, self.fetch_budget_seconds,
                 self.night_mode, self.latitude, self.longitude, self.bat_min_score,
                 self.night_bird_ratio, self.night_bird_quiet_count,
                 self.night_bat_count, self.night_bat_bins, self.night_coverage_fraction]
        return hashlib.sha256(json.dumps(value).encode()).hexdigest()


def normalise_url(value: str) -> str:
    p = urlsplit(value.strip())
    if p.scheme not in ('http', 'https') or not p.hostname:
        raise ValueError('Set base_url to your station, e.g. http://YOUR-STATION:8080')
    if p.username or p.password or p.query or p.fragment:
        raise ValueError('Use a plain station URL, without credentials, query or fragment')
    p.port  # validates malformed ports
    path = p.path.rstrip('/')
    if path.endswith('/api/v1'):
        path = path[:-7]
    return urlunsplit((p.scheme, p.netloc, path, '', ''))


def load(path: Path) -> Settings:
    values = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    if not isinstance(values, dict): raise ValueError('Config must be a JSON object')
    unknown = set(values) - {f.name for f in fields(Settings)}
    if unknown: raise ValueError('Unknown config option(s): ' + ', '.join(sorted(unknown)))
    return Settings(**values)


def save(path: Path, settings: Settings) -> None:
    path.write_text(json.dumps(asdict(settings), indent=2) + '\n', encoding='utf-8')
    path.chmod(0o600)
