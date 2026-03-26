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
    geolocator = Nominatim(user_agent=settings.NOMINATIM_USER_AGENT)
    try:
        location = geolocator.geocode(address, timeout=10)
        if location is None:
            logger.warning("Geocoding returned no results for address: %s", address)
            return None, None
        logger.info("Geocoded '%s' -> (%.6f, %.6f)", address, location.latitude, location.longitude)
        return location.latitude, location.longitude
    except GeocoderTimedOut:
        logger.error("Geocoding timed out for address: %s", address)
        return None, None
    except GeocoderServiceError as exc:
        logger.error("Geocoding service error for address '%s': %s", address, exc)
        return None, None
