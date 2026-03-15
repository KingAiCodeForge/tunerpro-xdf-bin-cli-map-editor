## INFO FOR THE MS45 BIN AND XDF, MS45.0 AND MS45.1 DIFFERENCES, AND ACROSS FIRMWARES

NO HARD paths — just names of bins and xdf, xmls and a2ls and where to get them.

---

### Hardware Specifications

| Detail | Value |
| ------ | ----- |
| **ECU Manufacturer** | Siemens |
| **ECU Model** | MS45 (MS45.0 = non-US / E46 330i, MS45.1 = US market) |
| **Processor** | Infineon C167CS (16-bit) — BMW training manual says "two 32-bit microprocessors" but this describes the dual-MCU architecture (main + monitoring) |
| **Flash Chip** | 1 MB (1,048,576 bytes = 1024 KB) |
| **Total BIN Size** | 1,048,576 bytes (1024 KB) — **double** the MS42/MS43 |
| **Partial BIN Size** | ~116–128 KB (calibration only, 0x40000–0x5CF7F) |
| **Engine Family** | BMW M54 inline-6 (double VANOS) — same engines as MS43 |
| **Throttle Control** | Drive-by-wire (EDK electronic throttle) + Idle Air Actuator (ZWD) |
| **MAF Sensor** | Bosch HFM5 hot-film |
| **Lambda Control** | MS45.0: 4× narrowband (2 pre-cat, 2 post-cat). **MS45.1: wideband pre-cat** |
| **Communication** | **PT-CAN bus** (NOT K-line DS2 like MS42/MS43) |
| **Pin Connector** | 134 pins — 5 modular connectors (X60001–X60005: 9+24+52+40+9 pins) |
| **Byte Order** | MSB_FIRST (big-endian, Motorola format) |
| **Production** | MY2003 E85 Z4, MY2004 E83 X3 |

### Dual Processor Architecture

The MS45 uses two MCUs on a single PCB:

| Processor | Controls |
| --------- | -------- |
| **Primary** | Engine load, electronic throttle, idle actuator, ignition, knock control |
| **Secondary** | Air/fuel mixture, emission control, misfire detection, evaporative leak detection |

### Memory Layout

| Start | End | Section | Size |
| ----- | --- | ------- | ---- |
| 0x00000 | 0x01FFF | Boot sector | 8 KB |
| 0x02000 | 0x0FFFF | Program area (part 1) | 56 KB |
| 0x10000 | 0x1FFFF | Program area (part 2) + HW/SW ID at 0x1F982 | 64 KB |
| 0x20000 | 0x3FFFF | Program area (part 3) | 128 KB |
| **0x40000** | **0x5CBFF** | **Calibration data** (A2L-mapped region) | **~117 KB** |
| 0x5CC00 | 0x7FFFF | Additional cal/variant data | ~147 KB |
| 0x80000 | 0xFFFFF | Program area (lower bank) | 512 KB |

**BASEOFFSET:** For 1024K (full) XDFs, addresses are absolute — no offset needed. For 116K (partial) XDFs, subtract 0x40000 from A2L addresses to get XDF offsets.

### Checksums

The MS45 uses a fundamentally different checksum system from MS42/MS43:

| Type | Address | Covers | Notes |
| ---- | ------- | ------ | ----- |
| **CRC32** | 0x40100 | 0x40200–0x5CFFF | Polynomial: 0x04C11DB7, init 0xFFFFFFFF, no reflection, XOR out 0x00000000 |
| **RSA Signature** | 0x40170 | 0x40000–0x4016F + 0x40200–0x5CFFF | **Required for OBD flashing** — flash tools must generate valid RSA |

**Disabling CRC32 (development only):** Set `val_mo3_swi_cal_cks` → `0xA5`.

**Critical difference from MS42/MS43:** The RSA signature requirement means you cannot simply hex-edit and flash via OBD. Flash tools (MS45 Flasher, Quickflash) handle RSA generation automatically.

### Firmware Versions

| ECU | Firmware | Markets | Notes |
| --- | -------- | ------- | ----- |
| **MS45.0** | **4560BN02S** (also written 456BO02S) | EU, rest-of-world, E46 330i | Narrowband pre-cat O2 |
| **MS45.1** | **457LO02S** | US only | **Wideband pre-cat O2** — XDFs NOT interchangeable with MS45.0 |

**Critical rule:** MS45.0 and MS45.1 are NOT interchangeable. They use different O2 sensor strategies. Never use an MS45.0 XDF on an MS45.1 BIN or vice versa.

### XDF Definition Files

| File | ECU | Type | Notes |
| ---- | --- | ---- | ----- |
| `Siemens_MS450_456BO02S_1024K.xdf` | MS45.0 | Full 1 MB bin | **Recommended for full flash** |
| `Siemens_MS450_456BO02S_116K.xdf` | MS45.0 | Partial 116 KB | For partial cal reads |
| `Siemens_MS451_457LO02S_1024K.xdf` | MS45.1 | Full 1 MB bin | **Recommended for MS45.1** |
| `Siemens_MS451_457LO02S_116K.xdf` | MS45.1 | Partial 116 KB | For partial cal reads |
| `MS45.xdf` | Unknown | Legacy | In DAMOS folder |

### BIN Files (Where to Get)

| Source | What | Notes |
| ------ | ---- | ----- |
| **ms4x.net → Flash Files** | Community flash files by engine/market/chassis | Free, checksummed |
| **MS45 Flasher → Read ECU** | Your ECU's BIN (full or partial ~116 KB) | Via CAN bus |
| **WinkFP** (BMW Standard Tools) | Full flash read/write via SP-Daten | For service/coding operations |
| **BDM100 / Galletto** | Direct chip read (bench flash) | For locked or dead ECUs |

### Available Engine Variants

#### MS45.0 (4560BN02S) — Non-US + E46 330i

| Engine | Displacement | Power | Chassis Applications |
| ------ | ------------ | ----- | -------------------- |
| M54B22 | 2.2L | 125 kW | E60 520i |
| M54B25 | 2.5L | 141 kW / 192 PS | E60 525i, Z4 2.5 |
| M54B30 | 3.0L | 170 kW / 231 PS | E46 330i, E39 530i, E53 X5 3.0i, E83 X3 3.0i, Z3/Z4 3.0i |

#### MS45.1 (457LO02S) — US Only

| Engine | Chassis | Notes |
| ------ | ------- | ----- |
| M54B30 | E46, E83 X3 | Standard + Performance Package + AT variants |
| M54B25 | E46 | Standard + AT variants |
| **M56B25** (SULEV) | E46 | Coupe/Sedan/Touring — ultra-low emissions variant |

### HW Number → Variant Mapping

| HW Number | ECU | Engines |
| --------- | --- | ------- |
| 5WK93014 | MS45.0 | M54B30 (E60 530i, E53 X5, X3 3.0i) |
| 5WK93016 | MS45.0 | M54B22/M54B25 (E60 520i/525i) |
| 5WK93018 | MS45.0 | M54B30 (E83 X3 3.0i, E85 Z4 3.0si) |
| 5WK93020 | MS45.0 | M54B25 (E61/X3 2.5) |
| 5WK93022 | MS45.0/1 | M54B30 (late Z4) |

### Key Calibration Maps

The MS45 uses mixed naming conventions — `ip_*`, `id_*`, `c_*`, `kf_*` prefixes appear.

#### Fueling

| Map Name | Description |
| -------- | ----------- |
| `ip_ti_bas` | Base injection time |
| `ip_ti_fl` | Full-load enrichment |
| `ip_td__vb` | Injector deadtime vs battery voltage |
| `ip_fac_*` | Injection correction factors |

#### Ignition

| Map Name | Description |
| -------- | ----------- |
| `kf_iga_bas` | Base ignition timing — **main map** |
| `kf_iga_knk` | Knock retard table |
| `ip_iga_*` | Ignition timing variants (cold, warm, idle, part-load) |

#### VANOS

| Map Name | Description |
| -------- | ----------- |
| `kf_vanos_*` | Variable valve timing setpoints (intake + exhaust) |

#### Limiters

| Map Name | Description |
| -------- | ----------- |
| `c_n_max_*` | RPM limiter scalars |
| `c_v_max` | Speed limiter |

#### Load / Airflow

| Map Name | Description |
| -------- | ----------- |
| `ip_maf_*` | MAF correction tables |
| `ip_tps_*` | Throttle position tables |
| `ip_put_sp` | Boost/load target |

#### MS45-Specific Features (not on MS42/MS43)

| Map Name | Description |
| -------- | ----------- |
| Exhaust flap maps | Switching thresholds by gear group (AT/MT), addresses in $4FDxx range |
| Sound flap (SOF) maps | PWM control, RPM/pedal request, TIA/VB correction — "Sport" button |
| `c_tco_sp_*` | Coolant temperature setpoints (MAP thermostat control) |
| Resonance/turbulence flap | Intake flap transition at ~3750 RPM — not present on MS42/MS43 |

### Unique MS45 Systems

#### Resonance-Turbulence Intake
The MS45 controls a resonance flap in the intake manifold that switches at approximately 3750 RPM to optimize torque curve characteristics. Not present on MS42/MS43.

#### DMTL (Diagnostic Module Tank Leakage)
Evaporative leak detection pump controlled by the ECM. The ECM maintains relay power up to **3 minutes after key-off** to complete the DMTL test cycle.

#### Dynamic Driving Control ("Sport" Mode)
Sound flap control and throttle response modification activated via the Sport button. Controls exhaust sound flap PWM duty cycle based on RPM and pedal position.

#### MAP Thermostat
Electronic coolant thermostat controlled by the ECM via `c_tco_sp_*` setpoints — more sophisticated than the MS42's simpler e-thermostat setup.

### Flash Tools

**IMPORTANT:** The MS4x Flasher does NOT support MS45. It only supports MS42/MS43.

| Tool | Protocol | Read | Write | Checksum/RSA | Notes |
| ---- | -------- | ---- | ----- | ------------ | ----- |
| **MS45 Flasher** (terraphantm) | CAN bus (INPA K+DCAN, 1ms latency) | Full/Partial | Full/Partial | Auto CRC32 + RSA | Free (GPL v3). **Recommended** |
| **MS45 Quickflash** v2.67 (BTT) | CAN bus (FT232RL FTDI) | Full/Partial | Full/Partial | Auto + EWS delete | $39 |
| **MS45 DME Unlock** | INPA K+DCAN (1ms latency) | — | — | Auto + RSA | Free (GPL v3). Unlocks locked ECUs |
| **WinkFP** (BMW Standard Tools) | K-line or CAN via OBD2 | Full | Full | Via SP-Daten | Free with BMW Tools package |
| **BDM100 / Galletto** | Direct BDM (bench) | Full | Full | Manual | For locked/dead ECUs |

**Connection:** K+DCAN cable with **1ms latency** required for MS45 Flasher. Standard INPA cables with slower latency may fail.

### MS42/MS43 → MS45 Comparison

| Feature | MS42 | MS43 | MS45 |
| ------- | ---- | ---- | ---- |
| Flash size | 512 KB | 512 KB | **1024 KB (1 MB)** |
| Cal size | 32 KB | 64 KB | **~117 KB** |
| BASEOFFSET | 0x48000 | 0x70000 | **0x40000** |
| Checksum type | 3× CRC16 | 3× CRC16 + 2× 32-bit sum | **CRC32 + RSA signature** |
| Communication | K-line (DS2) | K-line (DS2) | **CAN bus (PT-CAN)** |
| Processor | C167CR-SR | C167CR-LM | **C167CS** |
| Flash tool | MS4x Flasher | MS4x Flasher | **MS45 Flasher / Quickflash** |
| Patchlist | v1.7.1 (17 patches) | v2.9.2 (many more) | **None exists** |
| Custom firmware | None | MS43X | **None** |
| DAMOS params | ~1,981 | ~3,457 | **~4,057** |
| O2 sensors | Narrowband (all) | Narrowband (all) | NB (MS45.0) / **WB pre-cat (MS45.1)** |
| Byte order | MSB_FIRST | MSB_FIRST | MSB_FIRST |

### No Patchlist / No Custom Firmware

Unlike MS42 (patchlist v1.7.1) and MS43 (patchlist v2.9.2 + MS43X custom firmware), the MS45 has **no community patchlist and no custom firmware**. Modifications are limited to calibration data edits via XDF files.

This makes the MS45 less flexible for forced-induction builds. The RSA signature requirement also adds complexity to the flash process.

### References

- **ms4x.net wiki** — https://www.ms4x.net/index.php?title=Siemens_MS45
- **MS45 Flasher** — https://www.ms4x.net/index.php?title=MS45_Flasher
- **Flash Files MS45** — https://www.ms4x.net/index.php?title=Flash_Files_MS45
- **Firmware Files** — https://www.ms4x.net/index.php?title=Firmware_Files
- **MS45 WinkFP Flash Files** — local doc: `1bmw_ms42_tuning_guides/MS45_WinkFP_Flash_Files_and_Combining_Partials.md`
- **E60 525i XDF Strategy** — local doc: `1bmw_ms42_tuning_guides/E60_525i_MS45_XDF_Strategy.md`
- **BMW Training Manual** — local doc: `02_MS45.md` (21,518 words, converted from PDF)

### Local Reference Files

| File | Content |
| ---- | ------- |
| `1bmw_ms42_tuning_guides/ms45_damos/4520D30S.a2l` | DAMOS A2L — MS45.0 E46 330i (M54B30) |
| `1bmw_ms42_tuning_guides/ms45_damos/4560I00S.A2L` | DAMOS A2L — MS45.0 E60/Z4 era, **best for E60 525i** |
| `1bmw_ms42_tuning_guides/ms45_damos/456BG23P.a2l` | DAMOS A2L — MS45.0 market variant |
| `1bmw_ms42_tuning_guides/ms45_damos/457LG23P.a2L` | DAMOS A2L — **MS45.1** (US wideband O2) |
| `1bmw_ms42_tuning_guides/ms45_damos/6m661411.A2L` | DAMOS A2L — **11.8MB**, largest MS45 A2L, likely full Damos with extended parameter set |
| `1bmw_ms42_tuning_guides/ms45_damos/If_ccp4.a2l` | CCP interface A2L — defines CAN Calibration Protocol measurement channel IDs for CAN-based logging |
| `1bmw_ms42_tuning_guides/ms45_damos/if_kwp6.a2l` | KWP interface A2L — defines KWP2000 measurement IDs for diagnostic logging (directly needed for TunerPro ADX) |
| `1bmw_ms42_tuning_guides/ms45_damos/Ms45damos.csv` | Complete parameter database — 4,057 entries |
| `1bmw_ms42_tuning_guides/MS45_WinkFP_Flash_Files_and_Combining_Partials.md` | WinkFP flash procedure + partial BIN combining |
| `1bmw_ms42_tuning_guides/E60_525i_MS45_XDF_Strategy.md` | XDF strategy, memory map, A2L properties |
| `1bmw_ms42_tuning_guides/COMPATIBILITY_MATRIX.md` | XDF/BIN/ECU compatibility rules |
