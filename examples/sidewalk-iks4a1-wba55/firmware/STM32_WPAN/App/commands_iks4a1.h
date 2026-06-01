/**
  ******************************************************************************
  * @file    commands_iks4a1.h
  * @brief   Lightweight downlink command dispatcher for the IKS4A1 demo.
  *
  * Mirrors the opcode-routing pattern used by sid_app_demo (apps/common) but
  * without pulling in the full TLV parser. Wire format:
  *
  *     ofs  size  field
  *     0    1     opcode
  *     1    *     opcode-specific parameters (network / big-endian)
  *
  * Supported opcodes:
  *     0x01  CMD_LED_ON       (no params)            -> turn user LED on
  *     0x02  CMD_LED_OFF      (no params)            -> turn user LED off
  *     0x10  CMD_SET_INTERVAL (4 bytes uint32 BE s)  -> change uplink period,
  *                                                     clamped to [60, 3600]
  *
  * SET_INTERVAL uses big-endian (network byte order) to match the encoding
  * /IOTCONNECT applies to a numeric bytesCommandParameter. If your instance
  * emits little-endian, swap the byte order in cmd_set_interval().
  ******************************************************************************
  */

#ifndef COMMANDS_IKS4A1_H_
#define COMMANDS_IKS4A1_H_

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CMD_IKS4A1_LED_ON         (0x01u)
#define CMD_IKS4A1_LED_OFF        (0x02u)
#define CMD_IKS4A1_SET_INTERVAL   (0x10u)

/* Lower / upper bounds and default for set_interval, in seconds.
 * Tuned for Sidewalk BLE: the Echo tears the link down ~60 s after each
 * connect, so action frames must fire inside that window. With a 6 x 5 s
 * capability handshake the first action at the 15 s default lands at
 * ~45 s of connection uptime — comfortably inside the 60 s window — and
 * a second action frame typically squeezes in before the drop. */
#define CMD_IKS4A1_INTERVAL_MIN_S (10u)
#define CMD_IKS4A1_INTERVAL_MAX_S (3600u)
#define CMD_IKS4A1_INTERVAL_DFLT_S (15u)

/* Returns true if the message was a recognized command. data/size are the raw
 * bytes from on_sidewalk_msg_received(). */
bool commands_iks4a1_dispatch(const uint8_t *data, size_t size);

/* Demo task uses this to read the current uplink period in milliseconds. */
uint32_t commands_iks4a1_get_interval_ms(void);

#ifdef __cplusplus
}
#endif

#endif /* COMMANDS_IKS4A1_H_ */
