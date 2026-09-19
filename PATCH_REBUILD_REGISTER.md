# Patch and Formula Rebuild Register

**Updated:** 20 September 2026
**Scope:** Holden VY `$060A`, stock BMW MS43 `430069`, and MS43X001
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
5. Rebuild VY stationary launch and stock-MS43 cruise selector as the first two
   exact-parent examples.
6. Bench the strongest retained VY v47/v48/v51 and ghost-cam candidates after
   their remaining control-flow proofs close.
7. Re-disassemble official MS43X releases and rebuild LC/RAL/NLS/AFR/limiter
   behavior from compiled code.
