"""Artwork identity and lookup. Curated custom images always outrank generated art."""
from __future__ import annotations
import json
import os
import re
from pathlib import Path
from .config import ROOT

NAME = re.compile(r'[A-Za-z]{2,32} [a-z][a-z-]{1,40}(?: [a-z][a-z-]{1,40})?\Z')
SLUG = re.compile(r'[a-z]+(?:[_-][a-z]+)+\Z')


def art_state() -> Path:
    return Path(os.environ.get('GARDEN_INK_STATE_DIR', str(ROOT/'state'))).expanduser()/'autoart'


def read_manifest(assets=None):
    path = (assets or ROOT/'assets')/'manifest.json'
    value = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    if not isinstance(value, dict): raise ValueError('Artwork manifest must be an object')
    return value


def identity(scientific: str, assets=None):
    """Validate a name, normalise aliases; subspecies share their species plate."""
    name = ' '.join(str(scientific).split())
    if not NAME.fullmatch(name): raise ValueError('Expected a scientific species name')
    key = ' '.join(name.split()[:2]).casefold()
    entry = read_manifest(assets).get(key, {})
    filename = entry.get('file', '')
    slug = Path(filename).stem if filename.endswith('.png') and '/' not in filename and '\\' not in filename else key.replace(' ', '_')
    if not SLUG.fullmatch(slug): raise ValueError('Unsafe artwork identifier')
    return slug, slug.replace('_', ' ').capitalize()


def candidates(scientific: str, assets=None):
    assets = assets or ROOT/'assets'
    slug, name = identity(scientific, assets)
    manifest = read_manifest(assets)
    exact = '_'.join(str(scientific).strip().casefold().split())
    keys = [exact, slug]
    for key, entry in manifest.items():
        if isinstance(entry, dict) and entry.get('file') == slug+'.png':
            alias = key.replace(' ', '_')
            if SLUG.fullmatch(alias): keys.append(alias)
    keys = list(dict.fromkeys(keys))
    return ([assets/'custom'/(key+'.png') for key in keys] +
            [art_state()/'images'/(slug+'.png')] +
            [assets/'birds'/(slug+'.png')])


def find_art(species: dict, assets=None):
    try:
        return next((p for p in candidates(species['scientific_name'], assets) if p.is_file()), None)
    except (ValueError, KeyError):
        return None
