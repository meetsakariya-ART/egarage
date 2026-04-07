"""
core/geocode.py
───────────────
Converts a text address to lat/lng using OpenStreetMap Nominatim.
Completely FREE — no API key needed.
"""

import urllib.request
import urllib.parse
import json
import logging

logger = logging.getLogger(__name__)


def geocode_address(address: str, city: str = '', country: str = 'India') -> dict:
    """
    Returns {'lat': float, 'lng': float, 'display': str} or None if not found.

    Usage:
        result = geocode_address('42 Kalavad Road', city='Rajkot')
        if result:
            garage.lat = result['lat']
            garage.lng = result['lng']
    """
    query = ', '.join(filter(None, [address, city, country]))
    params = urllib.parse.urlencode({
        'q':              query,
        'format':         'json',
        'limit':          1,
        'addressdetails': 1,
    })
    url = f'https://nominatim.openstreetmap.org/search?{params}'

    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'eGarage-App/1.0 (egarage.in)'}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())

        if data:
            return {
                'lat':     float(data[0]['lat']),
                'lng':     float(data[0]['lon']),
                'display': data[0].get('display_name', query),
            }
    except Exception as e:
        logger.error(f'Geocode failed for "{query}": {e}')

    return None