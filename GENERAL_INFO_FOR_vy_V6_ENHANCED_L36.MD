## INFO FOR THE VY V6 ENHANCED L36 BIN AND PORTING FROM STOCK 92118883 AND VS VT VX V6 TO VY ENHANCED V6 1.0V

NO HARD paths — just names of bins and xdf, xmls and where to get them (urls where possible).

---

### Hardware Specifications

| Detail | Value |
|--------|-------|
| **ECU Manufacturer** | GM Delco / Delphi |
| **ECU Type** | Flash PCM (Powertrain Control Module) |
| **Processor** | Motorola 68HC11 |
| **BIN Size** | 131,072 bytes (128 KB) |
| **BASEOFFSET** | 0x0 (no offset — file addresses match directly) |
| **Engine** | L36 3800 Series II V6, 3.8L OHV, naturally aspirated |
| **Fuel System** | Sequential multi-port injection, MAF-based |
| **MAF Sensor** | Hot-wire mass airflow |
| **Throttle Control** | Cable (mechanical — NOT drive-by-wire) |
| **Lambda Control** | 2 × O2 sensors (1 pre-cat, 1 post-cat — narrowband stock, wideband with upgrade) |
| **Communication** | ALDL (GM serial diagnostic link) |

### PCM Part Numbers

| PCM Box Code | ECU Code | Application |
|--------------|----------|-------------|
| **09356445** | — | VX/VY Flash PCM (general V6) |
| **16269238** | $060A | VY Series I, underfloor catalytic converters |
| **16269268** | $060B | VY Series II, close-coupled catalytic converters (2004+) |
| **16233396** | $07A/$07B | VY Supercharged L67 |

### ECU Codes and OS Variants

| ECU Code | Engine | Cat Config | Notes |
|----------|--------|-----------|-------|
| **$060A** | L36 3.8L V6 NA | Underfloor cats | VY Series I — primary tuning target |
| **$060B** | L36 3.8L V6 NA | Close-coupled cats | VY Series II (Dec 2003+) |
| **$07** | L67 3.8L V6 Supercharged | — | VY Supercharged (different maps entirely) |

### Calibration IDs ($060A — VY Series I)

| Cal ID | Trans | PCM Box Code | Notes |
|--------|-------|-------------|-------|
| **92118883** | Auto | 16269238 | Pre-production / early release — commonly used as stock base |
| **92118885** | Auto | 16269238 | Start of production (domestic) |
| **92118886** | Manual | 16269238 | Start of production |
| **92118889** | Manual | 16269238 | — |

### Calibration IDs ($060B — VY Series II)

| Cal ID | Trans | PCM Box Code | Notes |
|--------|-------|-------------|-------|
| 92161296 | Auto | 16269268 | Superseded |
| **92162167** | Auto | 16269268 | Main Series II calibration |
| 92163399 | Manual | 16269268 | — |
| 92169212 | Manual | 16269268 | SOP Dec 2003 Sedan |
| 92169213 | Manual | 16269268 | SOP Dec 2003 UTE |
| 92169214 | Auto | 16269268 | Series I 1-Tonner/Crewman, low-speed TCC fix |
| 92171287 | Auto | 16269268 | TCC 130 variant |
| 92209180 | Auto | 16269268 | Crewman high-speed TCC |
| 92211726 | Auto | 16269268 | Series II 1-Tonner/Crewman Jan 2004 |

### Key Identification Scalars (read from BIN)

| Field | Typical Value ($060A) |
|-------|----------------------|
| EPROM ID | 0x077E |
| BCC ID | 0x30334130 |
| SOFTWARE ID | 0xAA0A |
| APPLICATION ID | 305 |
| PROGRAM ID (PCM Box Code) | 16269238 |
| CALIBRATION ID | 92118883 |
| TRANSMISSION ID | 0x7FC1 |

### XDF Definition Files

#### Stock XDFs
| File | ECU Code | Notes |
|------|----------|-------|
| `VY V6_$060A v2.62.xdf` | $060A | Stock community XDF |
| `VY V6_$060A v2.63.xdf` | $060A | Latest stock version |
| `VY V6_$060B v2.41.xdf` | $060B | Series II |
| `VY_L67_V1.95_$07.xdf` | $07 | Supercharged |

#### Enhanced XDFs (from pcmhacking.net — by "The1")
| File | Tables | Notes |
|------|--------|-------|
| **`VX VY_V6_$060A_Enhanced_v2.09b.xdf`** | 1,880 | **Recommended** — latest Enhanced version |
| `VY_V6_$060A_Enhanced_v1.2.xdf` | — | Older version |
| `VY_V6_$060A_Enhanced_v0.9h.xdf` | — | Early version |
| `VX VY_V6_SC_$07_Enhanced_v2.6i.xdf` | — | Supercharged enhanced |

**Where to get:** pcmhacking.net forums (registered users — free).

#### Enhanced BIN Files
| File | Notes |
|------|-------|
| `VX-VY_V6_$060A_Enhanced_v1.0a_first_gear_hold_patch.bin` | Enhanced OS + 1st gear hold |
| `VX-VY_V6_$060A_Enhanced_v1.0a.bin` | Base Enhanced OS |

**Important:** Enhanced BINs require Enhanced XDFs — stock XDFs will NOT display correct values with Enhanced BINs.

### Enhanced Mod — What It Changes

The "Enhanced" OS mod (by The1 from pcmhacking.net) extends the PCM firmware to support:

| Feature | Stock Limit | Enhanced Limit |
|---------|-------------|----------------|
| **MAF software limit** | 10,082 Hz / 256 g/s | 16,226 Hz / 510 g/s |
| **CYLAIR tuning range** | 850 mg/cyl | 1,650 mg/cyl |
| **Table count** | Fewer | 1,310 const, 330 tables, 351 flags, 3 patches |
| **Boost support** | None | Supported (extended VE, fueling, spark tables) |
| **Additional AIR tables** | None | Extra spark, fuel, and timing tables for forced induction |

**CLI Editor XDF stats (Enhanced v2.09a):**
- 1,310 constants (scalars)
- 330 tables (2D maps)
- 351 flags (bit flags)
- 3 patches (code patches — SKIP ONLY during porting)

### Load Axis and Formulas

| Parameter | Value |
|-----------|-------|
| **Load unit** | CYLAIR50 (mg/cyl × 50) |
| **Load range** | 50 – 850 (stock), 50 – 1650 (Enhanced) |
| **Spark formula** | degrees = X / 256 × 90 − 35 |
| **Injector offset formula** | ms = X / 260 / 256 × 1000 |
| **Stock PE (Power Enrichment) AFR** | 12.80:1 |
| **DTC base address** | 0x56D2 |

### Key Calibration Maps

#### Fueling
| Map Name (XDF) | Description |
|-----------------|-------------|
| Commanded AFR Table | Target AFR by RPM × CYLAIR |
| Injector Flow Rate | Injector characterization (cc/min or lb/hr) |
| Injector Offset (Deadtime) | Deadtime vs battery voltage |
| PE Enable | Power Enrichment activation threshold (by CYLAIR/TPS) |
| PE AFR Target | AFR target during power enrichment |
| MAF Calibration Table | MAF Hz → g/s transfer function |
| BLM / Fuel Trims | Long-term and short-term fuel trim cells |

#### Ignition
| Map Name (XDF) | Description |
|-----------------|-------------|
| Main Spark Table | Spark advance by RPM × CYLAIR — **primary tuning target** |
| Adaptive Spark Table | ECU-learned timing adjustments (overlay on main table) |
| Knock Retard Scalar | Maximum knock retard allowed |
| Knock Recovery Rate | How fast timing returns after knock event |

#### Idle
| Map Name (XDF) | Description |
|-----------------|-------------|
| Idle Speed Table | Target idle RPM by coolant temp |
| IAC (Idle Air Control) Steps | Stepper motor position by temp |

#### Transmission (Auto)
| Map Name (XDF) | Description |
|-----------------|-------------|
| Shift Points | Upshift/downshift RPM by throttle position |
| TCC (Torque Converter Clutch) | Lock/unlock conditions |
| Line Pressure | Transmission line pressure by load |

### VS → VY Porting Differences

| Parameter | VS V6 ($51) | VY V6 ($060A) |
|-----------|------------|---------------|
| **Load axis** | MGS (93–593) | CYLAIR50 (50–850) |
| **Spark formula** | degrees = X × 0.351565 | degrees = X/256 × 90 − 35 |
| **Injector offset** | ms = X / 65.536 | ms = X / 260 / 256 × 1000 |
| **PE enable** | TPS % threshold | MGC (mg/cyl) threshold |
| **DTC base address** | 0x35E2 | 0x56D2 |
| **XDF element count** | 681 const, 257 tables, 349 flags | 1,310 const, 330 tables, 351 flags |

**Porting rules:** When porting VS→VY, the CLI editor must:
1. Resample tables to match the different CYLAIR axis breakpoints
2. Convert spark values between the two formulas
3. Skip patches (firmware-specific code mods are not portable)
4. Handle load unit conversion (MGS → CYLAIR50)

### Flash Tools for VY V6

| Tool | Protocol | Notes |
|------|----------|-------|
| **pcmhacking.net FlashTool** | ALDL | Free, open-source. Reads/writes full 128 KB BIN |
| **TunerPro RT + OSEPlugin** | ALDL (real-time) | For live viewing/datalogging via NVRAM (not flash) |
| **EFILive** | ALDL / OBD2 | Commercial. Full read/write/scan/tune |
| **HP Tuners** | OBD2 | Commercial. Full read/write/scan |
| **Delco FlashTool** | ALDL | Legacy flash tool |

**Connection:** ALDL cable (serial or USB-serial to OBD1/OBD2 connector). The VY uses the OBD2 connector but the PCM communicates via ALDL protocol (not standard OBD2 PIDs for flash operations).

### Common Modifications

| Mod | Notes |
|-----|-------|
| **MAF Rescale** | For larger MAF housing or aftermarket sensor |
| **Rev Limiter Raise** | Stock is ~6200 RPM |
| **Speed Limiter Delete** | Remove electronic speed cap |
| **DTC Suppress** | For decat, removed secondary air, etc. |
| **PE AFR Tuning** | Adjust power enrichment targets for wideband tuning |
| **Shift Point Adjustment** | Higher shift points for performance (auto trans) |
| **TCC Tuning** | Earlier lockup for fuel economy, later for power |
| **Crackle/Pops Tune** | Overrun fuel settings for exhaust character |
| **1st Gear Hold Patch** | Enhanced OS only — holds 1st gear for launches |

### References

- **pcmhacking.net** — https://pcmhacking.net (Enhanced OS, flash tool, XDFs)
- **EFILive** — https://www.efilive.com (V8 Scan & Tune for Holden)
- **pcmhacking.net Forums** — Search for "VY V6 Enhanced" or "$060A"
