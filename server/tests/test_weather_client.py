"""Tests for the weather client."""

import pytest
import respx
from httpx import Response

from mcp_server.weather_client import (
    AUSTRALIAN_CITIES,
    WMO_WEATHER_CODES,
    WeatherAPIError,
    WeatherClient,
)


@pytest.fixture
def weather_client():
    return WeatherClient()


@pytest.fixture
def mock_current_weather_response():
    return {
        "current": {
            "time": "2024-10-06T10:00",
            "temperature_2m": 22.5,
            "relative_humidity_2m": 65,
            "apparent_temperature": 21.0,
            "is_day": 1,
            "precipitation": 0.0,
            "weather_code": 1,
            "wind_speed_10m": 15.0,
            "wind_direction_10m": 180,
        }
    }


@pytest.fixture
def mock_forecast_response():
    return {
        "daily": {
            "time": ["2024-10-06", "2024-10-07", "2024-10-08"],
            "weather_code": [1, 3, 61],
            "temperature_2m_max": [25.0, 23.0, 20.0],
            "temperature_2m_min": [15.0, 14.0, 12.0],
            "precipitation_probability_max": [10, 30, 80],
            "precipitation_sum": [0.0, 0.5, 15.0],
            "wind_speed_10m_max": [20.0, 25.0, 35.0],
            "uv_index_max": [6.0, 5.0, 3.0],
        }
    }


class TestWeatherClient:
    def test_list_available_cities(self, weather_client):
        cities = weather_client.list_available_cities()
        assert len(cities) == 10
        assert "Sydney" in cities
        assert "Melbourne" in cities
        assert "Brisbane" in cities

    def test_resolve_location_valid(self, weather_client):
        lat, lon, tz = weather_client._resolve_location("Sydney")
        assert lat == -33.8688
        assert lon == 151.2093
        assert tz == "Australia/Sydney"

    def test_resolve_location_case_insensitive(self, weather_client):
        lat1, lon1, tz1 = weather_client._resolve_location("SYDNEY")
        lat2, lon2, tz2 = weather_client._resolve_location("sydney")
        assert lat1 == lat2
        assert lon1 == lon2

    def test_resolve_location_invalid(self, weather_client):
        with pytest.raises(ValueError) as exc_info:
            weather_client._resolve_location("InvalidCity")
        assert "Unknown city" in str(exc_info.value)

    @respx.mock
    async def test_get_current_weather(self, weather_client, mock_current_weather_response):
        respx.get("https://api.open-meteo.com/v1/forecast").mock(
            return_value=Response(200, json=mock_current_weather_response)
        )

        weather = await weather_client.get_current_weather("Sydney")

        assert weather.city == "Sydney"
        assert weather.temperature == 22.5
        assert weather.humidity == 65
        assert weather.wind_speed == 15.0
        assert weather.weather_description == "Mainly clear"
        assert weather.is_day is True

    @respx.mock
    async def test_get_forecast(self, weather_client, mock_forecast_response):
        respx.get("https://api.open-meteo.com/v1/forecast").mock(
            return_value=Response(200, json=mock_forecast_response)
        )

        forecast = await weather_client.get_forecast("Sydney", days=3)

        assert len(forecast) == 3
        assert forecast[0].date == "2024-10-06"
        assert forecast[0].temperature_max == 25.0
        assert forecast[0].temperature_min == 15.0
        assert forecast[2].precipitation_probability == 80

    @respx.mock
    async def test_compare_weather(self, weather_client, mock_current_weather_response):
        respx.get("https://api.open-meteo.com/v1/forecast").mock(
            return_value=Response(200, json=mock_current_weather_response)
        )

        comparison = await weather_client.compare_weather(["Sydney", "Melbourne"])

        assert "Sydney" in comparison
        assert "Melbourne" in comparison
        assert "_summary" in comparison
        assert "hottest" in comparison["_summary"]

    def test_weather_codes_mapping(self):
        assert WMO_WEATHER_CODES[0] == "Clear sky"
        assert WMO_WEATHER_CODES[61] == "Slight rain"
        assert WMO_WEATHER_CODES[95] == "Thunderstorm"

    def test_australian_cities_have_coordinates(self):
        for _city, info in AUSTRALIAN_CITIES.items():
            assert "lat" in info
            assert "lon" in info
            assert "timezone" in info
            assert -45 < info["lat"] < -10  # Valid Australian latitude range
            assert 110 < info["lon"] < 160  # Valid Australian longitude range

    @respx.mock
    async def test_get_current_weather_http_error(self, weather_client):
        respx.get("https://api.open-meteo.com/v1/forecast").mock(
            return_value=Response(503, json={"error": True})
        )
        with pytest.raises(WeatherAPIError, match="Open-Meteo request failed"):
            await weather_client.get_current_weather("Sydney")

    @respx.mock
    async def test_get_current_weather_malformed_payload(self, weather_client):
        respx.get("https://api.open-meteo.com/v1/forecast").mock(
            return_value=Response(200, json={"current": {"temperature_2m": 20}})
        )
        with pytest.raises(WeatherAPIError, match="missing or invalid"):
            await weather_client.get_current_weather("Sydney")
