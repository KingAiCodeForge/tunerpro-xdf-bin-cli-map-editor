# Patch and Formula Rebuild Register

**Updated:** 24 September 2026
**Scope:** Holden VY `$060A`, BMW MS42 `0110C6`, stock BMW MS43 `430069`, and MS43X001
**Status:** active rebuild queue; no legacy artifact is approved for vehicle use

## Current decision

Existing patch bytes and uncertain XDF formulas are research evidence. Newer
disassembly, call tracing, RAM/runtime tracing, and native-value evidence now
supersede several earlier assumptions. Rebuild each patch or formula from its
exact clean parent instead of repairing an old output in place.

Use these queue states:

| State | Meaning |
|---|---|
| `WITHDRAW` | Known wrong hook, control flow, address, table, or equation. Do not use as an implementation base. |
| `REBUILD_FIRST` | Useful intent/evidence exists, but the implementation contract is incomplete. |
| `BENCH_NEXT` | Strong static byte contract exists; controlled execution/readback is the next evidence gate. |
| `HOLD_FOR_TRACE` | Required producer/consumer, runtime state, or hardware behavior remains unresolved. |
| `LEGACY_REFERENCE` | Preserve hash and diff for provenance only. |
| `STATIC_PROVED` | Exact lineage, bounded diff and offline integrity checks pass; physical write/readback or vehicle proof is still open. |

No state in this document means flash-ready or vehicle-tested.

## Required rebuild contract

Every replacement must contain:

1. Exact ECU, software/OS, image layout, byte count, parent filename and
   SHA-256.
2. Current disassembly evidence for the function, callers, inputs, outputs,
   branch targets, final actuator/lookup path, and any code cave.
3. A patch manifest with file offsets, address basis, expected original bytes,
   replacement bytes, immutable ranges, and reverse bytes.
4. Register, stack, condition-code, bank/page, timeout, hysteresis, release,
   and fault-path proof where code executes.
5. Correct XDF storage width, signedness, endian, dimensions, axes, forward
   equation, inverse equation, and raw-range round trip where calibration data
   is exposed.
6. Complete parent/output byte diff with zero unexplained changes.
7. Checksum/signature coverage, deterministic repair, independent verifier,
   readback, rollback, and recovery procedure.
8. A bench test first, followed by a separately defined vehicle or dyno A/B
   test with pass and abort conditions.

## Holden VY `$060A`

Canonical Enhanced v1.0a parent SHA-256:
`5CB8BD1C61DA37A3846B6C28600CDC21DB3CEEF0C764232D0CD7EC8D6E836ABD`.

Current Antus v2.09b XDF SHA-256:
`5CE2DCC9CF683698B8C939863AC0CA610FEB8656D0DF11BE40FDD286D31B3C4D`.

### P0 — withdraw now

#### Muncies/The1 spark-cut base, patch `0x6A10`

- Present in R06 and
  `Muncies_060A_LaunchFuelCut_R07_KingAI_corrected.xdf`.
- R07 XDF SHA-256:
  `48BFCF90D20862A0CBE3208FAD16CDCDD6A291E5DDD34D2849A6146DCE633212`.
- The foreground path at CPU `$FD84` clears `$149E.0`, sets all `$16FA`
  bits, then calls `$31EF`.
- The reachable path ends at `$34BF RTI`, not `RTS`; using it as a foreground
  `JSR` target corrupts the return frame. Release behavior for most `$16FA`
  bits is also unproved.
- Action: `WITHDRAW`. Do not repair it by NOPing only the call. Design a new,
  RTS-bounded routine with explicit state release and proved B3/B4 effects.

Controlling evidence:
`VY_V6_Assembly_Modding/reports/local_re/vy_v1_1a_patch_semantics_20260910/VY_V1_1A_PATCH_SEMANTICS_CORRECTED.md`.

#### Historical spark-cut implementations

- v38 cross-bank-calls `$C500` from bank 2.
- v44/v45 assume `$017B` owns the final EST period. New tracing shows the
  value continues through `$0199 -> $019B -> $1444`.
- Action: `WITHDRAW` v38/v44/v45 and related derivatives as code bases. Trace
  the final external EST path and release state before redesign.

### P1 — rebuild first

#### Stationary launch fuel cut, patch `0x6A42`

- Hook file offset `0x125BA`: `96 A2 A1 00 -> BD FE C0 01` in corrected R07.
- Routine starts at file `0x17EC0`; full/restart scalars are `0x17EF0` and
  `0x17EF1`, displayed with `X*25`.
- R06 is wrong: it encoded `$BEC0/$BEF0/$BEF1`, which points `0x4000` below the
  intended bank-2 code/data. R07 corrects those operands to
  `$FEC0/$FEF0/$FEF1` and contains an inverse patch.
- Remaining blockers: no bound parent SHA, deterministic checksum/apply
  manifest, register/CCR/stack proof, complete selector-X trace, or runtime
  proof for the FILTKPH condition.
- Action: `REBUILD_FIRST` against exact v1.0a and the mapped factory bank-2
  RPM fuel-cut path `$A547-$A5D5`.

#### Muncies auxiliary patches

- DTC32 patch `0x6A01` changes file `0x56D4 CC -> 8C`; it has base bytes but
  no parent-hash/checksum/reverse contract.
- MAP-source patches `0x6A02/0x6A03` at file `0x14398` have inverse entries,
  but still need source binding, checksum handling, and current
  producer/consumer/fallback tracing.
- Action: `REBUILD_FIRST`; keep development-only meanwhile.

### P2 — validate or bench

#### Ghost-cam selector

- Source: `VY_V6_Assembly_Modding/asm_wip/ghost_cam/ghost_cam_retarded_idle_selector_v1.asm`.
- Hook file `0x1790F` (`B6 1A 45 -> BD FE A2`); handler at `0x17EA2` in a
  checked zero run.
- Builder verifies the exact v1.0a source hash, original bytes, free space,
  checksum, output manifest, and diff. Rollback is the exact parent; a separate
  reverse command is still absent.
- Blockers: idle-cadence source `$1916`, hook/register/CCR control-flow proof,
  bench behavior, and logged idle/catalyst effects.
- Action: `HOLD_FOR_TRACE` until the hook/control-flow/register/CCR proof
  closes; then promote it to `BENCH_NEXT`.

#### v47/v48/v49/v51 injector and bugfix lane

- v47, v48 and v51 currently have the strongest VY static contracts: exact
  parent/base bytes, bounded diffs, deterministic output hashes, repaired
  checksums, and verifiers.
- v49 remains injector-characterization-only and depends on v48.
- External injector TIO and hardware behavior remain unproved.
- Action: keep v47/v48/v51 as `BENCH_NEXT`; keep v49 `HOLD_FOR_TRACE` until
  six-injector bench data exists.

#### v46 hook probe

- Byte/state-equivalent infrastructure probe with exact hashes and verifier.
- Adds 11 cycles and two transient stack bytes; no explicit reverse command.
- Action: bench-only when common-area hook infrastructure needs validation.

### P3 — archive and calibration cleanup

- The broad ASM concept archive contains 66 files: 39 fail assembly, 41 have
  cross-bank-call risk, 21 use the wrong runtime hook, and 11 retain active
  placeholders. Treat them as requirements/ideas, not patch sources.
- Rebuild D1 hold as an upshift-only change at file `0x0404B`. Retire the old
  `0x0404D -> FF` edit because it also raises the 2-1 downshift threshold to
  roughly 205.19 km/h.

## BMW MS42 `0110C6`

Canonical clean M52TUB28 EU3 RHD parent SHA-256:
`65C3B91A05A0D6AE40F82E39F327FDC2FF672F9B61E2C3233780535E44539F90`.

### P0 — quarantine damaged ghost-cam full images

- The F6 ghost-cam image SHA-256
  `F6E6B2DCC1D36BD5657B519FFC86D0F4F7CBEA656DAB69465271C3958675F0C4`
  contains the intended 84 calibration-byte delta plus a broken C166 `CALLS`
  first half at `0x709AE-0x709AF`.
- The A230 image SHA-256
  `A2305997E204E71D6D10478055871049B82A439CE1A8532485678B5FE11FD3DD`
  contains the same 84 bytes and broken call, plus 108 writes displaced exactly
  `0x48000` below their intended maps.
- The reviewed TunerPro image shows negative idle-ignition corrections and
  different error-axis breakpoints, while the local bodies retain stock axes
  and the current CLI/XDF path renders raw `C9/BD/...` as positive values.
- Action: keep both full images `LEGACY_REFERENCE` and do not flash them. Keep
  the five-map/84-byte reconstruction `HOLD_FOR_TRACE` until native TunerPro
  signedness and axis parity are proved.

### P1 — bounded aggressive-throttle reconstruction

- Port only `ip_tps_sp_pvs_tco_1__pvs__n` and
  `ip_tps_sp_pvs_tco_2__pvs__n` onto the clean parent. Their full-image ranges
  are `0x4AD34-0x4AE53` and `0x4AE54-0x4AF73`.
- The resulting delta is exactly 416 bytes inside those two 288-byte bodies.
  Both output bodies have SHA-256
  `9FDA5433BFBA7DDAAC9F0D935662E1579DF0099B38F1B91F603F965B78E90889`;
  axes remain stock and the code sentinel at `0x709AE` remains
  `DA 06 82 08`.
- Pre-checksum CLI output SHA-256:
  `8EEB90CB61FE9373C338FEE17686AE272AA22F2E8E0BE5FA6631B24AAF877B49`.
- Exact `0110C6` CAL-CRC repair changes only `0x4FEE0-0x4FEE1`. The corrected
  candidate SHA-256 is
  `BABE46932DEA70FE7796E7441F2C176CC9D009DCA17F3249098CE46AD488E4A6`
  and differs from the parent at 418 bytes: the 416 table bytes plus two stored
  CAL-CRC bytes. Boot `0xDF13`, CAL `0x14D6` and program `0xF347` all verify.
- The exact profile uses boot seed `0x2D2D`, `0110C6` CAL seed `0x3643` and
  program seed `0x3030`, with descriptor validation across four distinct
  pinned, checksum-valid `0110C6` stock/reference images. Twelve focused
  checksum tests pass.
- Action: retain as `STATIC_PROVED`, not flash-approved. Native TunerPro
  review, exact-DME matching, recovery, physical write/readback and logged
  pedal/requested/actual-throttle proof remain open.

### P2 — first MS42 ASM proof

- Prefer the `0110C6` DS2 Logging Feature Enhancement over a hardcut, launch or
  combustion patch. Its strict manifest is bound to clean parent SHA-256
  `65C3B91A05A0D6AE40F82E39F327FDC2FF672F9B61E2C3233780535E44539F90`
  and produces final SHA-256
  `AF72CCEB84CF12D75A8791051A43BCE00F4CC33447ECF51C3B1B2625810ED9DD`.
- The rebuilt `kingai.raw-patch.v2` manifest SHA-256 is
  `94CE827E565747F5E559646D8D5AC8D60CBF63CD6BCC7D4F333048E23C24C579`.
  Trusted-profile forward verification produces canonical-evidence SHA-256
  `2E4AC373CF1D25596B2E2883DF9DDE68E8A0A29B8AFDD1F8D174775463D204F3`;
  reverse verification produces
  `D4DB8B5CD5CCBF61468748F633670757818D8DB0EF62AB8A9F9AD21406033EE0`.
- The four declared chunks are the hook at `0x20950-0x20955`
  (`DA 01 26 D2 0D 02 -> FA 06 00 0E CC 00`), program-CRC bytes at
  `0x50306-0x50307` (`47 F3 -> 88 AF`), logger part 1 at
  `0x60E00-0x60EFF` (256 bytes), and logger part 2 at
  `0x60F00-0x60FC7` (200 declared bytes, 198 actual changes). The result has
  exactly 462 changed bytes and no changes outside those ranges. Boot, CAL and
  program checksums all verify, and reverse application restores the exact
  clean-parent SHA-256.
- The hook is covered by the ECU program CRC, but the complete payload range
  `0x60E00-0x60FC7` is outside ECU program-CRC coverage. Therefore the valid
  ECU checksums cannot authenticate the logger body; require the complete
  final-image SHA-256 and physical readback match at the bench gate.
- Action: `STATIC_PROVED / BENCH_NEXT`, not approved for an on-car flash. Make
  one manual 9600-baud bench transaction with complete DS2 frame
  `12 05 0B B0 AC`, require a reply beginning `12 49 A0` with coherent
  length/XOR and plausible values, and compare an unpatched DME as the negative
  control. The matching M52TUB28 ADX SHA-256 is
  `2BFE535BB6CC9E628B6ED740CC355794CBED1E3EF1DEA46D460CB8446F7C8B46`;
  it automatically switches to 125000 baud, so keep it as a later high-speed
  reference and do not combine baud-bypass or speed patches in the first test.

## Stock BMW MS43 `430069`

Canonical community patchlist:
`Siemens_MS43_MS430069_Community_Patchlist_v2.9.2.xdf`, SHA-256
`0BDFC536E658364475300DB1CFEDDD22EF372649F69656CA2F77F47CD0881425`.

### P0 — establish identity and layout first

- Resolve image layout before any patch: 64 KiB calibration at offset 0,
  128 KiB wrapper calibration at `0x10000`, and 512 KiB full image calibration
  at `0x70000` where applicable.
- Bind every patch to exact parent SHA, OSID/internal ID, layout, patch title
  and ID, entries, code-context signature, reverse bytes, immutable ranges,
  and checksum result.
- A September audit found all 27 previously checked 128 KiB pairs had layout
  false negatives when treated as offset-zero calibrations.

### P1 — canonical patchlist rebuild

- The canonical XDF contains 27 patch/data objects, 67 entries and 2,239
  target bytes.
- Twelve entries totaling 712 bytes lack `basedata`, including immobilizer
  clearing, deprecated LC data, map-reduction bodies, LC/RAL defaults, and MAF
  defaults.
- `xdf_patch_apply_strict.py` correctly refuses unguarded entries and checks
  exact base bytes, bounds and overlap, but does not repair checksums or create
  a reverse artifact.
- Action: add original-byte evidence to every entry and rebuild checksum and
  reverse contracts before applying the canonical set.

### P2 — first functional patch families

1. Re-trace the cruise-selector patch first because it has the strongest
   existing guarded/checksummed reference. Its clean base is SHA-256
   `0F97B32F0C5AD517F8834E33F909BEAC6771764F0AC79A12569344BDA3F4443D`;
   guarded sites are `0x2A3F2` and `0x2C968`. The current result remains
   `BLOCKED_FOR_VEHICLE` and lacks an explicit reverse artifact.
2. Rebuild ignition cut plus LC/RAL from current control-flow traces; these are
   high-consequence and cannot be certified from the XDF labels alone.
3. Rebuild Alpha-N, 2048/4096 MAF, boost/load extension and injection
   calculation as one dependent family. Reconcile the canonical patchlist with
   the unproved Load_Extend fork.
4. Rebuild DS2 baud/speed/logger patches after mapping code-cave collisions and
   proving the protocol/control flow.
5. Keep immobilizer/checksum-bypass/clear-data in a separate bench/recovery
   lane. Cosmetic cluster/MIL/CAN patches follow engine-control work.

Historical full-image code variants are `LEGACY_REFERENCE`. Their filenames
describe intent only; reconstruct from the clean exact parent and never carry
their program regions forward wholesale.

## MS43X001

- Repository checkpoint: `ms43x-custom-firmware` commit
  `8782120b1917205728be0935c56f58d87f26e823`.
- Official 512 KiB XDF SHA-256:
  `D4311E9DFF6258887370880DB8FFEBC517FB0F24614D32CD940AB35ED12E302E`.
- The XDF uses `BASEOFFSET 0x70000` and contains no XDF patch objects. MS43X
  features are integrated firmware plus loose ASM, so stock-MS43 patch offsets
  and the current strict BASEOFFSET-zero patcher do not apply.
- All 33 catalogued 43X001 paths/13 unique BINs share the same executable-code
  SHA; local turbo/ghost/RAL variants are calibration changes, not proof of a
  new ASM build.

### Rebuild priorities

1. Disassemble each exact official release and resolve the crossed NLS/RAL
   labels, active-bit branch-direction disagreement, apparent injection-source
   typo, and source/default-versus-release mismatches before changing ASM.
2. Rebuild LC/RAL/NLS, AFR override and RPM-limiter behavior against the exact
   compiled release, not the loose source alone.
3. Keep MAFless/speed-density, boost and injection work blocked until active
   table selection, sensor transfer, load/torque consumers and hardware limits
   are traced.

## Formula and XDF correction queue

### P0 — correct known wrong targets or schemas

#### VY final-drive ratio

- XDF/file address `0x705A-0x705B` is a 16-bit big-endian Q14 word. The stock
  raw word is `0xC51F`.
- The production XDF incorrectly declares an 8-bit item using `X*2**14`.
- Correct display candidate: `X/16384`; the stock value displays about
  `3.080017`.
- Action: rebuild the XDF item width/storage/equation and prove native display,
  inverse encoding and round trip before replacing the production definition.

#### MS43X wrong ignition table

- The customer v2 changed `ip_iga_optm_ron98__n__maf`, ID `0x1B50`, XDF Z
  address `0x70A5`, instead of intended main
  `ip_iga_ron98_pl__n__maf`, ID `0x1BFE`, address `0x7315`.
- Both use `0.375*X-23.625`; the error was table selection, not conversion.
- The retained correction restores 15 wrong-table cells and changes exactly
  15 bytes at full-image offsets `0x77117..0x77149` versus v2. It is
  `CLI_CHECKED`; native TunerPro and vehicle proof remain due.
- Evidence:
  `1bmw_ms42_tuning_guides/community_intake/vexed_con_2026-09/ms43x_wrong_table_regression_20260920/`.

### P1 — retain proved math, revalidate physical meaning

#### VY injector calculations

- Instruction-proved raw pulse conversion:
  `milliseconds = X / 260 / 256 * 1000`.
- Multiplier arithmetic:
  `2 * ((scalar_hi * m) + round_half_up((scalar_lo * m) / 256))`, with raw
  multiplier `128` equal to unity.
- Recalculate injector voltage offset, minimum/default pulse width and the
  low-pulse row separately for stock and v48. Do not copy the stock `-0x20`
  row into v48 because v48 couples translation to `$7800`.
- Do not reuse v49 SPA_RES unchanged: its index step changes 16 to 8 counts and
  wraps at raw `0x80`, jumping row 8 to row 0.
- Arithmetic is statically proved; physical TIO/driver behavior needs
  six-injector bench data.

#### VY address corrections

- Historical CPU addresses `$14468/$21B0B/$24E3F` exceed HC11 space.
  Correct CPU forms are `$C468/$9B0B/$CE3F`; XDF locations remain file
  offsets with base offset zero.
- The claimed dwell file offset `0x1823F` was wrong. The corrected historical
  location `0x1023F` still needs exact-hash trace proof.

#### MS43X VE and related tables

- `ip_map_ve_2/5/6/7/8__map__n` are 16x16 unsigned-16 tables using
  `0.00097656252*X` (approximately `X/1024`). The official MS43X XDF and A2L
  support this formula; do not change it merely because values look unusual.
- Prove the active table through selector `ip_nr_ip_ve__vo` and VANOS state
  before accepting or modifying cells.
- `ip_ti_fl__n` uses `0.0039058823*X-0.5`; stock MS43 A2L evidence supports
  the equation, while the relocated MS43X address still needs a custom-code
  xref.

## Immediate execution order

1. Withdraw VY `0x6A10`, the retired spark-cut family, and the D1 downshift
   edit from all test queues.
2. Correct and native-check the VY final-drive XDF item.
3. Preserve the MS43X 15-cell wrong-table revert as a review-only regression
   fixture.
4. Build a common identity/layout/patch-manifest validator before producing
   new direct-patch binaries.
5. Native-check the checksum-valid, bounded MS42 throttle reconstruction and
   complete its exact-DME/recovery/write-readback gates; retain the five-map
   ghost-cam body for signedness/axis forensics only.
6. Bench the `STATIC_PROVED` MS42 DS2 logger with exact full-image readback;
   rebuild VY stationary launch and stock-MS43 cruise selector as the next
   exact-parent patch examples.
7. Bench the strongest retained VY v47/v48/v51 and ghost-cam candidates after
   their remaining control-flow proofs close.
8. Re-disassemble official MS43X releases and rebuild LC/RAL/NLS/AFR/limiter
   behavior from compiled code.
