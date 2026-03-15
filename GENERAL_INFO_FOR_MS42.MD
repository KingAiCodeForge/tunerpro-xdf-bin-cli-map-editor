## INFO FOR THE MS42 BIN AND XDF 0110C6, AND ACROSS FIRMWARES. EU2 SETTINGS FROM MS4X AND OTHER FINDINGS

NO HARD paths — just names of bins and xdf, xmls and a2ls and where to get them.

---

### Hardware Specifications

| Detail | Value |
|--------|-------|
| **ECU Manufacturer** | Siemens |
| **ECU Model** | MS42 |
| **Processor** | Infineon C167CR-**SR** @ 20 MHz |
| **Flash Chip** | AMD AM29F400BB — 4 megabit (512 KB) |
| **Total BIN Size** | 524,288 bytes (512 KB) |
| **Engine Family** | BMW M52TU inline-6 (double VANOS) |
| **Throttle Control** | MDK (Motor-Driven) drive-by-wire — dual potentiometer feedback, cable-linked pedal. NOT cable throttle. |
| **MAF Sensor** | Bosch HFM5 hot-film |
| **Lambda Control** | 4 × lambda sensors (2 pre-cat, 2 post-cat on EU3) |
| **Communication** | K-line (DS2 protocol) + CAN bus |

### Memory Layout (from ms4x.net wiki)

| Start | End | Section | Size |
|-------|-----|---------|------|
| 0x00000 | 0x0FFFF | Bootloader & UIF | 64 KB |
| 0x10000 | 0x3FFFF | Program Code 1 | 192 KB |
| 0x40000 | 0x47FFF | Unused Space | 32 KB |
| **0x48000** | **0x4FFFF** | **Calibration Data** | **32 KB** |
| 0x50000 | 0x7FFFF | Program Code 2 | 192 KB |

**BASEOFFSET = 0x48000** (subtract=0 in XDF). All XDF map addresses are offsets within this calibration area. The exporter adds BASEOFFSET to get the file offset.

**Bootloader section** is one-time-programmable under normal flash operations — once a byte changes from 0xFF it cannot be changed back without boot-mode access (JMGarage Flasher).

### Firmware Versions

| Version | Notes |
|---------|-------|
| **0110AD** | Early firmware |
| **0110C6** | Most common, best community support, recommended for tuning |
| ~~0110C7~~ | **Does not exist in any known binary** — referenced in some docs but never found in 364 scanned firmware files |
| **0110CA** | Latest OEM version — can be overwritten with 0110C6 via full flash |

**Critical rule:** Each firmware version has different map positions. An XDF for 0110C6 will show garbage if used with a 0110CA BIN. Always match XDF to firmware version exactly.

**Upgrading:** You can full-flash any MS42 to 0110C6 firmware regardless of its current version. After upgrade, use 0110C6 definition files. The MS4x Flasher tool handles this.

### Checksums

The MS42 uses **3 CRC16 checksums** that must be correct for the engine to start:

| Type | Section | Address |
|------|---------|--------|
| CRC16 | Boot | 0x3C24 |
| CRC16 | Program | 0x50306 |
| CRC16 | Calibration | 0x4FEE0 |

**Disabling calibration checksum (development only):** Set WORD at `0x4FEFE` → `0xFFFF`, set BYTE at `0x5002C` → `0xA8`.

The MS4x Flasher corrects checksums automatically on-the-fly. If using boot-mode flashing (JMGarage), you must correct checksums manually before flashing.

### XDF Definition Files

| File | Source | Notes |
|------|--------|-------|
| `Siemens_MS42_0110C6_ENG_512K_v1.1.xdf` | ms4x.net community | English, 512 KB full flash, **recommended** |
| `0110C6 German.xdf` | ms4x.net | German language labels |
| Earlier community XDFs | e46fanatics forum | Various, may be incomplete |

**XDF contents (0110C6 v1.1):**
- 1,384 constants (scalars)
- 597 tables (2D maps)
- 0 flags, 0 patches (flag/patch support varies by XDF version)

### BIN Files (Where to Get)

| Source | What | Notes |
|--------|------|-------|
| **ms4x.net → Flash Files** | Community flash files for 0110C6 | Free, open, checksummed |
| **MS4x Flasher → Read ECU** | Read your own ECU's BIN | Full or partial (64 KB cal only) |
| **JMGarage Flasher** | Boot-mode read for locked ECUs | Needed if DS2 read-locked |

BIN file naming convention: files from ms4x.net are typically named like:
- `0110C6_M52TUB28_EU2.bin` (engine variant + emissions standard)
- `0110C6_M52TUB25_EU3.bin`

### Available Engine Variants (all use MS42)

| Engine Code | Displacement | Power | Applications |
|-------------|-------------|-------|-------------|
| M52TUB20 | 2.0L | 110 kW / 150 PS | E46 320i, E39 520i, Z3 2.0 |
| M52TUB25 | 2.5L | 125 kW / 170 PS | E46 323i/325i, E39 523i/525i, Z3 2.5 |
| M52TUB28 | 2.8L | 142 kW / 193 PS | E46 328i, E39 528i, Z3 2.8 |

### Key Calibration Maps (Siemens naming convention)

#### Fueling
| Map Name | Dimensions | Description |
|----------|-----------|-------------|
| `kf_ti_tkw2_vanos_tl_bk1__n__lm` | 16×20 | Warm engine injection time, bank 1, part-load |
| `kf_ti_tkw2_vanos_tl_bk2__n__lm` | 16×20 | Warm engine injection time, bank 2, part-load |
| `kf_ti_tkw1_vanos_ll__n__lm` | 16×20 | Cold engine injection time, idle |
| `kf_ti_tkw2_vanos_ll__n__lm` | 16×20 | Warm engine injection time, idle |
| `id_maf_tab` | 256×1 | MAF sensor calibration (voltage → kg/h), eq = `0.015625*X` |
| `T_TI_AS` | 1×1 | Base injection time scalar — primary injector size scaling |

#### Ignition
| Map Name | Dimensions | Description |
|----------|-----------|-------------|
| `kf_zw_roz98_vanos_tl__n__lm` | 16×20 | Ignition timing, RON98 fuel, warm part-load — **main map** |
| `kf_zw_roz91_vanos_tl__n__lm` | 16×20 | Ignition timing, RON91 fuel, warm part-load |
| `kf_zw_roz98_vanos_ll__n__lm` | 16×20 | Ignition timing, RON98 fuel, warm idle |
| `tab_zw_dec_kr_1__n` | — | Knock retard stage 1 (by RPM) |
| `tab_zw_dec_kr_2__n` | — | Knock retard stage 2 (by RPM) |

#### VANOS (Variable Valve Timing)
| Map Name | Description |
|----------|-------------|
| `KF_NWSOLL_TKW2_TL_E` | Intake VANOS setpoint, warm engine, part-load — **main intake cam map** |
| `KF_NWSOLL_TKW2_LL_E` | Intake VANOS setpoint, warm engine, idle |
| `KF_NWSOLL_TKW2_TL_A` | Exhaust VANOS setpoint, warm engine, part-load — **main exhaust cam map** |
| `KF_NWSOLL_TKW2_LL_A` | Exhaust VANOS setpoint, warm engine, idle |
| `KF_NWSOLL_TKW1_TL_E` | Intake VANOS setpoint, cold engine, part-load |
| `KF_NWSOLL_TKW1_TL_A` | Exhaust VANOS setpoint, cold engine, part-load |
| `KF_NWSOLL_TKW2_VL_E` | Intake VANOS setpoint, warm engine, full-load |
| `KF_NWSOLL_TKW2_VL_A` | Exhaust VANOS setpoint, warm engine, full-load |
| `KF_NWSOLL_FAK_TL_E` | Intake VANOS cold→warm blending factor, part-load |
| `KF_NWSOLL_FAK_TL_A` | Exhaust VANOS cold→warm blending factor, part-load |

#### Limiters
| Map Name | Description |
|----------|-------------|
| `TAB_NMAX_MT` | RPM soft limiter (manual trans) — cuts injectors per fuelcut pattern |
| `TAB_NMAX_MAX_MT` | RPM hard limiter (manual trans) — cuts all cylinders |
| `TAB_NMAX_AT__NTV` | RPM soft limiter (auto trans) — per gear |
| `TAB_NMAX_MAX_AT__NTV` | RPM hard limiter (auto trans) — per gear |
| `TV_MAX_VL` | Speed limiter — set to 255 for no limit |

#### Alpha/N (MAF Failsafe)
| Map Name | Description |
|----------|-------------|
| `KF_LM_DIAG_1` | Alpha/N airflow estimate — used when MAF is disconnected or faulty |

#### Throttle (Drive-by-Wire)
| Map Name | Description |
|----------|-------------|
| `KF_MDK_SOLL_PWG_TKW1` | Throttle vs pedal position — cold engine |
| `KF_MDK_SOLL_PWG_TKW2` | Throttle vs pedal position — warm engine |

#### E-Thermostat (Coolant Temp Control)
| Map Name | Description |
|----------|-------------|
| `TAB_TKW_SOLL_KFK__N__LM_ERS` | Target coolant temp without A/C |
| `TAB_TKW_SOLL_KFK_KA__N__LM_ERS` | Target coolant temp with A/C |
| `TKW_SOLL_TOEL_MIN` | Min oil temp before e-thermostat maps activate (default 102°C) |

### Load Calculation

Engine load in the MS42 is proportional to **MAF ÷ RPM** (mg/stroke) and is used to index all major fuel and ignition tables. The axes are typically:
- **X-axis (columns):** Engine speed (RPM)
- **Y-axis (rows):** Airflow / load (mg/stroke or derived)

**Maximum engine load: 1389 mg/stroke** — hardcoded in firmware, cannot be changed without program code rewrites. This limits the MS42 for forced-induction applications (MS43X raises this to 2778 mg/stroke).

**MAF maximum: 1024 kg/h** (factory). Can be doubled to 2048 kg/h via patchlist MAF hack.

### Safety Features (handle with care)

| Parameter | Description |
|-----------|-------------|
| `n_min_lu` | Minimum RPM for misfire detection |
| `n_max_lu` | Maximum RPM for misfire detection |
| `n_ti_ad_fak_min` | Min RPM for fuel trim adaptation (multiplicative) |
| `n_ti_ad_add_max` | Max RPM for fuel trim adaptation (additive) |

### Common Modifications

| Mod | Maps/Scalars Affected | Notes |
|-----|----------------------|-------|
| **SAP Delete** (Secondary Air Pump) | `konf_ssp` at 0x4828E → **0** (0=OFF, 1=ON). **WARNING:** MS43 uses INVERTED values (1=deleted). Also suppress DTCs 35, 62, 50 | Removes SAP relay activation |
| **Post-Cat O2 Delete** | DTC suppression for rear O2 sensors | For decat/catless setups |
| **EWS Delete** | Immobilizer bypass | Via patchlist or ISN alignment |
| **Rev Limiter Raise** | `TAB_NMAX_MT` / `TAB_NMAX_MAX_MT` | Be cautious of valve float |
| **Speed Limiter Delete** | `TV_MAX_VL` = 255 | Removes electronic speed cap |
| **MAF Rescale** | `id_maf_tab` | For aftermarket MAF sensors or big MAF housings |
| **E-Thermostat Lower** | `TAB_TKW_SOLL_KFK__N__LM_ERS` | Reduce coolant temps — M52TU runs warm |

### Community Patchlist v1.7.1 (0110C6 only)

17 patches available for 0110C6 firmware. Applied via TunerPro's Patch function using `Siemens_MS42_0110C6_Community_Patchlist_v1.7.1.xdf`.

| Patch | Description |
|-------|-------------|
| Immobilizer Bypass | Bypasses EWS checks |
| Clear Immobilizer Data | Virginizes ECU (clears ISN) |
| Checksum Bypass | Disables calibration CRC16 |
| M3 Cluster LED Support | Activates M cluster LEDs + oil temp on CAN bus |
| DS2 Baudrate Bypass | Allows baudrate switching while engine running |
| DS2 Logging Enhancement | New logging command support |
| DS2 Speed Increase | Faster DS2 polling |
| MAF Hack 2048 kg/h | Doubles MAF range (must use patchlist `id_maf_tab`) |
| Ignition Cut Limiter | Adds ignition cut before fuel cut rev limit |
| Deceleration Map Switch | Switches decel maps via cruise control stalk |
| Launch Control + RAL | Launch control + rolling anti-lag |
| Alpha/N | Uses MAF substitute table for load (for ITB/turbo) |
| MIL Knock Indicator | Flashes MIL during knock events |
| CAN Boost Gauge | OLM boost gauge output via CAN |

**Note:** Patchlist is compatible with 0110C6 only. The wiki also references 0110C7 compatibility but no 0110C7 binary has been found.

### Flash Tools

| Tool | Protocol | Read | Write | Checksum | Notes |
|------|----------|------|-------|----------|-------|
| **MS4x Flasher** (v1.5.0) | DS2 (K-line) | Full/Partial | Full/Partial | Auto-corrects | Free, recommended. 512 KB read in ~120s |
| **JMGarage Flasher** | Boot-mode | Full (incl. bootloader) | Full | Manual | Needed for locked ECUs, virginizing |
| **INPA/NCS Expert** | DS2 | Read only | — | — | BMW dealer diagnostics |

**Connection:** K-DCAN cable (USB to OBD2), K-line on pin 7. MS42 uses 9600 baud DS2 (can be increased to 125 kbaud via patchlist DS2 Baudrate bypass — requires activating the patch with engine off, ignition on).

### EU2 vs EU3 Differences

| Feature | EU2 | EU3 |
|---------|-----|-----|
| Post-cat O2 sensors | Not used for closed-loop | Used for cat monitoring |
| Secondary air pump | Not required | Required for cold-start emissions |
| DTC set | Smaller | Includes cat efficiency and SAP DTCs |
| Base calibration | Same fuel + ignition maps | Same — only config bytes + MAF differ |

**Key finding:** Binary comparison shows only **347 bytes differ** between EU2 and EU3. Of those, 322 bytes are the MAF table (`id_maf_tab`) — likely due to different MAF sensor hardware between markets, NOT emissions calibration. The fuel and ignition maps are identical between EU2 and EU3 on 0110C6.

**Converting EU3 → EU2 (3 bytes minimum):**
1. `konf_abgasanlage` at 0x48287 → **1** (from 3) — switches to 2 pre-cat O2 only
2. `konf_mil` at 0x4828C → **0** (from 3) — relaxes MIL monitoring
3. `konf_ssp` at 0x4828E → **0** — disables SAP

Plus optionally: relax 11 diagnostic threshold scalars for post-cat O2 / cat efficiency to EU2 factory values.

Does NOT require reflashing program code — calibration-only changes. Full procedure in `1bmw_ms42_tuning_guides/MS42_MS43_Conversion_EU2_and_Table_Reference.md`.

### Relationship to MS43

MS42 (M52TU) and MS43 (M54) share the same Siemens platform but:
- Different processors (20 MHz vs 24 MHz)
- Different memory layout (cal at 0x48000 vs 0x70000)
- Different firmware version numbering (0110xx vs 430xxx)
- **410 tables share identical names** (69% of MS42 tables exist in MS43)
- XDFs and BINs are NOT cross-compatible — never use an MS43 XDF on an MS42 BIN

### References

- **ms4x.net wiki** — https://www.ms4x.net/index.php?title=Siemens_MS42
- **MS4x Flasher** — https://www.ms4x.net/index.php?title=MS4x_Flasher
- **First Steps** — https://www.ms4x.net/index.php?title=First_steps_and_requirements
- **Definition Files** — https://www.ms4x.net/index.php?title=Definition_Files
- **Siemens Keyword Translation** — https://www.ms4x.net/index.php?title=Siemens_Keyword_Translation
- **Community Patchlist MS42** — https://www.ms4x.net/index.php?title=TunerPro_Community_Patchlist_MS42
- **Flash Files** — https://www.ms4x.net/index.php?title=Flash_Files
- **Firmware Files** — https://www.ms4x.net/index.php?title=Firmware_Files

### Local Reference Files

| File | Content |
|------|---------|
| `1bmw_ms42_tuning_guides/ms42_damos/ms42.a2l` | DAMOS A2L — THE gold standard for parameter descriptions (76,069 lines) |
| `1bmw_ms42_tuning_guides/MS42_MS43_Conversion_EU2_and_Table_Reference.md` | Full cross-referenced conversion guide, EU2 procedure, table addresses |
| `1bmw_ms42_tuning_guides/MS42_0110C6_SAP_Delete_EU2_Setup_VERIFIED.md` | Verified SAP delete + EU2 setup with binary comparison |
| `1bmw_ms42_tuning_guides/COMPATIBILITY_MATRIX.md` | XDF/BIN/ECU compatibility rules |
| `1bmw_ms42_tuning_guides/bin_inventory_and_xdf_mapping.md` | 650 BIN file catalog with hashes |