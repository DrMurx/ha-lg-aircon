"""Tests for the LG Aircon config flow."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lg_aircon.const import CONF_INFRARED_ENTITY_ID, DOMAIN

from .conftest import EMITTER_ENTITY_ID


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Skip actual entry setup during flow tests."""
    with patch(
        "custom_components.lg_aircon.async_setup_entry", return_value=True
    ):
        yield


@pytest.fixture
def mock_emitters() -> Generator[None]:
    """Pretend one infrared emitter entity exists."""
    with patch(
        "custom_components.lg_aircon.config_flow.async_get_emitters",
        return_value=[EMITTER_ENTITY_ID],
    ):
        yield


async def test_user_flow_creates_entry(
    hass: HomeAssistant, mock_setup_entry: None, mock_emitters: None
) -> None:
    """The happy path creates an entry titled after the chosen name."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Living Room AC",
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living Room AC"
    assert result["data"] == {
        CONF_NAME: "Living Room AC",
        CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
    }


async def test_aborts_without_emitters(hass: HomeAssistant) -> None:
    """The flow aborts when no infrared emitter entities exist."""
    with patch(
        "custom_components.lg_aircon.config_flow.async_get_emitters",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_emitters"


async def test_aborts_on_duplicate_name_and_emitter(
    hass: HomeAssistant, mock_setup_entry: None, mock_emitters: None
) -> None:
    """The same name + emitter pair cannot be configured twice."""
    MockConfigEntry(
        domain=DOMAIN,
        title="Living Room AC",
        data={
            CONF_NAME: "Living Room AC",
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Living Room AC",
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # A second unit on the same emitter under a different name is fine.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Bedroom AC",
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
