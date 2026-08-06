/**
 * location_wba55.c — see location_wba55.h.
 *
 * Built against Amazon Sidewalk SDK 1.19.4.20 (STM32-Sidewalk-SDK full variant).
 * Verified against that release's sid_location.h:
 *   - struct sid_location_config { type_mask, callbacks, max_effort,
 *                                  manage_effort, stepdowns, fragmentation }
 *   - sid_location_init / _run / _deinit
 *   - SID_LOCATION_METHOD_BLE_GATEWAY, SID_LOCATION_EFFORT_L1/_DEFAULT,
 *     SID_LOCATION_SCAN_AND_SEND
 *
 * NOTE: this SDK's location library predates the "resolve_location on a user
 * message" piggyback API (Location Library Guide PS 1.0 Rev A, §2.7). Here we
 * use the dedicated sid_location_run() path, which is the correct tool for a
 * location-only proof and does not depend on that newer revision.
 *
 * >>> On-target validation needed: confirm the include path for the SID_PAL_LOG_*
 * macros matches your tree (app_sidewalk.c pulls them in already) and that the
 * Level-1 request is issued only on a time-synced BLE connection.
 */

#include "location_wba55.h"

#include <sid_api.h>
#include <sid_location.h>
#include <sid_pal_log_ifc.h>   /* SID_PAL_LOG_* — same source app_sidewalk.c uses */

/* Minimum seconds between Level-1 requests. The stock demo task ticks every
 * ~15 s; resolving location that often is wasteful and risks rate limiting.
 * One resolve every 2 min is plenty for a bench proof — tune as needed. */
#ifndef LOCATION_WBA55_MIN_PERIOD_S
#define LOCATION_WBA55_MIN_PERIOD_S (120u)
#endif

static bool     s_inited = false;
static uint32_t s_last_run_gps_s = 0u;   /* 0 = never run */

static const char *status_str(enum sid_location_status st)
{
    switch (st) {
        case SID_LOCATION_LVL1_READY:       return "LVL1_READY (BLE gateway location available)";
        case SID_LOCATION_LVL1_UNAVAILABLE: return "LVL1_UNAVAILABLE (no opted-in gateway in range)";
        case SID_LOCATION_SEND_DONE:        return "SEND_DONE";
        case SID_LOCATION_SCAN_DONE:        return "SCAN_DONE";
        default:                            return "UNKNOWN";
    }
}

/* Dump a byte buffer as hex over UART, 16 bytes/line so each line stays well
 * under SID_PAL_LOG_MSG_LENGTH_MAX. Manual nibble formatting avoids relying on
 * printf field-width support in the tiny-printf build. */
static void log_payload_hex(const uint8_t *buf, size_t len)
{
    static const char hex[] = "0123456789ABCDEF";
    char line[3 * 16 + 1];   /* "XX " per byte, 16 bytes, + NUL */
    for (size_t off = 0; off < len; off += 16) {
        size_t n = (len - off) < 16u ? (len - off) : 16u;
        size_t p = 0;
        for (size_t i = 0; i < n; i++) {
            const uint8_t b = buf[off + i];
            line[p++] = hex[(b >> 4) & 0x0Fu];
            line[p++] = hex[b & 0x0Fu];
            line[p++] = ' ';
        }
        line[p] = '\0';
        SID_PAL_LOG_INFO("LOC: payload[%02u]: %s", (unsigned)off, line);
    }
}

/* Asynchronous result of a location request. This is the device-side proof that
 * the resolve left the device; the resolved coordinates themselves are produced
 * cloud-side and delivered to the AWS location destination, not back to here. */
static void location_callback(const struct sid_location_result *const result, void *context)
{
    (void)context;
    if (result == NULL) {
        return;
    }
    if (result->err != SID_ERROR_NONE) {
        SID_PAL_LOG_WARNING("LOC: result status=%s err=%d mode=%d",
                            status_str(result->status), (int)result->err, (int)result->mode);
        return;
    }
    SID_PAL_LOG_INFO("LOC: result status=%s mode=%d link=%d",
                     status_str(result->status), (int)result->mode, (int)result->link);

    /* Raw uplink payload inspection. NOTE: this is the gateway-proximity data the
     * device sends UP for cloud-side resolution — it is NOT a resolved lat/lon
     * (no coordinate ever returns to the device on the BLE L1 path). Decoding it
     * requires the Amazon location-protocol spec. Logged here only as a debug aid. */
    if (result->size > 0u) {
        size_t n = result->size;
        if (n > SID_LOCATION_MAX_PAYLOAD_SIZE) {
            n = SID_LOCATION_MAX_PAYLOAD_SIZE;
        }
        SID_PAL_LOG_INFO("LOC: uplink payload size=%u bytes (sent for cloud resolve, not a coordinate)",
                         (unsigned)result->size);
        log_payload_hex(result->payload, n);
    }
}

sid_error_t location_wba55_init(struct sid_handle *handle)
{
    if (handle == NULL) {
        return SID_ERROR_INVALID_ARGS;
    }
    if (s_inited) {
        return SID_ERROR_NONE;
    }

    static struct sid_location_config cfg = {
        .sid_location_type_mask = SID_LOCATION_METHOD_BLE_GATEWAY, /* BLE only */
        .callbacks    = { .on_update = location_callback, .context = NULL },
        .max_effort   = SID_LOCATION_EFFORT_L1,
        /* manage_effort=false pins the request to a single, explicit effort mode.
         * With managed effort the library auto-escalates past L1 when no
         * consenting gateway is immediately available ("Trying next effort mode:
         * 3"); mode L3 needs a WiFi/GNSS scan PAL absent from this BLE-only build,
         * so sid_location_run() then returns SID_ERROR_NOSUPPORT (-6). BLE-only L1
         * must never escalate, so we disable managed effort and request L1 below. */
        .manage_effort = false,
        .stepdowns     = { 0 },  /* not applicable to BLE-only */
        .fragmentation = { 0 },  /* BLE needs no fragmentation */
    };

    sid_error_t ret = sid_location_init(handle, &cfg);
    if (ret != SID_ERROR_NONE) {
        SID_PAL_LOG_ERROR("LOC: sid_location_init failed: %d", (int)ret);
        return ret;
    }
    s_inited = true;
    SID_PAL_LOG_INFO("LOC: location library initialized (BLE gateway, L1)");
    return SID_ERROR_NONE;
}

sid_error_t location_wba55_run(struct sid_handle *handle)
{
    if (!s_inited || handle == NULL) {
        return SID_ERROR_INVALID_STATE;
    }

    /* Rate-limit using GPS time (same clock the demo app already reads). */
    struct sid_timespec now = { 0 };
    if (sid_get_time(handle, SID_GET_GPS_TIME, &now) == SID_ERROR_NONE) {
        const uint32_t now_s = (uint32_t)now.tv_sec;
        if ((s_last_run_gps_s != 0u) &&
            ((now_s - s_last_run_gps_s) < LOCATION_WBA55_MIN_PERIOD_S)) {
            return SID_ERROR_BUSY; /* suppressed by throttle — caller ignores */
        }
        s_last_run_gps_s = now_s;
    }

    /* BLE Level-1: no scan buffer; cloud resolves from gateway proximity.
     * Request L1 explicitly. SID_LOCATION_EFFORT_DEFAULT is only valid with
     * manage_effort=true (see header); since we disabled managed effort to stop
     * escalation to unsupported WiFi/GNSS modes, we must name the mode. */
    struct sid_location_run_config run_cfg = {
        .type   = SID_LOCATION_SCAN_AND_SEND,
        .mode   = SID_LOCATION_EFFORT_L1,
        .buffer = NULL,
        .size   = 0u,
    };

    sid_error_t ret = sid_location_run(handle, &run_cfg, 0u /* delay_s */);
    if (ret != SID_ERROR_NONE) {
        SID_PAL_LOG_ERROR("LOC: sid_location_run failed: %d", (int)ret);
    } else {
        SID_PAL_LOG_INFO("LOC: Level-1 BLE location resolve requested");
    }
    return ret;
}

sid_error_t location_wba55_deinit(struct sid_handle *handle)
{
    if (!s_inited) {
        return SID_ERROR_NONE;
    }
    sid_error_t ret = sid_location_deinit(handle);
    s_inited = false;
    s_last_run_gps_s = 0u;
    return ret;
}
