"""Client for Open-Meteo weather API - free, no API key required."""

from dataclasses import dataclass
from typing import Any, TypedDict

import httpx


class CityInfo(TypedDict):
    lat: float
    lon: float
    timezone: str


AUSTRALIAN_CITIES: dict[str, CityInfo] = {
    "sydney": {"lat": -33.8688, "lon": 151.2093, "timezone": "Australia/Sydney"},
    "melbourne": {"lat": -37.8136, "lon": 144.9631, "timezone": "Australia/Melbourne"},
    "brisbane": {"lat": -27.4705, "lon": 153.0260, "timezone": "Australia/Brisbane"},
    "perth": {"lat": -31.9514, "lon": 115.8617, "timezone": "Australia/Perth"},
    "adelaide": {"lat": -34.9285, "lon": 138.6007, "timezone": "Australia/Adelaide"},
    "canberra": {"lat": -35.2802, "lon": 149.1310, "timezone": "Australia/Sydney"},
    "hobart": {"lat": -42.8826, "lon": 147.3257, "timezone": "Australia/Hobart"},
    "darwin": {"lat": -12.4634, "lon": 130.8456, "timezone": "Australia/Darwin"},
    "gold coast": {"lat": -28.0167, "lon": 153.4000, "timezone": "Australia/Brisbane"},
    "newcastle": {"lat": -32.9283, "lon": 151.7817, "timezone": "Australia/Sydney"},
}

WMO_WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


@dataclass
class CurrentWeather:
    city: str
    temperature: float
    apparent_temperature: float
    humidity: int
    wind_speed: float
    wind_direction: int
    weather_code: int
    weather_description: str
    is_day: bool
    precipitation: float
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "city": self.city,
            "temperature_celsius": self.temperature,
            "feels_like_celsius": self.apparent_temperature,
            "humidity_percent": self.humidity,
            "wind_speed_kmh": self.wind_speed,
            "wind_direction_degrees": self.wind_direction,
            "conditions": self.weather_description,
            "is_daytime": self.is_day,
            "precipitation_mm": self.precipitation,
            "timestamp": self.timestamp,
        }


@dataclass
class DailyForecast:
    date: str
    temperature_max: float
    temperature_min: float
    weather_code: int
    weather_description: str
    precipitation_probability: int
    precipitation_sum: float
    wind_speed_max: float
    uv_index_max: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "high_celsius": self.temperature_max,
            "low_celsius": self.temperature_min,
            "conditions": self.weather_description,
            "precipitation_chance_percent": self.precipitation_probability,
            "precipitation_mm": self.precipitation_sum,
            "wind_speed_max_kmh": self.wind_speed_max,
            "uv_index": self.uv_index_max,
        }


class WeatherAPIError(Exception):
    """Raised when Open-Meteo cannot be reached or returns an unexpected payload."""


class WeatherClient:
    """Client for Open-Meteo API."""

    BASE_URL = "https://api.open-meteo.com/v1"

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _resolve_location(self, city: str) -> tuple[float, float, str]:
        """Resolve city name to coordinates."""
        city_lower = city.lower().strip()
        if city_lower in AUSTRALIAN_CITIES:
            info = AUSTRALIAN_CITIES[city_lower]
            return info["lat"], info["lon"], info["timezone"]
        raise ValueError(
            f"Unknown city: {city}. Supported cities: {', '.join(sorted(AUSTRALIAN_CITIES))}"
        )

    async def _forecast_json(self, params: dict[str, Any]) -> dict[str, Any]:
        client = await self._get_client()
        try:
            response = await client.get(f"{self.BASE_URL}/forecast", params=params)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise WeatherAPIError(f"Open-Meteo request failed: {exc}") from exc
        except ValueError as exc:
            raise WeatherAPIError("Open-Meteo returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise WeatherAPIError("Open-Meteo returned an unexpected payload")
        return payload

    async def get_current_weather(self, city: str) -> CurrentWeather:
        """Get current weather for an Australian city."""
        lat, lon, tz = self._resolve_location(city)
        data = await self._forecast_json(
            {
                "latitude": lat,
                "longitude": lon,
                "timezone": tz,
                "current": (
                    "temperature_2m,relative_humidity_2m,apparent_temperature,is_day,"
                    "precipitation,weather_code,wind_speed_10m,wind_direction_10m"
                ),
            }
        )

        current = data.get("current")
        if not isinstance(current, dict):
            raise WeatherAPIError("Open-Meteo response missing current weather data")

        try:
            weather_code = int(current["weather_code"])
            return CurrentWeather(
                city=city.title(),
                temperature=float(current["temperature_2m"]),
                apparent_temperature=float(current["apparent_temperature"]),
                humidity=int(current["relative_humidity_2m"]),
                wind_speed=float(current["wind_speed_10m"]),
                wind_direction=int(current["wind_direction_10m"]),
                weather_code=weather_code,
                weather_description=WMO_WEATHER_CODES.get(weather_code, "Unknown"),
                is_day=bool(current["is_day"]),
                precipitation=float(current["precipitation"]),
                timestamp=str(current["time"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise WeatherAPIError(
                f"Open-Meteo current weather payload is missing or invalid: {exc}"
            ) from exc

    async def get_forecast(self, city: str, days: int = 7) -> list[DailyForecast]:
        """Get weather forecast for an Australian city."""
        days = min(max(days, 1), 16)
        lat, lon, tz = self._resolve_location(city)
        data = await self._forecast_json(
            {
                "latitude": lat,
                "longitude": lon,
                "timezone": tz,
                "forecast_days": days,
                "daily": (
                    "weather_code,temperature_2m_max,temperature_2m_min,"
                    "precipitation_probability_max,precipitation_sum,"
                    "wind_speed_10m_max,uv_index_max"
                ),
            }
        )

        daily = data.get("daily")
        if not isinstance(daily, dict) or "time" not in daily:
            raise WeatherAPIError("Open-Meteo response missing daily forecast data")

        forecasts = []
        try:
            for i in range(len(daily["time"])):
                weather_code = int(daily["weather_code"][i])
                forecasts.append(
                    DailyForecast(
                        date=str(daily["time"][i]),
                        temperature_max=float(daily["temperature_2m_max"][i]),
                        temperature_min=float(daily["temperature_2m_min"][i]),
                        weather_code=weather_code,
                        weather_description=WMO_WEATHER_CODES.get(weather_code, "Unknown"),
                        precipitation_probability=int(daily["precipitation_probability_max"][i]),
                        precipitation_sum=float(daily["precipitation_sum"][i]),
                        wind_speed_max=float(daily["wind_speed_10m_max"][i]),
                        uv_index_max=float(daily["uv_index_max"][i]),
                    )
                )
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise WeatherAPIError(
                f"Open-Meteo forecast payload is missing or invalid: {exc}"
            ) from exc

        return forecasts

    async def compare_weather(self, cities: list[str]) -> dict[str, Any]:
        """Compare current weather across multiple cities."""
        if len(cities) > 5:
            cities = cities[:5]

        results: dict[str, Any] = {}
        for city in cities:
            try:
                weather = await self.get_current_weather(city)
                results[city.title()] = weather.to_dict()
            except (ValueError, WeatherAPIError) as exc:
                results[city.title()] = {"error": str(exc)}

        valid_temps = [
            (city, data["temperature_celsius"])
            for city, data in results.items()
            if isinstance(data, dict) and "temperature_celsius" in data
        ]
        if valid_temps:
            hottest = max(valid_temps, key=lambda item: item[1])
            coldest = min(valid_temps, key=lambda item: item[1])
            results["_summary"] = {
                "hottest": {"city": hottest[0], "temperature": hottest[1]},
                "coldest": {"city": coldest[0], "temperature": coldest[1]},
            }

        return results

    def list_available_cities(self) -> list[str]:
        """List all supported Australian cities."""
        return sorted([city.title() for city in AUSTRALIAN_CITIES])
