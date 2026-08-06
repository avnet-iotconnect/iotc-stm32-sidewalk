/**
  ******************************************************************************
  * @file    sensors_iks4a1.h
  * @brief   Thin abstraction over the X-CUBE-MEMS1 IKS4A1 BSP for the
  *          Sidewalk-over-BLE example. Reads LSM6DSV16X (accel + gyro),
  *          LPS22DF (pressure), SHT40AD1B (humidity + temp) and STTS22H
  *          (temp), and packs a TLV uplink payload compatible with both:
  *
  *            - the existing /IOTCONNECT 'STsidewalk2' decoder (temperature
  *              only, via tag 0x06)
  *            - a new sidewalk_iks4a1_tlv.py decoder that surfaces every
  *              IKS4A1 sensor (custom tags 0x20-0x27)
  *
  *          Wire format (sid_demo-style TLV, little-endian values):
  *            byte  0   : msg_desc = 0x40 (opc=NOTIFY, no status header)
  *            bytes 1.. : TLV stream of (header + length + value)
  *                          header = (size_type << 6) | (tag & 0x3F)
  *                          size_type 0 -> 1-byte length
  *                          size_type 1 -> 2-byte length
  *                          size_type 2 -> 4-byte length
  *
  *          See sidewalk_iks4a1_tlv.py in iotc-stm32-sidewalk for the
  *          decoder side.
  ******************************************************************************
  */

#ifndef SENSORS_IKS4A1_H_
#define SENSORS_IKS4A1_H_

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SENSORS_IKS4A1_PROTO_VERSION       (0x01u)

/* Worst-case TLV-encoded uplink size (msg_desc + 9 TLV entries):
 *   msg_desc           : 1
 *   TAG_TEMP (0x06)    : 1 + 1 + 2 = 4
 *   IKS_VERSION        : 1 + 1 + 1 = 3
 *   IKS_SEQUENCE       : 1 + 1 + 1 = 3
 *   IKS_ACCEL          : 1 + 1 + 6 = 8
 *   IKS_GYRO           : 1 + 1 + 6 = 8
 *   IKS_STTS22H_X100   : 1 + 1 + 2 = 4
 *   IKS_SHT40_X100     : 1 + 1 + 2 = 4
 *   IKS_HUMIDITY_X100  : 1 + 1 + 2 = 4
 *   IKS_PRESSURE_X100  : 1 + 1 + 4 = 6
 *   ----------------------------- = 45  (rounded up below)
 */
#define SENSORS_IKS4A1_PAYLOAD_MAX_SIZE    (96u)

/* sid_demo TLV tags (apps/common/sid_demo_parser/include/sid_demo_types.h).
 * Re-using these lets the /IOTCONNECT-approved sid_demo decoder surface the
 * standard fields (sensor_data, gps_time, link_type, etc.) for our device
 * exactly the way it does for the Nordic reference firmware. */
#define TAG_NUMBER_OF_BUTTONS                (0x01u)
#define TAG_NUMBER_OF_LEDS                   (0x02u)
#define TAG_TEMPERATURE_SENSOR_DATA_NOTIFY   (0x06u)
#define TAG_CURRENT_GPS_TIME_IN_SECONDS      (0x07u)
#define TAG_TEMP_SENSOR_AVAILABLE_UNIT       (0x0Bu)
#define TAG_LINK_TYPE                        (0x0Cu)
#define TAG_OTA_SUPPORTED                    (0x0Eu)

/* IKS4A1-specific TLV tags (above sid_demo's 0x01..0x13 range; unknown to
 * decoders that follow sid_demo conventions, so they get silently skipped). */
#define TAG_IKS4A1_VERSION                 (0x20u)
#define TAG_IKS4A1_SEQUENCE                (0x21u)
#define TAG_IKS4A1_ACCEL                   (0x22u)
#define TAG_IKS4A1_GYRO                    (0x23u)
#define TAG_IKS4A1_TEMP_STTS22H_X100       (0x24u)
#define TAG_IKS4A1_TEMP_SHT40_X100         (0x25u)
#define TAG_IKS4A1_HUMIDITY_X100           (0x26u)
#define TAG_IKS4A1_PRESSURE_X100           (0x27u)
#define TAG_IKS4A1_ORIENTATION             (0x28u)  /* u8 enum, see sensors_iks4a1_orient_t */
#define TAG_IKS4A1_QVAR_RAW                (0x29u)  /* i16le, raw LIS2DUXS12 Qvar count */
#define TAG_IKS4A1_MLC1                    (0x2Au)  /* u8, LSM6DSV16X MLC1_SRC raw label
                                                       (asset_tracking UCF: 0=stationary_upright,
                                                       4=stationary_not_upright, 8=in_motion, 12=shaken) */
#define TAG_IKS4A1_MLC1_MODEL              (0x2Bu)  /* u8, identifies which UCF/decision tree is
                                                       loaded; the decoder uses this to pick the
                                                       right raw-value -> label map. See the
                                                       SENSORS_IKS4A1_MLC1_MODEL_* enum. */

/* MLC1 model identifier — emitted on the wire so the decoder can pick the
 * right label dictionary for the raw MLC1_SRC value. When you change the
 * .ucf you load in sensors_iks4a1_init(), bump the value here AND register
 * the matching label map in the decoder. Old decoders that don't know a new
 * model ID fall back to surfacing the raw integer untranslated, which is
 * graceful (no crash, just no label string). */
#define SENSORS_IKS4A1_MLC1_MODEL_NONE             (0u) /* MLC not loaded / not wired */
#define SENSORS_IKS4A1_MLC1_MODEL_ASSET_TRACKING   (1u) /* lsm6dsv16x_asset_tracking.ucf (IKS4A1) or
                                                           ism6hg256x_asset_tracking (IKS5A1) —
                                                           same algorithm, same 0/4/8/12 classes */
#define SENSORS_IKS4A1_MLC1_MODEL_ACTIVITY_MOBILE  (2u) /* lsm6dsv16x_activity_recognition_for_mobile.ucf  (reserved) */
#define SENSORS_IKS4A1_MLC1_MODEL_ACTIVITY_WRIST   (3u) /* activity_recognition_for_wrist                 (reserved) */
#define SENSORS_IKS4A1_MLC1_MODEL_GYM_ACTIVITY     (4u) /* gym_activity_recognition                       (reserved) */
#define SENSORS_IKS4A1_MLC1_MODEL_HEAD_GESTURES    (5u) /* head_gestures                                  (reserved) */
#define SENSORS_IKS4A1_MLC1_MODEL_YOGA_POSE        (6u) /* yoga_pose_recognition                          (reserved) */

/* msg_desc bytes per sid_demo encoding:
 *   bit 7    : status_hdr_ind
 *   bits 6-5 : opc           (2 = NOTIFY, 3 = RESP)
 *   bits 4-3 : cmd_class     (0 = DEMO_APP)
 *   bits 2-0 : cmd_id        (0 = CAP_DISCOVERY, 1 = ACTION)
 *
 * Capability discovery notify : status=0 opc=2 class=0 cmd=0 -> 0x40
 * Action notification         : status=0 opc=2 class=0 cmd=1 -> 0x41
 * Capability response (DL)    : status=1 opc=3 class=0 cmd=0 -> 0xE0
 */
#define SENSORS_IKS4A1_MSG_DESC_NOTIFY_CAP     (0x40u)
#define SENSORS_IKS4A1_MSG_DESC_NOTIFY_ACTION  (0x41u)
#define SENSORS_IKS4A1_MSG_DESC_RESP_CAP       (0xE0u)
/* Backward-compat alias for older callers that referenced the bare name. */
#define SENSORS_IKS4A1_MSG_DESC                SENSORS_IKS4A1_MSG_DESC_NOTIFY_ACTION

/* 6D orientation enum, matches the LSM6DSV16X native D6D_SRC bit positions
 * (face that is currently up). UNKNOWN = no face detected above threshold. */
typedef enum {
    SENSORS_IKS4A1_ORIENT_UNKNOWN     = 0,
    SENSORS_IKS4A1_ORIENT_X_POS_UP    = 1,   /* +X face up — landscape right */
    SENSORS_IKS4A1_ORIENT_X_NEG_UP    = 2,   /* -X face up — landscape left  */
    SENSORS_IKS4A1_ORIENT_Y_POS_UP    = 3,   /* +Y face up — portrait up     */
    SENSORS_IKS4A1_ORIENT_Y_NEG_UP    = 4,   /* -Y face up — portrait down   */
    SENSORS_IKS4A1_ORIENT_Z_POS_UP    = 5,   /* +Z face up — face-up         */
    SENSORS_IKS4A1_ORIENT_Z_NEG_UP    = 6,   /* -Z face up — face-down       */
} sensors_iks4a1_orient_t;

typedef struct {
    int16_t  acc_mg[3];          /* mg                 */
    int16_t  gyr_dps_x10[3];     /* dps * 10           */
    int16_t  stts22h_c_x100;     /* deg C * 100        */
    int16_t  sht40_temp_c_x100;  /* deg C * 100        */
    uint16_t sht40_rh_x100;      /* %RH * 100          */
    uint32_t lps22df_pa_x100;    /* hPa * 100 (cPa)    */
    uint8_t  orientation;        /* sensors_iks4a1_orient_t */
    int16_t  qvar_raw;           /* LIS2DUXS12 Qvar raw count (signed) */
    uint8_t  mlc1_raw;           /* LSM6DSV16X MLC1_SRC label (0/4/8/12 for asset_tracking) */
    uint8_t  mlc1_model_id;      /* SENSORS_IKS4A1_MLC1_MODEL_* — which UCF produced mlc1_raw */
} sensors_iks4a1_reading_t;

/* Returns 0 on success, negative on error. Safe to call from a FreeRTOS task. */
int  sensors_iks4a1_init(void);

/* Returns 0 on success, negative on error. Fills *out with latest readings.   */
int  sensors_iks4a1_read(sensors_iks4a1_reading_t *out);

/* Pack a sid_demo-compatible action notification (msg_desc 0x41) with the
 * latest reading plus high-resolution IKS4A1 tags. gps_time_s comes from
 * sid_get_time(SID_GET_GPS_TIME); pass 0 if unavailable.
 * buf must be at least SENSORS_IKS4A1_PAYLOAD_MAX_SIZE bytes.
 * Returns the actual number of bytes written, or 0 on parameter error. */
uint32_t sensors_iks4a1_pack(uint8_t *buf,
                              uint32_t buf_len,
                              uint8_t  seq,
                              uint32_t gps_time_s,
                              const sensors_iks4a1_reading_t *r);

/* Pack a sid_demo capability-discovery notification (msg_desc 0x40)
 * advertising the device's button/LED/sensor capabilities. Sent once per
 * connection until the cloud responds with the capability-discovery
 * response (msg_desc 0xE0). */
uint32_t sensors_iks4a1_pack_capability(uint8_t *buf, uint32_t buf_len);

#ifdef __cplusplus
}
#endif

#endif /* SENSORS_IKS4A1_H_ */
