/**
 * location_wba55.h — Sidewalk BLE network-location (Level 1) helper for the
 * sidewalk-location-wba55 example.
 *
 * Wraps the Amazon Sidewalk Location Library (SDK >= 1.19, full variant) to
 * request a BLE gateway-proximity location resolve. No GNSS/WiFi hardware and
 * no scan PALs are required: Level 1 ("Connected to Sidewalk via BLE") asks the
 * cloud to resolve position from the opted-in (Community Finding) gateway the
 * device is connected through — "no additional power draw".
 *
 * Requires the build to link the location-enabled Sidewalk archive
 * (sidewalk_sdk_full_stm32wba_ble.a) and to define SID_SDK_CONFIG_ENABLE_LOCATION=1.
 * Do NOT define SID_SDK_CONFIG_ENABLE_WIFI / _GNSS — this is BLE-only.
 */
#ifndef LOCATION_WBA55_H
#define LOCATION_WBA55_H

#include <stdbool.h>
#include <sid_error.h>

struct sid_handle;

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Initialize the location library for BLE-only Level-1 resolution.
 * Call once, after sid_init() returns SID_ERROR_NONE.
 *
 * @param handle  the handle returned by sid_init()
 * @return SID_ERROR_NONE on success
 */
sid_error_t location_wba55_init(struct sid_handle *handle);

/**
 * Request one BLE gateway-proximity location resolve (effort Level 1).
 * Call only when the Sidewalk link is READY and time-synced (i.e. the same
 * condition under which the stock app sends its counter uplink).
 *
 * Internally rate-limited: at most one request per LOCATION_WBA55_MIN_PERIOD_S
 * seconds (see .c) so we stay well inside Sidewalk location rate limits.
 *
 * @param handle  the handle returned by sid_init()
 * @return SID_ERROR_NONE if a request was queued,
 *         SID_ERROR_BUSY  if suppressed by the rate limiter (not an error).
 */
sid_error_t location_wba55_run(struct sid_handle *handle);

/**
 * Deinitialize the location library. Call before sid_deinit().
 */
sid_error_t location_wba55_deinit(struct sid_handle *handle);

#ifdef __cplusplus
}
#endif

#endif /* LOCATION_WBA55_H */
