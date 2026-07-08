"""Shared fixtures for the LG Aircon (IR) tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lg_aircon.const import CONF_INFRARED_ENTITY_ID, DOMAIN

EMITTER_ENTITY_ID = "infrared.mock_emitter"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> Generator[None]:
    """Enable loading custom integrations from custom_components/."""
    yield


@pytest.fixture
def mock_send_command() -> Generator[AsyncMock]:
    """Capture commands sent through the infrared emitter helper."""
    with patch(
        "homeassistant.components.infrared.helpers.async_send_command",
        new_callable=AsyncMock,
    ) as mock:
        yield mock


def sent_values(mock_send_command: AsyncMock) -> list[int]:
    """Return the 28-bit frame values of all sent commands, in order."""
    return [call.args[2].value for call in mock_send_command.await_args_list]


@pytest.fixture
async def config_entry(
    hass: HomeAssistant, mock_send_command: AsyncMock
) -> AsyncGenerator[MockConfigEntry]:
    """Set up a configured LG Aircon entry against a fake emitter."""
    # A state for the emitter entity keeps the consumer entities available.
    hass.states.async_set(EMITTER_ENTITY_ID, "idle")
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living Room AC",
        data={
            CONF_NAME: "Living Room AC",
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    yield entry
