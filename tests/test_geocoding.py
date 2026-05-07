"""
Модульні тести для сервісу геокодування (з моками — без реальних HTTP-запитів).
"""
from unittest.mock import patch, MagicMock
import pytest
from apps.tasks.services.geocoding import geocode_address
from geopy.exc import GeocoderTimedOut, GeocoderServiceError


class TestGeocodeAddress:
    @patch('apps.tasks.services.geocoding.Nominatim')
    def test_successful_geocoding(self, mock_nominatim_cls):
        mock_loc = MagicMock()
        mock_loc.latitude = 50.4501
        mock_loc.longitude = 30.5234
        mock_nominatim_cls.return_value.geocode.return_value = mock_loc

        lat, lon = geocode_address("Kyiv, Ukraine")
        assert lat == pytest.approx(50.4501)
        assert lon == pytest.approx(30.5234)

    @patch('apps.tasks.services.geocoding.Nominatim')
    def test_address_not_found_returns_none(self, mock_nominatim_cls):
        mock_nominatim_cls.return_value.geocode.return_value = None
        lat, lon = geocode_address("Nonexistent Address XYZ123")
        assert lat is None
        assert lon is None

    @patch('apps.tasks.services.geocoding.Nominatim')
    def test_timeout_returns_none(self, mock_nominatim_cls):
        mock_nominatim_cls.return_value.geocode.side_effect = GeocoderTimedOut()
        lat, lon = geocode_address("Some Address")
        assert lat is None
        assert lon is None

    @patch('apps.tasks.services.geocoding.Nominatim')
    def test_service_error_returns_none(self, mock_nominatim_cls):
        mock_nominatim_cls.return_value.geocode.side_effect = GeocoderServiceError("service down")
        lat, lon = geocode_address("Some Address")
        assert lat is None
        assert lon is None
