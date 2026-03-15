## INFO FOR THE MS43 BIN AND XDF AND PORTING TO MS43X, AND ACROSS FIRMWARES. EU2 SETTINGS FROM MS4X AND OTHER FINDINGS

NO HARD paths — just names of bins and xdf, xmls and a2ls and where to get them.

---

### Hardware Specifications

| Detail | Value |
|--------|-------|
| **ECU Manufacturer** | Siemens |
| **ECU Model** | MS43 |
| **Processor** | Infineon C167CR-**LM** @ 24 MHz (8 MHz crystal × 3 PLL) |
| **Flash Chip** | AMD AM29F400BB — 4 megabit (512 KB) |
| **Total BIN Size** | 524,288 bytes (512 KB) |
| **Engine Family** | BMW M54 inline-6 (double VANOS) |
| **Throttle Control** | Drive-by-wire (electronic throttle, no cable backup) |
| **MAF Sensor** | Bosch HFM5 hot-film |
| **Lambda Control** | 4 × lambda sensors (2 pre-cat, 2 post-cat) |
| **Communication** | K-line (DS2 protocol) + CAN bus |

### Memory Layout (from ms4x.net wiki)

| Start | End | Section | Size |
|-------|-----|---------|------|
| 0x00000 | 0x0FFFF | Bootloader & UIF | 64 KB |
| 0x10000 | 0x6FFFF | Program Code | 384 KB |
| **0x70000** | **0x7FFFF** | **Calibration Data** | **64 KB** |

**BASEOFFSET = 0x70000** (subtract=0 in XDF). This is different from MS42 (0x48000). The MS43 has its calibration at the END of flash, and gets double the calibration space (64 KB vs 32 KB in MS42).

**Bootloader section** (0x00000–0x0FFFF) is one-time-programmable under normal operation.

### Checksums (from ms4x.net wiki)

The MS43 uses **three CRC16 checksums** + **two 32-bit addition checksums**:

| Type | Section | Address |
|------|---------|---------|
| **CRC16** | Boot | 0x3C24 |
| **CRC16** | Program | 0x6FDE0 |
| **CRC16** | Calibration | 0x73FE0 |
| **32-bit Addition** | Program (monitor) | 0x6FDAE |
| **32-bit Addition** | Calibration (monitor) | 0x72FFC |

**Rule:** The addition checksums must be corrected BEFORE the CRC16 checksums, because the addition checksums sit inside the CRC16-protected regions.

If any checksum is wrong the ECU will NOT start the engine.

**Disabling CRC16 calibration checksum (for dev only):**
1. Set word at 0x73FFE to 0xFFFF
2. Set byte at 0x6FFB0 to 0xA8
3. Change byte at firmware-specific address from 0x84 to 0x94:

| Firmware | Address |
|----------|---------|
| 430037 | 0x58999 |
| 430055 | 0x5B87D |
| 430056 | 0x5B87F |
| 430064 | 0x5FEB3 |
| 430066 | 0x63595 |
| 430069 | 0x63595 |

### Firmware Versions

| Version | Notes |
|---------|-------|
| MS430037 | Early firmware |
| MS430055 | Older community tuning base |
| MS430056 | Old community standard (e46fanatics era) — superseded |
| MS430064 | Intermediate update |
| MS430066 | Late version |
| **MS430069** | **Latest and final** BMW release (2005). Best community support. **Recommended.** |

**Critical rule:** Firmware versions are NOT interchangeable. A 430056 calibration BIN flashed onto a 430069 ECU (or vice versa) = non-starting engine. Always match XDF to firmware.

**Upgrade path:** Any MS43 can be full-flashed to 430069 via MS4x Flasher. After upgrade, use only 430069 definition files.

### MS430069 Flash Files Available (from ms4x.net)

| Engine | Variants Available |
|--------|--------------------|
| **M54B22** (2.2L) | EU4 LHD, EU4 RHD |
| **M54B25** (2.5L) | EU4 LHD, EU4 RHD, EU4 Compact, US |
| **M54B30** (3.0L) | **EU2 LHD, EU2 RHD**, EU4 LHD, EU4 RHD, US |

**Important:** There are **no factory M52TUB25/M52TUB20 calibrations** for 430069. The M52TUB28 EU4 LHD entry on ms4x.net is community-built from MS42 data + MS45.0 prototype data.

LHD vs RHD differ in exhaust gas temperature models (different catalytic converter configuration).

Chassis applications: E46 (3-series), E39 (5-series), E53 (X5), E83 (X3), Z3, Z4.

**Alpina variants:** MS430037 was used by Alpina B3, MS430070 by Alpina Roadster. These use non-standard calibrations.

### XDF Definition Files

| File | Source | Notes |
|------|--------|-------|
| `Siemens_MS43_430069_512K_1.1.3v.xdf` | ms4x.net community | English, 512 KB, **recommended for 430069** |
| `430056_*.xdf` files | e46fanatics archive | For legacy 430056 firmware only |

**XDF contents (430069 v1.1.3v):**
- 2,256 constants (scalars)
- 1,454 tables (2D maps)
- 0 flags, 0 patches

This is significantly larger than MS42 (1,454 vs 597 tables) due to more engine variants, dual-VANOS granularity, and extended patchlist features.

### BIN Files (Where to Get)

| Source | What | Notes |
|--------|------|-------|
| **ms4x.net → Flash Files MS43** | Community 430069 flash files by engine/market | Free, checksummed |
| **MS4x Flasher → Read ECU** | Your ECU's BIN (full or 64 KB cal) | ~120s for full read |
| **JMGarage Flasher** | Boot-mode read for locked ECUs | For DS2-locked units |

### Available Engine Variants (all use MS43)

| Engine Code | Displacement | Power | Applications |
|-------------|-------------|-------|-------------|
| M54B22 | 2.2L | 125 kW / 170 PS | E46 320i/ci (post-2000), E83 X3 2.0i |
| M54B25 | 2.5L | 141 kW / 192 PS | E46 325i/ci/xi, E39 525i, E60 525i, Z4 2.5i |
| M54B30 | 3.0L | 170 kW / 231 PS | E46 330i/ci/xi, E39 530i, E53 X5 3.0i, Z3/Z4 3.0i |

### Key Calibration Maps (Siemens IVVT naming — MS43 uses different names than MS42)

#### Load Calculation (Speed Density + MAF hybrid)
| Map Name | Description |
|----------|-------------|
| `ip_maf_vo_[1-8]__map__n` | Speed-density volumetric efficiency tables (8 subranges) |
| `ip_maf_tco_cor__tco` | Coolant temp correction for speed-density output |
| `id_maf_tab` | MAF sensor calibration (voltage → kg/h) |

The MS43 uses a pre-calculated speed-density model multiplied by a MAF correction factor. Load = MAF ÷ RPM in mg/stroke.

#### Fueling
| Map Name | Description |
|----------|-------------|
| `ip_ti_tco_1_pl_ivvt_1__n__maf` | Cold engine injection time, bank 1, part-load |
| `ip_ti_tco_1_pl_ivvt_2__n__maf` | Cold engine injection time, bank 2, part-load |
| `ip_ti_tco_2_pl_ivvt_1__n__maf` | Warm engine injection time, bank 1, part-load |
| `ip_ti_tco_2_pl_ivvt_2__n__maf` | Warm engine injection time, bank 2, part-load |
| `ip_ti_fl__n` | Full-load injection time |
| `ip_ti_cat_var__n__maf` | Cat-prep injection lean-out (when no lambda sensors) |
| `ip_td__vb` | Injector deadtime vs battery voltage |

#### Ignition
| Map Name | Description |
|----------|-------------|
| `ip_iga_ron_98_pl_ivvt__n__maf` | Ignition timing, RON98, warm part/full-load — **main map** |
| `ip_iga_ron_91_pl_ivvt__n__maf` | Ignition timing, RON91, warm part/full-load |
| `ip_iga_tco_1_is_ivvt__n__maf` | Cold engine ignition, idle |
| `ip_iga_tco_1_pl_ivvt__n__maf` | Cold engine ignition, part/full-load |
| `ip_iga_tco_2_is_ivvt__n__maf` | Warm engine ignition, idle |

**Cold→warm transition:** Uses blending factors. Once at operating temp, the ECU switches to `ip_iga_ron_9*` maps for part/full load.

#### VANOS
| Map Name | Description |
|----------|-------------|
| `ip_cam_sp_in_pl__n__maf` | Intake VANOS target, part-load |
| `ip_cam_sp_in_is__n__maf` | Intake VANOS target, idle |
| `ip_cam_sp_ex_pl__n__maf` | Exhaust VANOS target, part-load |
| `ip_cam_sp_ex_is__n__maf` | Exhaust VANOS target, idle |

#### Drive-by-Wire
| Map Name | Description |
|----------|-------------|
| `ip_md_sol_tl_1_fgr__pvs_sol__n` | Throttle request, part-load, warm |
| `ip_md_sol_tl_0_fgr__pvs_sol__n` | Throttle request, part-load, cold |

#### Limiters
| Map Name | Description |
|----------|-------------|
| `ip_n_max_mt` | RPM soft limiter (manual trans) |
| `ip_n_max_max_mt` | RPM hard limiter (manual trans) |
| `c_v_max` | Speed limiter |

### Variant Configuration Switches

The MS43 uses configuration switches (`c_conf_*`) to enable/disable features per-vehicle:
- `c_conf_sap` — Secondary Air Pump (**WARNING: inverted vs MS42!** 0 = auto-learn/active, **1 = SAP deleted/not present**, 2 = present no SAFM, 3 = present with SAFM)
- `c_conf_ac` — Air Conditioning
- `c_conf_ews` — EWS Immobilizer
- `c_conf_at` — Automatic Transmission
- `c_conf_cruise` — Cruise Control
- `c_conf_ambient` — Ambient Pressure Sensor

### Common Modifications

| Mod | Maps/Scalars Affected | Notes |
|-----|----------------------|-------|
| **SAP Delete** | `c_conf_sap` = **1** (NOT 0! Value 0 = auto-learn, still active) + DTC suppress | Removes SAP relay activation |
| **Post-Cat O2 Delete** | DTC suppression | For decat/catless |
| **EWS Delete** | Via patchlist | Removes immobilizer check |
| **Exhaust Pops/Crackle** | Overrun fuel cut tables | Toggleable or timed versions |
| **Launch Control** | Via patchlist | RPM limiter with boost build |
| **Rev Limiter Raise** | `ip_n_max_mt` / `ip_n_max_max_mt` | Watch for valve float |
| **Speed Limiter Delete** | `c_v_max` | — |
| **MAF Rescale** | `id_maf_tab` | For aftermarket MAF housings |
| **ICV Delete** | Via patchlist | For ITB conversions |
| **Lumpy Idle** | Patchlist | Simulates aggressive camshaft |
| **VANOS Tweak** | `ip_cam_sp_in/ex_pl` | Small midrange power gain |

### Community Patchlist v2.9.2 (430069 only)

Applied via `Siemens_MS43_MS430069_Community_Patchlist_v2.9.2.xdf`. Includes all MS42 v1.7.1 patches plus:

| Patch | Description |
|-------|-------------|
| MAF Hack 4096 kg/h | Quadruples MAF range (vs 2048 on MS42) |
| Boost Control | Forces canister purge output for boost solenoid control |
| Injection Calculation | Custom injection scalar calculation for non-standard injectors |
| MAF-Based Full Load Enrichment | `ip_ti_fl` 16×12 full-load table (MS43 exclusive) |
| E3x Diff VSS Fix | Corrects vehicle speed signal for E36/E30 diff sensor |

All MS42 patches also available: EWS bypass, checksum bypass, M cluster LEDs, DS2 baudrate/speed, ignition cut, launch control + RAL, alpha/N, MIL knock indicator, CAN boost gauge, decel map switch.

### MS43X Custom Firmware (successor to patchlist)

Released Oct 2025 — a complete custom firmware replacement for 430069. Key features:
- Closed-loop boost control
- Flex fuel / E85 blending
- VE-model fueling (speed-density, MAF-less operation)
- Configurable MAP/MAF/Alpha-N switching
- Extended load limit: 2778 mg/stroke (vs 1389 on MS42)
- Overboost protection
- Launch control with anti-lag
- Injection scalar calculation
- Full-load enrichment table (`ip_ti_fl` 16×12)

**MS43X is only for MS43 430069** — not available for MS42 or other MS43 firmware versions.
More info: https://www.ms4x.net/index.php?title=MS43X

### Catalyst Overheating Prevention (COP)

The MS43 has a safety feature that retards timing and enriches fueling if exhaust gas temps are modeled too high. Key tables:
- `ip_iga_ron_91_pl_ivvt__n__maf` — timing pulled when COP active
- `ip_ti_cop_nr_*__n__maf` — COP fuel enrichment tables (set to 0 to disable per-cylinder)
- `ip_maf_min_cop__n__iga_dif` — COP activation threshold

### Flash Tools

Same as MS42 — both supported by the same tools:

| Tool | Read | Write | Checksum | Notes |
|------|------|-------|----------|-------|
| **MS4x Flasher** (v1.5.0) | Full/Partial | Full/Partial | Auto-corrects CRC16 + addition | Free, recommended |
| **JMGarage Flasher** | Full (boot-mode) | Full | Manual | For locked ECUs / virginizing |

### MS42 ↔ MS43 Porting Notes

| Aspect | MS42 | MS43 |
|--------|------|------|
| BASEOFFSET | 0x48000 | 0x70000 |
| Cal data size | 32 KB | 64 KB |
| Processor clock | 20 MHz | 24 MHz |
| Map naming | `kf_*` / `tab_*` prefixes | `ip_*` / `id_*` prefixes (IVVT) — some tables use `ID_` in CSV/A2L but `ip_` in XDF |
| Table count | 597 | 1,454 |
| **Common tables** | 410 exact name matches (69% of MS42) | Same 410 tables |
| XDF/BIN compatible? | **NO** | **NO** |
| Load limit | 1389 mg/stroke (hardcoded) | 1389 (stock) / **2778 (MS43X)** |
| MAF limit | 1024 kg/h (2048 w/ patch) | 1024 (4096 w/ patch) |
| Patchlist | v1.7.1 (17 patches) | **v2.9.2** (more features) |
| Custom firmware | None | **MS43X** |
| Processor | C167CR-**SR** | C167CR-**LM** |

Porting is done by the CLI editor's `port` command — it matches maps by name, handles equation differences, and resamples if axes differ. Only calibration data is portable; code patches are firmware-specific.

### References

- **ms4x.net wiki** — https://www.ms4x.net/index.php?title=Siemens_MS43
- **Flash Files MS43** — https://www.ms4x.net/index.php?title=Flash_Files_MS43
- **MS4x Flasher** — https://www.ms4x.net/index.php?title=MS4x_Flasher
- **First Steps** — https://www.ms4x.net/index.php?title=First_steps_and_requirements
- **Siemens Keyword Translation** — https://www.ms4x.net/index.php?title=Siemens_Keyword_Translation
- **Community Patchlist MS43** — https://www.ms4x.net/index.php?title=TunerPro_Community_Patchlist_MS43
- **Firmware Files** — https://www.ms4x.net/index.php?title=Firmware_Files
- **MS43X Custom Firmware** — https://www.ms4x.net/index.php?title=MS43X
- **MS43 PCB Components** — https://www.ms4x.net/index.php?title=Siemens_MS43_PCB_Components

### Local Reference Files

| File | Content |
|------|---------|
| `1bmw_ms42_tuning_guides/ms43_damos/4323T110.A2L` | DAMOS A2L v055.01 — 105,421 lines of parameter definitions |
| `1bmw_ms42_tuning_guides/ms43_damos/MS43.csv` | Complete parameter database — 3,457 entries with addresses and dimensions |
| `1bmw_ms42_tuning_guides/ms43_damos/MS43 ECU Definitions.xml` | RomRaider XML definitions with scaling formulas |
| `1bmw_ms42_tuning_guides/MS42_MS43_Conversion_EU2_and_Table_Reference.md` | Full cross-referenced conversion guide, EU2 procedure, table address cross-reference |
| `1bmw_ms42_tuning_guides/ms43_m52tub25_rhd_eu2_323i_port_from_ms42.md` | Complete M52TU→MS43 conversion build document |
| `1bmw_ms42_tuning_guides/COMPATIBILITY_MATRIX.md` | XDF/BIN/ECU compatibility rules |