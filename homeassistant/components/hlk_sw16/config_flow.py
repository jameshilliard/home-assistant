"""Config flow for HLK-SW16."""
import asyncio
from contextlib import suppress

from hlk_sw16 import create_hlk_sw16_connection
from hlk_sw16.protocol import SW16Protocol
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_NAME
from homeassistant.core import HomeAssistant

from .const import (
    CONNECTION_TIMEOUT,
    DEFAULT_KEEP_ALIVE_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_RECONNECT_INTERVAL,
    DOMAIN,
)
from .errors import AlreadyConfigured, CannotConnect

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
    }
)


async def validate_input(hass: HomeAssistant, host, port):
    try:
        reader, writer = await asyncio.open_connection(host, port, loop=hass.loop)
        writer.write(SW16Protocol.format_packet(b"\x1e"))
        await writer.drain()
        response = await reader.readuntil(b'\xdd')
        packet = response.split(b'\xdd', 1)[0]
        valid = SW16Protocol._valid_packet(packet)
        print(f"response: {response}, packet: {packet}, valid: {valid}")
        writer.close()
        await writer.wait_closed()
        if valid:
            return True, None
        else:
            return False, CannotConnect
    except asyncio.TimeoutError:
        print("Could not connect due to timeout error.")
        return False, CannotConnect
    except OSError as exc:
        print("Could not connect due to error: %s",
                            str(exc))
        return False, CannotConnect
    except Exception as e:
        print(f"connection failed: {e} type: {type(e)}")


class SW16FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a HLK-SW16 config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_import(self, user_input):
        """Handle import."""
        validate = validate_input(self.hass, user_input[CONF_HOST], user_input[CONF_PORT])
        result, reason = await self.hass.async_add_executor_job(validate)
        if result == True:
            print("creating")
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)
        elif result == False and reason == CannotConnect:
            print("cannot connect")
            return self.async_abort(reason="cannot_connect")
        elif result == False and reason == AlreadyConfigured:
            print("already configured")
            return self.async_abort(reason="already_setup")
        print("fall through")
        
    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                await validate_input(self.hass, user_input[CONF_HOST], user_input[CONF_PORT])
                print("validated")
                address = f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
                return self.async_create_entry(title=address, data=user_input)
            except AlreadyConfigured:
                errors["base"] = "already_configured"
            except CannotConnect:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
