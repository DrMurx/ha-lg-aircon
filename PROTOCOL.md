# LG Artcool AC — IR Protocol & Broadlink Command Construction

> Status: decoded and verified against 26 captured remote presses, 2026-07.
> Purpose: reference spec for building a Home Assistant integration (climate entity)
> that synthesizes IR commands and sends them via a Broadlink RM4 mini.

## 1. Hardware Context

| Item | Detail |
|---|---|
| AC units | LG Artcool indoor units (split system) |
| Remote | LG, model no. **6711Z90031C** |
| IR blaster | **Broadlink RM4 mini**, integrated in HA via the native `broadlink` integration |
| Protocol family | LG 28-bit AC protocol ("LG2" in IRremoteESP8266 terms), reference implementation: [`ir_LG.h`](https://github.com/crankyoldgit/IRremoteESP8266/blob/master/src/ir_LG.h) / [`ir_LG.cpp`](https://github.com/crankyoldgit/IRremoteESP8266/blob/master/src/ir_LG.cpp) |

Key property of the protocol: **the remote transmits the full device state on every
press** (mode + temperature + fan in one frame). Captured key presses therefore
cannot be replayed as independent "buttons" — the frame must be synthesized from
the desired target state. Exception: a set of fixed one-shot command codes
(power off, swing, plasma, etc.), which are stateless constants.

## 2. The 28-bit Frame

Transmitted MSB-first. Bit layout (bit 27 = first transmitted):

```
 27           20 19  18 17 16 15 14    12 11     8 7      4 3      0
┌───────────────┬──────┬──────────┬────────┬────────┬────────┬───────┐
│  Sign = 0x88  │ Power│  (flags) │  Mode  │  Temp  │  Fan   │  Sum  │
│    8 bits     │ 2 b  │   3 b    │  3 b   │  4 b   │  4 b   │  4 b  │
└───────────────┴──────┴──────────┴────────┴────────┴────────┴───────┘
```

### Fields

| Field | Bits | Values |
|---|---|---|
| **Sign** | 27–20 | Always `0x88` |
| **Power** | 19–18 | `0` = normal state command; `3` = one-shot command family `0x88C....` (incl. power off) |
| **Flags** | 17–15 | Bit 15: see §2.1. Bit 16 set (with Power=0) marks the `0x881....` one-shot family (swing/jet). Bit 17: never observed set. |
| **Mode** | 14–12 | `0` Cool · `1` Dry · `2` Fan only · `3` Auto (AI) · `4` Heat |
| **Temp** | 11–8 | `temp_nibble = target_°C − 15`. Observed range on this remote: 18–30 °C (Cool), up to 30 °C (Heat). In **Auto** mode this nibble is *not* a temperature — it's an adjustment level (observed value `2`, presumably center of a −2…+2 scale). |
| **Fan** | 7–4 | `0` Quiet/Lowest · `2` Medium · `4` High · `5` Auto (observed set). `1` = Low exists in the reference implementation but was not observed in this remote's fan cycle (Quiet → Med → High → Auto). |
| **Sum** | 3–0 | Checksum, see below |

### Checksum

Sum of the four nibbles above the Sum nibble, modulo 16:

```python
sum_nibbles = ((v >> 4) & 0xF) + ((v >> 8) & 0xF) + ((v >> 12) & 0xF) + ((v >> 16) & 0xF)
checksum = sum_nibbles & 0xF
```

(Equivalent to IRremoteESP8266's `sumNibbles(state >> 4, 4)`.) Verified against
all 26 captures — zero mismatches.

### 2.1 Bit 15 — power-on vs. running-state flag

Empirical finding, **not documented in IRremoteESP8266**:

- The **Power ON** press (unit was off) transmitted the state frame with **bit 15 = 0**
  (`0x880064A` = Cool/21 °C/High).
- **Every** subsequent adjustment while running (temp, fan, mode) transmitted
  **bit 15 = 1** (`0x8808xxx` pattern).

Recommendation for the integration: replicate the remote's behavior —
send bit 15 = 0 when transitioning from off → on, bit 15 = 1 for all state
changes while the unit is on. (Untested whether the unit actually distinguishes
them; mirroring the remote is the safe default.)

### 2.2 State frame construction (normative)

```python
def build_state(mode: int, temp_c: int, fan: int, power_on: bool = False) -> int:
    v = 0x88 << 20
    if not power_on:
        v |= 1 << 15                      # running-state flag, see §2.1
    v |= (mode & 0x7) << 12
    v |= ((temp_c - 15) & 0xF) << 8
    v |= (fan & 0xF) << 4
    s = ((v >> 4) & 0xF) + ((v >> 8) & 0xF) + ((v >> 12) & 0xF) + ((v >> 16) & 0xF)
    return v | (s & 0xF)
```

There is **no "power on" bit as such** — any valid state frame switches the unit
on. Switching **off** uses the fixed one-shot code below.

## 3. Fixed One-Shot Command Codes (all verified on this unit)

| Function | Code | Semantics |
|---|---|---|
| **Power OFF** | `0x88C0051` | discrete (matches `kLgAcOffCommand`) |
| Jet Cool ("power cooling") | `0x8810089` | one-shot; unit self-sets Cool / 18 °C / fan High — subsequent state frames from the remote reflected that state |
| Swing V toggle | `0x8810001` | **toggle, stateful** (matches `kLgAcSwingVToggle`) |
| Swing H toggle (horizontal vane) | `0x8813004` | **toggle, stateful**; not present in IRremoteESP8266 |
| Plasma ON | `0x88C000C` | discrete |
| Plasma OFF | `0x88C0084` | discrete |
| Auto clean ON | `0x88C00B7` | discrete |
| Auto clean OFF | `0x88C00C8` | discrete |
| Light/LED toggle | `0x88C00A6` | toggle, stateful (matches `kLgAcLightToggle`) |

Integration implications:

- Plasma and auto clean can be modeled as **real switches** (deterministic on/off codes).
- Swing V, swing H, and light are IR **toggles**: HA can only track them
  optimistically (assumed state; drifts if the physical remote is used).
- Power off is discrete, so `climate.turn_off` is deterministic.

## 4. IR Physical Layer

- Carrier: 38 kHz (standard LG; the RM4 default for learned/sent codes).
- Frame: header mark/space, 28 data bits (pulse-distance coding), trailing mark, long gap.

Timings as measured from this remote (Broadlink tick = **32.84 µs**):

| Element | Ticks | µs (approx.) |
|---|---|---|
| Header mark | 269 (`0x010D`) | 8 834 |
| Header space | 136 (`0x88`) | 4 466 |
| Bit mark | 17 (`0x11`) | 558 |
| Space "0" | 17 (`0x11`) | 558 |
| Space "1" | 53 (`0x35`) | 1 741 |
| Trailing mark | 17 (`0x11`) | 558 |
| End gap | 3333 (`0x0D05`) | 109 460 |

(Capture jitter was ±1–2 ticks per element; the canonical values above decode
identically and are what the encoder should emit.)

## 5. Broadlink Packet Format

The HA `broadlink` integration sends raw command packets, base64-encoded:

```
byte 0      0x26            (IR marker; 38 kHz)
byte 1      0x00            (repeat count: 0 = send once)
bytes 2–3   uint16 LE       length of the pulse data that follows, in bytes
bytes 4…    pulse data      alternating mark/space durations in ticks (32.84 µs)
```

Pulse-duration encoding: one byte per duration if ≤ 255 ticks; durations > 255
ticks are escaped as `0x00` followed by a **big-endian uint16** (used here for
the header mark and the end gap).

A full LG frame is exactly **64 pulse bytes**: 4 (header, incl. escape) +
56 (28 bits × mark+space) + 1 (trailing mark) + 3 (end gap, escaped) → total
packet 68 bytes → base64.

## 6. Reference Encoder (verified round-trip against all captures)

```python
import base64

TICK = 32.84
HDR_MARK, HDR_SPACE = 269, 136
BIT_MARK, ZERO_SPACE, ONE_SPACE = 17, 17, 53
END_GAP = 0x0D05

def _emit(ticks: int) -> bytes:
    if ticks > 255:
        return bytes([0x00, ticks >> 8, ticks & 0xFF])
    return bytes([ticks])

def encode_broadlink(value: int, bits: int = 28) -> str:
    """28-bit LG value -> Broadlink base64 packet."""
    pulses = bytearray()
    pulses += _emit(HDR_MARK) + _emit(HDR_SPACE)
    for i in range(bits - 1, -1, -1):
        pulses += _emit(BIT_MARK)
        pulses += _emit(ONE_SPACE if (value >> i) & 1 else ZERO_SPACE)
    pulses += _emit(BIT_MARK)
    pulses += _emit(END_GAP)
    packet = bytes([0x26, 0x00, len(pulses) & 0xFF, len(pulses) >> 8]) + bytes(pulses)
    return base64.b64encode(packet).decode()
```

Worked example — Cool / 21 °C / fan High (running state):

```
build_state(mode=0, temp_c=21, fan=4)  ->  0x8808642
encode_broadlink(0x8808642)            ->
JgBAAAABDYgRNRERERERERE1ERERERERERERERERERERNRERERERERERETURNRERERERNRERERERERERETUREREADQU=
```

## 7. Sending via Home Assistant

Target device: the RM4 mini's `remote` entity from the `broadlink` integration.
Raw packets are sent with the `b64:` prefix:

```yaml
service: remote.send_command
target:
  entity_id: remote.rm4_mini
data:
  command: "b64:JgBAAAABDYgRNRERERE..."
```

Integration architecture recommendation:

- A `climate` entity (hvac_mode, target_temperature, fan_mode) that computes the
  28-bit value per §2.2, encodes per §6, and sends on every state change.
  `turn_off` sends `0x88C0051`; `turn_on` / first state change from off sends
  the state frame with bit 15 = 0.
- `switch` entities for plasma and auto clean (discrete codes).
- Optimistic `switch`/`button` entities for swing V, swing H, light (toggles).
- The entity must be **optimistic / assume-state** throughout: IR is
  transmit-only, there is no feedback channel. State drifts if the physical
  remote is used in parallel.

## 8. Constraints, Open Points, Caveats

1. **Auto (AI) mode**: temp nibble is an offset level, not °C (observed `2`,
   fan `5`). Do not map HA target temperature into Auto mode; either hide the
   temperature in Auto or expose the raw −2…+2 level (unverified scale).
2. **Fan value `1` (Low)** and **mode `2` (Fan only)** exist in the reference
   implementation but were not observed from this remote. Codes would checksum
   correctly; whether the unit accepts them is untested.
3. **Temperature limits**: LG typically clamps Cool to 18–30 °C and Heat to
   16–30 °C. The encoder should clamp accordingly; the temp nibble can encode
   15–30 °C.
4. **Swing** semantics are toggle-only at the IR level — no absolute vane
   positioning codes were found on this remote (the per-position `0x8813xxx`
   codes from other LG models may or may not work; untested).
5. **Jet Cool** overrides mode/temp/fan on the unit; after sending it, the
   integration should update its assumed state to Cool / 18 °C / High.
6. **Repeat byte** in the Broadlink packet is `0x00` (single transmission),
   matching the remote's behavior for short presses.

## 9. Evidence: Full Capture Decode Table

All checksums valid. Captured via HA Broadlink remote learning, 2026-07.

| Cmd | Value | Decoded | Button pressed (confirmed by user) |
|---|---|---|---|
| 1 | `0x880064A` | Cool 21 °C fan High, bit15=0 | Power ON |
| 2 | `0x8808743` | Cool 22 °C fan High | Temp + |
| 3 | `0x8808642` | Cool 21 °C fan High | Temp − |
| 4 | `0x8808653` | Cool 21 °C fan Auto | Fan cycle |
| 5 | `0x880860E` | Cool 21 °C fan Quiet | Fan cycle |
| 6 | `0x8808620` | Cool 21 °C fan Medium | Fan cycle |
| 7 | `0x8808642` | Cool 21 °C fan High | Fan cycle |
| 8 | `0x8810089` | one-shot | Jet Cool ("power cooling") |
| 9 | `0x880834F` | Cool 18 °C fan High | state after Jet Cool |
| 10 | `0x880B252` | Auto lvl 2, fan Auto | Mode cycle |
| 11 | `0x8809801` | Dry 23 °C fan Quiet | Mode cycle |
| 12 | `0x880CF4F` | Heat 30 °C fan High | Mode cycle |
| 13 | `0x880834F` | Cool 18 °C fan High | Mode cycle (back to Cool) |
| 14–16 | `0x8810001` | one-shot ×3 | Swing V toggle |
| 17–19 | `0x8813004` | one-shot ×3 | Swing H toggle (horizontal vane) |
| 20 | `0x88C000C` | one-shot | Plasma ON |
| 21 | `0x88C0084` | one-shot | Plasma OFF |
| 22 | `0x88C00B7` | one-shot | Auto clean ON |
| 23 | `0x88C00C8` | one-shot | Auto clean OFF |
| 24–25 | `0x88C00A6` | one-shot ×2 | Light toggle |
| — | `0x88C0051` | one-shot | Power OFF (confirmed separately) |