from datetime import timedelta
import logging
import aiohttp
import asyncio
import io

from PIL import Image
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import DOMAIN, URL, COLOR_THRESHOLDS

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=12)  # Update twice daily

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    coordinator = CHMIPollenCoordinator(hass)
    await coordinator.async_refresh()
    async_add_entities([CHMIPollenSensor(coordinator)], True)

class CHMIPollenCoordinator(DataUpdateCoordinator):
    def __init__(self, hass):
        super().__init__(
            hass,
            _LOGGER,
            name="CHMI Pollen Data",
            update_interval=SCAN_INTERVAL,
        )
        self.session = async_get_clientsession(hass)

    async def _async_update_data(self):
        try:
            async with self.session.get(URL) as resp:
                if resp.status != 200:
                    raise UpdateFailed(f"Error fetching image: {resp.status}")
                data = await resp.read()

            image = Image.open(io.BytesIO(data)).convert("RGB")

            # Analyze area of image (you can adjust the box)
            width, height = image.size
            box = (650, 1050, 700, 1100)
            cropped = image.crop(box)
            avg_color = tuple(map(int, cropped.resize((1, 1)).getpixel((0, 0))))

            _LOGGER.debug(f"Average color: {avg_color}")

            def closest_color(color):
                def distance(c1, c2):
                    return sum((a - b) ** 2 for a, b in zip(c1, c2))
                return min(COLOR_THRESHOLDS, key=lambda key: distance(color, COLOR_THRESHOLDS[key]))

            level = closest_color(avg_color)
            return {"color": avg_color, "level": level}

        except Exception as e:
            raise UpdateFailed(f"Image processing failed: {e}")

class CHMIPollenSensor(SensorEntity):
    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_name = "CHMI Pollen Level"
        self._attr_unique_id = "chmi_pollen_sensor"
        self._attr_native_unit_of_measurement = "level"
        self._attr_state_class = "measurement"

    @property
    def native_value(self):
        return self.coordinator.data.get("numeric") if self.coordinator.data else None

    @property
    def extra_state_attributes(self):
        if not self.coordinator.data:
            return {}
        return {
            "level": self.coordinator.data.get("level"),
            "average_color": self.coordinator.data.get("color")
        }

    async def async_update(self):
        await self.coordinator.async_request_refresh()
