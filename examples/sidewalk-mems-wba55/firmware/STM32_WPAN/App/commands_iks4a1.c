/**
  ******************************************************************************
  * @file    commands_iks4a1.c
  * @brief   Downlink command dispatcher for the IKS4A1 demo. See header for
  *          wire format and supported opcodes.
  ******************************************************************************
  */

#include "commands_iks4a1.h"

#include <sid_pal_log_ifc.h>

#if defined(NUCLEO_WBA55_BOARD)
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
#if defined(NUCLEO_WBA55_BOARD)
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

bool commands_iks4a1_dispatch(const uint8_t *data, size_t size)
{
    if (data == NULL || size == 0u) {
        return false;
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
