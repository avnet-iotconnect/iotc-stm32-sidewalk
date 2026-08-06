/**
  ******************************************************************************
  * @file    commands_iks4a1.c
  * @brief   Downlink command dispatcher for the IKS4A1 demo. See header for
  *          wire format and supported opcodes.
  ******************************************************************************
  */

#include "commands_iks4a1.h"

#include <stdint.h>
#include <string.h>

#include <sid_pal_log_ifc.h>

#if defined(NUCLEO_WBA55_BOARD) || defined(NUCLEO_WBA65_BOARD)
#  include "stm32wbaxx_nucleo.h"
#endif

/* Default uplink period (ms). Read by the demo task via
 * commands_iks4a1_get_interval_ms(). Updated atomically as a 32-bit write
 * from the on_sidewalk_msg_received() callback context. */
static volatile uint32_t s_interval_ms = CMD_IKS4A1_INTERVAL_DFLT_S * 1000u;

uint32_t commands_iks4a1_get_interval_ms(void)
{
    return s_interval_ms;
}

static void cmd_led_set(bool on)
{
#if defined(NUCLEO_WBA55_BOARD) || defined(NUCLEO_WBA65_BOARD)
    if (on) {
        BSP_LED_On(LED_BLUE);
    } else {
        BSP_LED_Off(LED_BLUE);
    }
#else
    (void)on;
#endif
}

static void cmd_set_interval(const uint8_t *params, size_t size)
{
    if (size < 4u) {
        SID_PAL_LOG_WARNING("CMD set_interval: short payload (%u)", (unsigned)size);
        return;
    }

    /* Big-endian uint32 to match the byte order /IOTCONNECT emits when
     * encoding a numeric bytesCommandParameter of integer type. */
    uint32_t secs = ((uint32_t)params[0] << 24)
                  | ((uint32_t)params[1] << 16)
                  | ((uint32_t)params[2] <<  8)
                  |  (uint32_t)params[3];

    if (secs < CMD_IKS4A1_INTERVAL_MIN_S) {
        secs = CMD_IKS4A1_INTERVAL_MIN_S;
    } else if (secs > CMD_IKS4A1_INTERVAL_MAX_S) {
        secs = CMD_IKS4A1_INTERVAL_MAX_S;
    }

    s_interval_ms = secs * 1000u;
    SID_PAL_LOG_INFO("CMD set_interval -> %lu s", (unsigned long)secs);
}

/* Byte-safe substring search. Returns offset of needle in haystack, or
 * SIZE_MAX if not found. */
static size_t s_find_substr(const uint8_t *hay, size_t hlen, const char *needle)
{
    size_t nlen = strlen(needle);
    if (nlen == 0u || nlen > hlen) {
        return SIZE_MAX;
    }
    for (size_t i = 0u; i + nlen <= hlen; i++) {
        if (memcmp(&hay[i], needle, nlen) == 0) {
            return i;
        }
    }
    return SIZE_MAX;
}

/* Skip JSON structural whitespace/punctuation, then parse a decimal integer.
 * Returns 0 if no digits are found at/after start. */
static uint32_t s_parse_uint_after(const uint8_t *data, size_t size, size_t start)
{
    while (start < size) {
        uint8_t c = data[start];
        if (c == ' ' || c == '\t' || c == '\n' || c == '\r' ||
            c == ':' || c == ',' || c == '"') {
            start++;
        } else {
            break;
        }
    }
    uint32_t val = 0u;
    bool found_digit = false;
    while (start < size && data[start] >= '0' && data[start] <= '9') {
        val = val * 10u + (uint32_t)(data[start] - '0');
        found_digit = true;
        start++;
    }
    return found_digit ? val : 0u;
}

/* Accept the wire payload as ASCII text (raw command name or full JSON) and
 * dispatch the matching command. This is a permissive substring match so
 * /IOTCONNECT can drive the device without a downlink-translator Lambda:
 *
 *   "IKS4A1_LED_ON"                                            -> LED on
 *   "IKS4A11_LED_ON"                                           -> LED on  (tolerates the deployed template's typo)
 *   "{\"command\":\"IKS4A1_LED_ON\"}"                          -> LED on
 *   "IKS4A1_LED_OFF"                                           -> LED off
 *   "{\"command\":\"IKS4A1_SET_INTERVAL\",
 *     \"interval_seconds\":30}"                                -> set interval to 30 s
 *
 * Returns true if a text command was recognised and dispatched. */
static bool try_parse_text_command(const uint8_t *data, size_t size)
{
    if (size < 5u) {
        return false;
    }
    uint8_t c = data[0];
    /* Quick prefilter: only attempt text parsing if the first byte looks like
     * ASCII text. The opcode-byte format uses 0x01/0x02/0x10, none of which
     * collide with '{', 'I', or '"'. */
    if (c != '{' && c != 'I' && c != 'i' && c != '"') {
        return false;
    }

    /* Check SET_INTERVAL first — LED_ON is a substring of (some) longer
     * names so we want the more specific match to win. */
    if (s_find_substr(data, size, "SET_INTERVAL") != SIZE_MAX) {
        uint32_t secs = 0u;
        size_t k = s_find_substr(data, size, "interval_seconds");
        if (k != SIZE_MAX) {
            secs = s_parse_uint_after(data, size, k + strlen("interval_seconds"));
        }
        /* Reuse cmd_set_interval(); it already clamps to MIN/MAX and writes
         * s_interval_ms. Synthesise the 4-byte big-endian param. */
        uint8_t params[4];
        params[0] = (uint8_t)(secs >> 24);
        params[1] = (uint8_t)(secs >> 16);
        params[2] = (uint8_t)(secs >>  8);
        params[3] = (uint8_t)(secs);
        SID_PAL_LOG_INFO("CMD set_interval (text) requested=%lu s", (unsigned long)secs);
        cmd_set_interval(params, 4u);
        return true;
    }

    /* LED_OFF must be checked before LED_ON because "LED_OFF" contains "LED_O"
     * but not "LED_ON". Order matters: LED_OFF first to avoid a false match. */
    if (s_find_substr(data, size, "LED_OFF") != SIZE_MAX) {
        SID_PAL_LOG_INFO("CMD led_off (text)");
        cmd_led_set(false);
        return true;
    }

    if (s_find_substr(data, size, "LED_ON") != SIZE_MAX) {
        SID_PAL_LOG_INFO("CMD led_on (text)");
        cmd_led_set(true);
        return true;
    }

    return false;
}

bool commands_iks4a1_dispatch(const uint8_t *data, size_t size)
{
    if (data == NULL || size == 0u) {
        return false;
    }

    /* Try ASCII / JSON parsing first so /IOTCONNECT can drive the device
     * without a downlink-translator Lambda. Falls through to opcode-byte
     * dispatch on no match. */
    if (try_parse_text_command(data, size)) {
        return true;
    }

    const uint8_t opcode  = data[0];
    const uint8_t *params = (size > 1u) ? &data[1] : NULL;
    const size_t   pn     = size - 1u;

    switch (opcode) {
        case CMD_IKS4A1_LED_ON:
            SID_PAL_LOG_INFO("CMD led_on");
            cmd_led_set(true);
            return true;

        case CMD_IKS4A1_LED_OFF:
            SID_PAL_LOG_INFO("CMD led_off");
            cmd_led_set(false);
            return true;

        case CMD_IKS4A1_SET_INTERVAL:
            cmd_set_interval(params, pn);
            return true;

        default:
            SID_PAL_LOG_WARNING("CMD: unknown opcode 0x%02X (size=%u)",
                                (unsigned)opcode, (unsigned)size);
            return false;
    }
}
