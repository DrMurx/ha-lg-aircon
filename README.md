# LG Aircon (IR) for Home Assistant

Control LG Artcool air conditioners over infrared, through Home Assistant's
native **`infrared` platform** (new in HA 2026.4). Each configured unit is a
virtual `climate` device that synthesizes the LG 28-bit AC protocol frame for
every state change and transmits it via any infrared emitter entity —
Broadlink, ESPHome IR blasters, or anything else that implements the emitter
platform.

The protocol implementation was decoded from an LG remote (model
6711Z90031C) and verified against 26 captured presses; see
[PROTOCOL.md](PROTOCOL.md) for the full specification.

## Requirements

- Home Assistant **2026.4 or newer**
- An integration exposing an **infrared emitter entity** (e.g. the Broadlink
  integration for an RM4 mini, or an ESPHome device with an IR transmitter)

## Installation

### HACS (recommended)

1. HACS → *Custom repositories* → add this repository as an **Integration**.
2. Install **LG Aircon (IR)** and restart Home Assistant.

### Manual

Copy `custom_components/lg_aircon` into your `config/custom_components/`
directory and restart Home Assistant.

## Setup

*Settings → Devices & services → Add integration → LG Aircon (IR)*.
Pick a name and the infrared emitter entity that can reach the unit. Add one
entry per air conditioner; several units can share the same emitter. The
emitter can be swapped later via *Reconfigure*.

## Entities

| Entity | Function |
|---|---|
| `climate` | Modes off/auto/cool/heat/dry/fan-only, target temperature, fan speed (quiet/low/medium/high/auto), vertical + horizontal swing, preset **Jet cool** (boost) |
| `switch` Plasma purifier | Discrete IR on/off codes |
| `switch` Auto clean | Discrete IR on/off codes |
| `button` Toggle light | Display light (IR toggle without absolute on/off codes) |

Details:

- **Turning off** uses the discrete power-off code, so `climate.turn_off` is
  deterministic. Turning on resumes the last assumed mode/temperature/fan.
- **Jet cool** (preset *boost*) makes the unit self-set Cool / 18 °C / fan
  High; the entity assumes that state. Any subsequent change returns to a
  normal state frame.
- **Auto (AI) mode** has no target temperature — the unit's own logic decides;
  the temperature field is hidden in that mode.
- Temperature limits follow the active mode (Cool 18–30 °C, Heat 16–30 °C).

## Caveats

- **IR is transmit-only.** All entities are optimistic/assumed-state; if the
  physical remote is used in parallel, Home Assistant's state drifts until
  the next command re-synchronizes mode/temperature/fan (swing, plasma,
  auto-clean and light cannot be re-synchronized this way).
- **Swing** is toggle-only at the IR level. The climate entity tracks
  vertical/horizontal swing optimistically and only transmits when the
  requested state differs from the assumed one.
- **Unverified operations:** fan speed *low* and the *fan-only* mode exist in
  the LG reference protocol but were not observed from this remote and are
  untested on the unit. They checksum correctly and are exposed; if your unit
  ignores them, avoid them.

## Development

```sh
uv sync            # Python ≥ 3.14.2; installs HA + test tooling
uv run pytest      # protocol tests verify every captured frame bit-for-bit
uv run ruff check .
```

The `custom_components/lg_aircon/protocol/` package is pure Python with no
Home Assistant imports and mirrors the structure of the
[infrared-protocols](https://github.com/home-assistant-libs/infrared-protocols)
library — the long-term goal is contributing the protocol upstream and adding
an air-conditioner device type to the core `lg_infrared` integration.

## License

[MIT](LICENSE)
