import logging
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from django.conf import settings

logger = logging.getLogger(__name__)


def geocode_address(address: str) -> tuple[float, float] | tuple[None, None]:
    """
    Перетворює текстову адресу на (широта, довгота) за допомогою API Nominatim.

    Повертає кортеж (lat, lon) у разі успіху або (None, None) у разі помилки.
    """
    result = geocode_address_full(address)
    return result['lat'], result['lon']


def geocode_address_full(address: str) -> dict:
    """
    Геокодує адресу та повертає словник з ключами:
      lat, lon     — числа з плаваючою комою або None
      country_code — рядок ISO 3166-1 alpha-2 у нижньому регістрі (напр. 'ua', 'se', 'no') або None
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
