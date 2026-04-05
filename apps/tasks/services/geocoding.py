import logging
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from django.conf import settings

logger = logging.getLogger(__name__)


def geocode_address(address: str) -> tuple[float, float] | tuple[None, None]:
    """
    Convert a text address to (latitude, longitude) using the Nominatim API.

    Returns (lat, lon) tuple on success, or (None, None) on failure.

    THESIS-NOTE: Nominatim has a usage policy of max 1 request/second and requires
    a unique User-Agent string. For production use, consider hosting a local
    Nominatim instance or using a paid geocoding service.
    """
    result = geocode_address_full(address)
    return result['lat'], result['lon']


def geocode_address_full(address: str) -> dict:
    """
    Geocode an address and return a dict with keys:
      lat, lon     — floats or None
      country_code — ISO 3166-1 alpha-2 lowercase string (e.g. 'ua', 'se', 'no'), or None
    """
    geolocator = Nominatim(user_agent=settings.NOMINATIM_USER_AGENT)
    try:
        location = geolocator.geocode(address, addressdetails=True, timeout=10)
        if location is None:
            logger.warning("Geocoding returned no results for address: %s", address)
            return {'lat': None, 'lon': None, 'country_code': None}
        country_code = (location.raw.get('address') or {}).get('country_code', None)
        logger.info(
            "Geocoded '%s' -> (%.6f, %.6f) country_code=%s",
            address, location.latitude, location.longitude, country_code,
        )
        return {'lat': location.latitude, 'lon': location.longitude, 'country_code': country_code}
    except GeocoderTimedOut:
        logger.error("Geocoding timed out for address: %s", address)
        return {'lat': None, 'lon': None, 'country_code': None}
    except GeocoderServiceError as exc:
        logger.error("Geocoding service error for address '%s': %s", address, exc)
        return {'lat': None, 'lon': None, 'country_code': None}
