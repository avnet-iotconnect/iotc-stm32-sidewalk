# SBDT / FUOTA changes for WBA55 — inventory & rollback

All changes are in the **STM32-Sidewalk-SDK** tree (not this iotc repo):
`/home/mlamp/dev/sidewalk/STM32-Sidewalk-SDK`. Each was made against otherwise-clean
files, so each can be reverted independently. Patches live in this folder.

## The changes (A–G)

| # | What | File | Category | Patch |
|---|------|------|----------|-------|
| A | `>>> OTA \|` human-readable log lines (transfer request/accept/reject, per-block receive, entire-image, finalize/validation) **plus `>>> OTA UPLINK \|` lines** for the FUOTA progress % and completion-status the device reports to the cloud | `apps/common/sid_app_sbdt_demo/sid_app_sbdt_demo.c` | logging | (in `sbdt_demo_logging_and_crc.patch`) |
| B | Call `sid_bulk_data_transfer_init()` to register SBDT rx handlers (fixes `NOSUPPORT -6`) | `apps/st/stm32wba/sid_sbdt_demo/STM32_WPAN/App/app_sidewalk.c` | functional fix | `sbdt_register_fix.patch` |
| C | **Space fix (two AIM flash bugs):** (1) erase page-align math `& (PAGE-1)` → `& ~(PAGE-1)` (fixes `STORAGE_ERASE_FAIL -32` on page-aligned blocks); (2) pad the final short OTA chunk up to the 16-byte flash word instead of rejecting it (fixes `write length … not aligned … (16 bytes)` on the last block → validation FAILED → AIM footer `0xFFFFFFFF`) | `apps/st/stm32wba/common/Core/Src/sid_application_install_manager_ifc.c` | space/flash | `aim_erase_align_fix.patch` |
| D | **Space fix:** accumulate the transfer CRC in RAM and drop the per-block KV read/write entirely (fixes `Prev CRC 0x0`, and silences the per-block `LittleFS: No more free space` / `COULD NOT STORE CRC` errors — the KV/LittleFS store is unusable on this board and not needed for a single-session OTA) | `apps/common/sid_app_sbdt_demo/sid_app_sbdt_demo.c` | space/flash | `crc_ram_fallback_fix.patch` |

| E | **Enhancement:** bump app version `1.1.0 → 1.1.1` (source of truth; regenerates the auto-generated `sid_app_version_cubeide.h`) | `apps/st/common/build_system/stm32_sidewalk_sdk_version.def` | enhancement | `ota_status_appversion_versionbump.patch` |
| F | **Enhancement:** report FUOTA completion (`ota_status` SUCCESS) via the AIM verification state (`AIMAVS_CONFIRMATION_PENDING` captured at boot) instead of the unusable KV `FILE_OTA_PENDING_KEY` flag — so the cloud actually receives a completion status | `apps/common/sid_app_sbdt_demo/sid_app_sbdt_demo.c` + `.../include/sid_app_sbdt_demo.h` (`ota_just_installed`) | enhancement | `ota_status_appversion_versionbump.patch` |
| G | **Enhancement:** append the app version (`SID_APP_PROJECT_*`) to the capability uplink as TLV tag `0x14`, distinct from the SDK `fw_version` (0x0F). Decoders `sidewalk-stm32-unified-v2.py` (flat) and `-v3.py` (`app_version` in the `ota` object) decode it | `apps/common/sid_app_sbdt_demo/sid_app_sbdt_demo.c` + `decoders/sidewalk-stm32-unified-v2.py` / `-v3.py` | enhancement | `ota_status_appversion_versionbump.patch` (firmware only; decoders are git-tracked in the iotc repo) |

`sbdt_demo_logging_and_crc.patch` is the full diff of that file (A + D together);
`crc_ram_fallback_fix.patch` isolates just D so the space fixes can be reverted on their own.
`ota_status_appversion_versionbump.patch` bundles E + F + G (isolated from A/B/C/D).

## Roll back ONLY the enhancements (E + F + G)

Reverts the version bump, the ota_status fix, and the app_version uplink, while KEEPING
logging (A), SBDT registration (B), and the space/CRC fixes (C, D). Decoder changes are
separate (plain git-tracked files in the iotc repo).

```bash
examples/sidewalk-sbdt-demo-wba55/dev-notes/rollback-enhancements.sh            # revert E+F+G
examples/sidewalk-sbdt-demo-wba55/dev-notes/rollback-enhancements.sh --reapply  # restore them
# then rebuild + reflash the app
```
(Verified: revert → reapply cycle leaves A/B/C/D untouched.)

## Roll back ONLY the space-related fixes (C + D)

This returns C and D to the original ST behavior while KEEPING the logging (A) and the
SBDT-registration fix (B):

```bash
examples/sidewalk-sbdt-demo-wba55/dev-notes/rollback-space-fixes.sh
# then rebuild + reflash the app (see "Rebuild" below)
```

Re-apply them again:

```bash
examples/sidewalk-sbdt-demo-wba55/dev-notes/rollback-space-fixes.sh --reapply
```

(The script does `git apply -R aim_erase_align_fix.patch crc_ram_fallback_fix.patch`
in the SDK. Verified to reverse cleanly.)

## Revert an individual change

```bash
cd /home/mlamp/dev/sidewalk/STM32-Sidewalk-SDK
git apply -R examples-path/<patch>.patch      # reverse one patch, or:
git restore <file>                            # revert ALL changes in that file
```
Note `git restore` on `sid_app_sbdt_demo.c` reverts BOTH A and D (same file).
Do NOT run a repo-wide `git restore` — the SDK has other unrelated local changes.

## Rebuild (headless-build.sh is broken here — use make directly)

```bash
export PATH="/opt/st/stm32cubeide_1.18.0/plugins/com.st.stm32cube.ide.mcu.externaltools.gnu-tools-for-stm32.13.3.rel1.linux64_1.0.0.202410170706/tools/bin:$PATH"
BD=/home/mlamp/dev/sidewalk/STM32-Sidewalk-SDK/apps/st/stm32wba/sid_sbdt_demo/STM32CubeIDE/STM32WBA55/Debug_Nucleo-WBA55
make -C "$BD" -j"$(nproc)" all      # compiles + signs; outputs sid_sbdt_demo_wba55.hex + _ota_image.{bin,hex}
```
Then copy outputs into `binaries/sid_sbdt_demo/` and reflash the app:
```bash
STM32_Programmer_CLI -c port=SWD mode=UR -d binaries/sid_sbdt_demo/sid_sbdt_demo_wba55.hex -v -rst
```

## Notes

- `-32` = `SID_ERROR_STORAGE_ERASE_FAIL`; `-6` = `SID_ERROR_NOSUPPORT` (not INVALID_ARGS).
- Change C is an **upstream ST bug** (SDK commit be294bf), not introduced here.
- The LittleFS `No more free space` root cause was never fully pinned (mount/format is in
  the prebuilt KV lib); change D works around it so a single-session OTA succeeds without KV.
- These `binaries/sid_sbdt_demo/*.hex` are untracked build artifacts and can be wiped by
  `git clean`; regenerate with the Rebuild step above.
