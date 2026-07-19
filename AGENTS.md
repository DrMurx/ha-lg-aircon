# AGENTS.md

Guidance for AI development agents working on this repository.

## What this project is

**LG Aircon (IR)** is a Home Assistant custom integration (HACS-installable)
that controls LG Artcool air conditioners over infrared, through Home
Assistant's native `infrared` platform (new in HA 2026.4). Each configured
unit is a virtual `climate` device that synthesizes the LG 28-bit AC
protocol frame for every state change and transmits it via any infrared
emitter entity — Broadlink, ESPHome IR blasters, or anything else that
implements the emitter platform.

The protocol was decoded from an LG remote (model 6711Z90031C) and verified
against 26 captured presses; see [PROTOCOL.md](PROTOCOL.md) for the full
specification. All entities are optimistic/assumed-state — IR is
transmit-only, there is no feedback channel from the unit. See `README.md`
for the full user-facing behavior.

The `custom_components/lg_aircon/protocol/` package is deliberately pure
Python with no Home Assistant imports: the long-term goal is contributing
the LG protocol to the
[infrared-protocols](https://github.com/home-assistant-libs/infrared-protocols)
library and adding an air-conditioner device type to HA core's
`lg_infrared` integration. Keep that package free of HA imports so it stays
easy to extract.

## Layout

- `custom_components/lg_aircon/` — the integration (Python 3.14.2+,
  Home Assistant 2026.4+). Key modules:
  - `protocol/` — pure-Python LG 28-bit frame encoder/decoder and fixed
    one-shot command codes (`codes.py`, `command.py`); no HA dependencies,
    mirrors the structure of the `infrared-protocols` library.
  - `entity.py` — common base entity providing device info and the linked
    infrared emitter entity.
  - `climate.py` — the air conditioner entity: hvac modes, target
    temperature, fan speed, vertical/horizontal swing, Jet cool preset.
  - `switch.py` — Plasma purifier and Auto clean (discrete on/off IR codes).
  - `button.py` — display light toggle (IR toggle without absolute
    on/off codes).
  - `config_flow.py` — UI setup: name + infrared emitter entity per air
    conditioner; the emitter can be swapped later via *Reconfigure*.
  - `translations/` — `en`, `de`, `es`, `fr`, `nl`, `pt`; keep all six in
    sync when changing `strings.json`.
- `tests/` — pytest suite built on `pytest-homeassistant-custom-component`;
  protocol tests verify every captured frame bit-for-bit.
- `PROTOCOL.md` — the reference IR protocol specification (frame layout,
  checksum, fixed command codes, Broadlink packet format).
- The repo is not an installable Python package; it ships via HACS from
  `custom_components/`. `pyproject.toml` only manages the dev environment.

## Development

Dependencies are managed with [uv](https://docs.astral.sh/uv/):

```bash
uv sync            # Python >= 3.14.2; installs HA + test tooling
uv run ruff check . # lint (config in pyproject.toml)
uv run pytest -v    # protocol tests verify every captured frame bit-for-bit
```

## Conventions

- **Keep `protocol/` HA-free**: no imports from `homeassistant.*` in
  `custom_components/lg_aircon/protocol/` — it is meant to be lifted
  wholesale into `infrared-protocols` eventually.
- **Version bump on every component change**: whenever anything under
  `custom_components/lg_aircon/` changes — or a dependency changes
  (manifest `requirements`, `pyproject.toml`/`uv.lock`) — bump the version
  in `pyproject.toml` and `custom_components/lg_aircon/manifest.json`; keep
  both identical.
- **Keep the README updated**: whenever a change adds, removes, or alters
  user-facing behavior (entities, modes, caveats), update `README.md` in
  the same commit.
- **Keep PROTOCOL.md updated**: whenever new IR codes or protocol details
  are decoded/verified, record them there with the evidence (capture
  values, confirmed button presses).
- **Commit per working milestone**: no commits for intermediate debug
  steps.
- Every new IR code or protocol behavior should be backed by a captured,
  checksum-verified frame before being wired into an entity — this
  integration is transmit-only and unverifiable operations must be called
  out (see PROTOCOL.md §8 / README Caveats).
- Releases are GitHub releases tagged `v<version>`, which HACS installs
  from.
