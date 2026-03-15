# ═══════════════════════════════════════════════════════════════════════════════
#  PORTING TEMPLATES — Map Classification for AI-Assisted Tune Porting
# ═══════════════════════════════════════════════════════════════════════════════
#
#  These templates tell the AI CLI editor how to classify maps when porting
#  between ECU firmware variants. Each section covers a specific porting
#  scenario.
#
#  Classification rules:
#    DIRECT_COPY   — Same name, same axes, same units. Copy values directly.
#    RESAMPLE      — Same name, different axis dimensions. Bilinear interpolation.
#    CONVERT       — Same name, different units (AFR↔Lambda). Convert then copy/resample.
#    MANUAL_REVIEW — Mass units, missing data, patchlist items, or unknown maps.
#    SKIP          — Code patches, program logic, not calibration data.
#
#  Author:       Jason King
#  Copyright:    (c) 2025 KingAI Pty Ltd
# ═══════════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════════
#  TEMPLATE 1: MS42 (0110C6) → MS43 (430069)
# ═══════════════════════════════════════════════════════════════════════════════
#
#  BMW Siemens MS42 to MS43 porting.
#  Both are Siemens C167CR family, very similar internal table structure.
#  Both use Lambda units for fuel targets (1.0 = stoich).
#
#  Reference XDFs (verified):
#    Source: Siemens_MS42_0110C6_ENG_512K_v1.1.xdf
#           → 1384 constants, 597 tables, BASEOFFSET=0x48000
#    Target: Siemens_MS43_430069_512K_1.1.3v.xdf
#           → 2256 constants, 1454 tables, BASEOFFSET=0x70000
#
#  CRITICAL: MS42 cal=32KB @0x78000, MS43 cal=64KB @0x70000.
#  NEVER mix XDFs — addresses differ by 0x8000+. All addresses wrong if mixed.
#
#  BASEOFFSET handling:
#    MS42 0110C6: BASEOFFSET offset=294912 (0x48000), subtract=0
#    MS43 430069: BASEOFFSET offset=458752 (0x70000), subtract=0
#    The CLI editor handles this automatically via UniversalXDFExporter.
#
# ─── SAFE: Direct Copy or Resample ──────────────────────────────────────────
#  These maps exist in both MS42 and MS43 with compatible semantics.
#  If axis dimensions match → direct copy. If not → bilinear resample.
#
#  Ignition / Spark (VERIFIED table names in MS42 0110C6 XDF):
#    - ip_iga_maf_n__n__maf         (main ignition table - part load)
#    - ip_iga_maf_n_is__n__maf      (ignition at idle)
#    - ip_iga_tco_1_is_ivvt__n__maf (ignition tco1 idle with IVVT)
#    - ip_iga_tco_1_pl_ivvt__n__maf (ignition tco1 part load IVVT)
#    - ip_iga_tco_2_is_ivvt__n__maf (ignition tco2 idle IVVT)
#    - ip_iga_ron_91_pl_ivvt__n__maf (RON91 part load IVVT)
#    - ip_iga_ron_98_pl_ivvt__n__maf (RON98 part load IVVT)
#    - ip_iga_aj_ron91__n__maf      (RON91 adjustment)
#    - ip_iga_aj_ron98__n__maf      (RON98 adjustment)
#    - ip_iga_knk_diag__n__lm       (knock diagnostics)
#    - ip_fac_knk_0..5__n__maf      (knock factor tables 0-5)
#    - ip_gain_knk__n               (knock sensor gain)
#    - id_iga_dec_knk_1/2__n        (knock retard decrements)
#    - id_iga_inc_knk__n            (knock retard increment/recovery)
#    - ip_igab__n__maf              (ignition base)
#    - ip_igab_is__n__maf           (ignition base idle)
#    - Dwell time tables (same coils on same cams → same dwell)
#
#  VANOS / Cam Timing (MUST match cam hardware — M52TU vs M54):
#    - ip_cam_sp_tco_1_in_is__n__maf_ivvt  (intake VANOS idle tco1)
#    - ip_cam_sp_tco_1_ex_is__n__maf_ivvt  (exhaust VANOS idle tco1)
#    - ip_cam_sp_tco_1_in_pl__n__maf_ivvt  (intake VANOS part load tco1)
#    - ip_cam_sp_tco_1_ex_pl__n__maf_ivvt  (exhaust VANOS part load tco1)
#    - ip_cam_sp_tco_2_*                   (tco2 variants)
#    - ip_cam_sp_tco_1_in_fl__n            (intake VANOS full load)
#    - ip_cam_sp_tco_1_ex_fl__n            (exhaust VANOS full load)
#    - ip_fac_cam_sp_*                     (VANOS correction factors)
#    WARNING: M52TU and M54 have different cam profiles. Only safe to copy
#    when hardware matches exactly.
#
#  Load / Airflow:
#    - ip_maf_vo_1..8__map__n   (MAF substitute/alpha-N backup tables)
#    - ip_vol_im__n__maf_mes    (intake manifold volume model)
#    - ip_pq_main_col_tq__n__tps_sum (throttle→torque request)
#    - ip_pvs_*                 (throttle position / pedal tables)
#
#  Idle:
#    - ip_n_sp_is__tco     (idle RPM target vs coolant temp)
#    - ip_isapwm__tco      (idle speed valve PWM vs coolant temp)
#    - ip_isapwm_at__tco   (idle speed valve auto trans)
#    - ip_isapwm_*         (all ISA-PWM sub-tables)
#
#  Temperature Compensation:
#    - ip_tco__v_tco    (coolant temp sensor linearisation)
#    - ip_tia__v_tia    (intake air temp sensor linearisation)
#    - ip_toil__v_toil  (oil temp calculation)
#
#  Rev/Speed Limiters:
#    - id_n_max_at__nvs / id_n_max_mt__nvs   (rev limiter tables)
#    - id_n_max_max_at__nvs / id_n_max_max_mt__nvs (absolute max RPM)
#    - id_n_max_lgrd__gear / id_n_max_lgrd_at__gear (rev limiter per gear)
#
# ─── CONVERT: AFR ↔ Lambda ──────────────────────────────────────────────────
#  Both MS42 and MS43 use Lambda natively (stoich = 1.0).
#  Conversion is NOT needed between these two ECUs.
#  However, if porting FROM a Holden (AFR) TO MS42/MS43 (Lambda):
#    Lambda = AFR / 14.7  |  AFR = Lambda * 14.7
#
#  MS42/MS43 fuel maps using Lambda (verified names):
#    - ip_lam_i__n__maf            (lambda integrator)
#    - ip_lam_neg_p__n__maf        (lambda negative proportional)
#    - ip_lam_pos_p__n__maf        (lambda positive proportional)
#    - ip_fac_lam_pu__tco          (lambda factor post-start)
#    - ip_fac_lam_dly__n__maf      (lambda delay factor)
#    - ip_lam_dif_max_cp__n__maf   (lambda max deviation)
#    - id_lam_tco_min__tco_st      (lambda enable temp, normal)
#    - id_lam_tco_min_is__tco_st   (lambda enable temp, idle)
#
#  Detection heuristics:
#    - Map name contains "lambda", "lamda", "lam_" → Lambda
#    - Map name contains "afr", "air_fuel", "a/f" → AFR
#    - Values near 1.0 (0.7-1.3 range) → probably Lambda
#    - Values near 14.7 (10-18 range) → probably AFR
#
# ─── MANUAL REVIEW: Mass / Airflow / Injector / Displacement ────────────────
#  Maps requiring engine-specific parameters to convert:
#
#  MAF Scaling (NEVER auto-port):
#    - id_maf_tab                   (256x1, voltage→kg/h, eq=0.015625*X)
#    - id_maf_tab (MAF Hack 2048)   (256x1, doubled scaling for big MAF)
#    - id_maf_tab__v_maf_1__v_maf_2 (16x16 2D view of same data)
#    Different MAF sensor = different calibration (HFM5 vs HFM6 vs Audi RS4)
#
#  Injector Characterisation:
#    - ip_td__vb                (injector deadtime vs battery, eq=X*0.032)
#    - ip_td_ign_mpl__vb        (injector deadtime ignition multiplier)
#    - ip_ti_*                  (all injection time tables)
#    - ip_tib__n__maf           (base injection time)
#    M52TU: 237 cc/min, 0.81ms@12V deadtime
#    M54B30: 254 cc/min, 0.576ms@12V deadtime
#    Always recalculate: New_IPW = Old_IPW * (Old_Flow / New_Flow)
#
#  Torque Model (displacement-dependent):
#    - ip_tqi_maf__n__maf       (torque from MAF)
#    - ip_tqi_pvs_tco_1/2__n__pvs (torque from throttle pos)
#    - ip_tqfr__n__maf          (torque friction)
#    Scale by displacement ratio if engine differs.
#
#  MAF Diagnostics:
#    - c_maf_min_hfm_diag       (MAF diagnostic minimum)
#    - c_maf_max_hfm_diag       (MAF diagnostic maximum)
#    - c_fac_hfm_min/max        (HFM correction factor ±40%)
#
#  DO NOT AUTO-PORT these without engine parameter review.
#
# ─── SKIP: Code Patches / Program Logic ─────────────────────────────────────
#  These are not calibration maps but code modifications from the patchlist.
#  They modify ECU program behavior, not table values.
#
#  Examples:
#    - [PATCH] Alpha/N
#    - [PATCH] Launch Control
#    - [PATCH] Extended Logging
#    - [PATCH] SAP Delete (Secondary Air Pump)
#    - [PATCH] EWS Delete (Immobilizer)
#    - [PATCH] Cat Monitor Delete
#
#  NEVER copy patch data between firmware versions.
#  Patches must be applied per-firmware using the correct patchlist.
#


# ═══════════════════════════════════════════════════════════════════════════════
#  TEMPLATE 2: VS/VT (Stock or Enhanced) → VY Enhanced V6 L36
# ═══════════════════════════════════════════════════════════════════════════════
#
#  Holden/GM V6 3.8L L36 (Series II Ecotec) porting.
#  VS = 1995-1997, VT = 1997-2000, VY = 2002-2004
#  All use GM Delco/Delphi ECMs with 68HC11 architecture.
#
#  Verified XDF/BIN data:
#    VS V6 $51 Enhanced:  681 constants, 257 tables, 349 flags
#    VT V6 $A5G:          177 constants, 118 tables, 205 flags
#    VY V6 $060A Enhanced: 1310 constants, 330 tables, 351 flags, 3 patches
#    VY BIN: 131072 bytes (128KB), BASEOFFSET=0x0
#
#  CRITICAL LOAD AXIS DIFFERENCE:
#    VS V6: MGS (Mass Grams/Second) range 93-593
#    VY V6: CYLAIR50 (mg/cyl × 50) range 50-850
#    These are NOT interchangeable! MGS 500 ≠ CYLAIR50 500
#
#  CRITICAL SPARK FORMULA DIFFERENCE:
#    VS V6: degrees = X × 0.351565
#    VY V6: degrees = X / 256 × 90 - 35
#    Same raw value = COMPLETELY different advance!
#
#  RPM Axes — SAME on both (<4800 RPM tables):
#    400, 600, 800, 1000, 1200, 1400, 1600, 1800, 2000, 2200, 2400,
#    2800, 3200, 3600, 4000, 4400, 4800
#    >4800: 4800, 5200, 5600, 6000, 6400
#
#  Stock PE AFR — SAME on both: 12.80:1
#
# ─── SAFE: Direct Copy (same function, name equivalents) ────────────────────
#  These maps serve the same function with compatible semantics.
#  Names differ but meaning is identical.
#
#  Spark / Ignition:
#    VS: 'Spark - Main Spark Advance - High Octane'
#    VY: 'Main High-Octane Spark Table < 4800 RPM'
#    NOTE: Values must be CONVERTED using formula difference!
#    Cannot copy raw values directly.
#
#    VS: 'Spark - Main Spark Advance - High Octane >4800RPM'
#    VY: 'Main High-Octane Spark Table > 4800 RPM'
#
#    VS: 'Spark - Main Spark Advance - Low Octane'
#    VY: 'Main Low-Octane Spark Table < 4800 RPM'
#
#  Fueling (both use AFR, values are directly comparable):
#    VS: 'Power Enrichment - Fuel Air Ratio Vs Coolant'
#    VY: 'PE Commanded AFR Vs Coolant Temperature'
#    Both stock at 12.80:1 operating temp.
#
#    VS: 'Injector - Offset Vs. Battery Voltage'
#    VY: 'Injector Offset Vs Battery Voltage'
#
#    VS: 'Injector - Low Pulse Width Injector Offset Vs Base Pulse Width'
#    VY: 'Low Pulse Width Injector Offset Vs Base Pulse Width'
#
#  PE Enable — DIFFERENT UNITS:
#    VS: TPS % threshold (50% stock, reduce to 26-32% for turbo)
#    VY: MGC (mg/cylinder) threshold (64.8 stock, reduce to 35-45 for turbo)
#    CANNOT COPY — different enable mechanism entirely.
#
# ─── CONVERT: Spark Formula Difference ──────────────────────────────────────
#  When copying spark values from VS to VY (or vice versa):
#    VS→VY: new_raw = int((vs_degrees + 35) / 90 * 256)
#    VY→VS: new_raw = int(vy_degrees / 0.351565)
#  Where:
#    vs_degrees = vs_raw × 0.351565
#    vy_degrees = vy_raw / 256 × 90 - 35
#
# ─── CONVERT: Injector Offset Formula Difference ───────────────────────────
#    VS:  ms = X / 65.536
#    VY:  ms = X / 260 / 256 × 1000
#
# ─── MANUAL REVIEW ──────────────────────────────────────────────────────────
#  Maps needing manual inspection because of platform differences:
#
#  MAF Calibration (NEVER auto-port):
#    Both use piecewise freq→g/s (Airflow = AFRS_n + Freq × MGSE_n)
#    But different sensors and calibration — always sensor-specific.
#    VY has: 'MAF Complete Offset, Divider and Tables.'
#           'MAF Scaler Table 1-Scaled Hz'
#
#  Fuel Tables VY-only (no VS equivalent):
#    VY: 'Fuel Trim Factor/ Injector Multiplier Vs RPM & Cylair'
#    VY: 'Base ECT Spark Table' (ECT spark correction)
#
#  Torque Management:
#    Generation-specific. VY has more refined torque tables.
#    Safety-critical — do not port without manual review.
#
#  Transmission Shift Tables:
#    Trans-specific. Auto vs manual differ. VY has different 4L60E calibration.
#
#  Load Axis Conversion (requires manual):
#    VS MGS 93-593 → VY CYLAIR50 50-850
#    Not a simple linear mapping. Need engine-specific rescaling.
#
# ─── SKIP ───────────────────────────────────────────────────────────────────
#  VIN/OS/calibration ID bytes — never port
#  Checksum bytes — recalculate with vendor tool
#  Operating system segments — never port
#  DTC base addresses differ: VS=0x35E2, VT=0x36DB, VY=0x56D2
#


# ═══════════════════════════════════════════════════════════════════════════════
#  TEMPLATE 3: VY V6 Stock → VY V6 Enhanced L36
# ═══════════════════════════════════════════════════════════════════════════════
#
#  Same generation, same engine, stock-to-enhanced upgrade.
#  This is the simplest porting scenario: same ECU hardware,
#  same firmware architecture, just different calibration values.
#
# ─── SAFE: Direct Copy (Almost Everything) ──────────────────────────────────
#  When going from stock to enhanced on the same VY V6:
#    - Both use the same XDF structure
#    - Both use the same addresses
#    - Both use the same units
#    - Table dimensions are identical
#
#  Nearly all tables can be directly copied:
#    - All spark tables
#    - All fuel tables
#    - All idle tables
#    - Rev limiters
#    - Speed limiters
#    - Torque management
#    - Fan control
#    - A/C compensation
#
# ─── MANUAL REVIEW ──────────────────────────────────────────────────────────
#  Even within the same generation, check:
#    - MAF calibration (if MAF sensor changed)
#    - Injector characterization (if injectors changed)
#    - Operating system version (if OS updated)
#    - Transmission tables (auto vs manual, different trans)
#    - VIN-locked calibration (may need VIN update)
#
# ─── SKIP ───────────────────────────────────────────────────────────────────
#  Same as above: VIN, checksums, OS segments.
#


# ═══════════════════════════════════════════════════════════════════════════════
#  CSV MAP MAPPING FORMAT
# ═══════════════════════════════════════════════════════════════════════════════
#
#  When source and destination map names don't match exactly, provide a CSV
#  mapping file with columns: src_name, dst_name
#
#  Example (ms42_to_ms43_mapping.csv):
#    src_name,dst_name
#    Fuel Map Base,Fuel Target Map
#    Ignition Timing Part Load,Spark Advance Part Load
#    VANOS Intake Angle,VANOS Intake Target
#
#  The CLI editor uses this with:
#    python cli_map_editor.py port \
#      --src-xdf ms42.xdf --src-bin ms42.bin \
#      --dst-xdf ms43.xdf --dst-bin ms43.bin \
#      --map-csv ms42_to_ms43_mapping.csv
#
#  Maps not in the mapping file are skipped.
#  Use --map-name for single-map porting.
#


# ═══════════════════════════════════════════════════════════════════════════════
#  AI DECISION FLOWCHART
# ═══════════════════════════════════════════════════════════════════════════════
#
#  When the AI is asked to port a tune, follow this decision tree:
#
#  1. Load both XDFs → list all maps in both
#  2. For each source map:
#     a. Does an exact name match exist in destination?
#        YES → go to step 3
#        NO  → check mapping CSV, or skip with warning
#     b. Do dimensions match?
#        YES → go to step 4
#        NO  → mark as RESAMPLE, go to step 4
#     c. Do axes match (same values)?
#        YES → go to step 4
#        NO  → mark as RESAMPLE, go to step 4
#  3. Check units:
#     a. Both AFR or both Lambda → DIRECT_COPY or RESAMPLE
#     b. One AFR, one Lambda → CONVERT + DIRECT_COPY or RESAMPLE
#     c. One or both MASS → MANUAL_REVIEW
#     d. Unknown units → check values:
#        - Values ~1.0 → probably Lambda
#        - Values ~14.7 → probably AFR
#        - If still unclear → MANUAL_REVIEW
#  4. Check if map is a code patch → SKIP
#  5. Execute classification:
#     - DIRECT_COPY → copy values cell-by-cell
#     - RESAMPLE → bilinear interpolation using axis values
#     - CONVERT → apply AFR↔Lambda conversion, then copy/resample
#     - MANUAL_REVIEW → log warning, skip automatic porting
#     - SKIP → do nothing
#  6. After all maps processed:
#     - Save ported BIN with timestamp
#     - Write log with all changes
#     - Print summary of ported/skipped/manual maps
#
