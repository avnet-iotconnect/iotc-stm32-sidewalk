/**
  ******************************************************************************
  * @file    sensors_iks5a1.c
  * @brief   IKS5A1 implementation of the sensors_iks4a1 abstraction. Same TLV
  *          wire format, same /IOTCONNECT decoder + template, but sourced from
  *          the IKS5A1 sensor stack (ISM6HG256X + IIS2DULPX + ILPS22QS) instead
  *          of IKS4A1's (LSM6DSV16X + LIS2DUXS12 + LPS22DF + SHT40 + STTS22H).
  *
  *          Build with SID_APP_IKS5A1_ENABLED=1 and SID_APP_IKS4A1_ENABLED=0
  *          to flash an X-NUCLEO-IKS5A1-stacked Nucleo-WBA55. The two boards
  *          are mutually exclusive — see the #error guard below.
  *
  * Sensor mapping (IKS5A1 -> IKS4A1 TLV tag):
  *   ISM6HG256X accel       -> tag 0x22  (acc_*_g)        — clean
  *   ISM6HG256X gyro        -> tag 0x23  (gyr_*_dps)      — clean
  *   ISM6HG256X 6D          -> tag 0x28  (orientation)    — NOT WIRED YET
  *                                                          (BSP wrapper lacks
  *                                                          6D Ex; would
  *                                                          require direct
  *                                                          register access)
  *   IIS2DULPX Qvar         -> tag 0x29  (qvar)           — clean
  *   ISM6HG256X MLC1        -> tags 0x2A/0x2B (mlc1)      — asset_tracking UCF
  *                                                          (same classes/model
  *                                                          id as IKS4A1)
  *   ILPS22QS  pressure     -> tag 0x27  (pressure_hpa)   — clean
  *   ILPS22QS  temperature  -> tag 0x06 + tag 0x24        — populated under
  *                                                          temp_stts22h_c
  *                                                          (semantic stretch:
  *                                                          there's no STTS22H
  *                                                          die on IKS5A1)
  *   no SHT40 -> tag 0x25 (temp_sht40_c) and 0x26 (humidity_sht40_pct)
  *               NOT emitted; the decoder leaves those fields absent.
  ******************************************************************************
  */

#include "sensors_iks4a1.h"    /* shared struct + TLV tag definitions */

#include <stdbool.h>
#include <string.h>
#include <sid_pal_log_ifc.h>

#if defined(SID_APP_IKS5A1_ENABLED) && (SID_APP_IKS5A1_ENABLED == 1)

#if defined(SID_APP_IKS4A1_ENABLED) && (SID_APP_IKS4A1_ENABLED == 1)
#  error "SID_APP_IKS4A1_ENABLED and SID_APP_IKS5A1_ENABLED are mutually exclusive (one sensor board at a time)."
#endif

#include "iks5a1_motion_sensors.h"
#include "iks5a1_motion_sensors_ex.h"
#include "iks5a1_env_sensors.h"
#include "stm32wbaxx_nucleo_bus.h"

/* ISM6HG256X MLC asset-tracking decision tree. ucf_line_t[] of (reg, val)
 * pairs converted from ST's official st-mems-machine-learning-core example
 * (same Smart Asset Tracking algorithm and MLC1_SRC classes as the
 * LSM6DSV16X variant on IKS4A1 — the cloud decoder model is shared). */
#include "ism6hg256x_asset_tracking.h"

/* ISM6HG256X registers we touch directly to read MLC inference output.
 * Same layout as the LSM6DSV16X: FUNC_CFG_ACCESS bit7 selects the EMB_FUNC
 * bank where MLC1_SRC lives. */
#define ISM6HG256X_REG_FUNC_CFG_ACCESS     (0x01u)
#define ISM6HG256X_FUNC_CFG_EMB_FUNC_BANK  (0x80u)  /* bit 7 = EMB_FUNC_REG_ACCESS */
#define ISM6HG256X_FUNC_CFG_MAIN_BANK      (0x00u)
#define ISM6HG256X_EMB_REG_MLC1_SRC        (0x70u)  /* in EMB_FUNC bank */

/* IIS2DULPX Qvar registers (same layout as LIS2DUXS12 — both AH/Qvar parts). */
#define IIS2DULPX_REG_OUT_T_AH_QVAR_L   (0x2Eu)
#define IIS2DULPX_REG_OUT_T_AH_QVAR_H   (0x2Fu)
#define IIS2DULPX_REG_AH_QVAR_CFG       (0x31u)
#define IIS2DULPX_AH_QVAR_CFG_ENABLE    (0x40u)   /* ah_qvar_en=1, defaults rest */

static int16_t  s_clamp_i16(int32_t v);
static uint16_t s_clamp_u16(int32_t v);

/* See sensors_iks4a1.c for the rationale — IKS5A1 BSP wrappers have the same
 * NULL-deref gotcha on Read_Register / Write_Register when init failed. */
static bool s_iis2dulpx_ok = false;
static bool s_mlc1_ok      = false;

int sensors_iks4a1_init(void)
{
    int32_t rc;

    s_iis2dulpx_ok = false;
    s_mlc1_ok      = false;

    if (BSP_I2C1_Init() != BSP_ERROR_NONE) {
        SID_PAL_LOG_ERROR("IKS5A1: I2C1 bus init failed");
        return -10;
    }

    /* ISM6HG256X — primary IMU (accel + gyro). */
    rc = IKS5A1_MOTION_SENSOR_Init(IKS5A1_ISM6HG256X_0, MOTION_ACCELERO | MOTION_GYRO);
    if (rc != BSP_ERROR_NONE) {
        SID_PAL_LOG_ERROR("IKS5A1: ISM6HG256X init failed (%ld)", (long)rc);
        return -1;
    }
    (void)IKS5A1_MOTION_SENSOR_Enable(IKS5A1_ISM6HG256X_0, MOTION_ACCELERO);
    (void)IKS5A1_MOTION_SENSOR_Enable(IKS5A1_ISM6HG256X_0, MOTION_GYRO);

    /* ILPS22QS — pressure + on-die temperature. */
    rc = IKS5A1_ENV_SENSOR_Init(IKS5A1_ILPS22QS_0, ENV_PRESSURE | ENV_TEMPERATURE);
    if (rc != BSP_ERROR_NONE) {
        SID_PAL_LOG_ERROR("IKS5A1: ILPS22QS init failed (%ld)", (long)rc);
        return -2;
    }
    (void)IKS5A1_ENV_SENSOR_Enable(IKS5A1_ILPS22QS_0, ENV_PRESSURE);
    (void)IKS5A1_ENV_SENSOR_Enable(IKS5A1_ILPS22QS_0, ENV_TEMPERATURE);

    /* IIS2DULPX — accelerometer + Qvar capacitive front-end. We don't read its
     * accel (ISM6HG256X is the primary IMU); just use the AH/Qvar channel. */
    rc = IKS5A1_MOTION_SENSOR_Init(IKS5A1_IIS2DULPX_0, MOTION_ACCELERO);
    if (rc != BSP_ERROR_NONE) {
        SID_PAL_LOG_WARNING("IKS5A1: IIS2DULPX init failed (%ld) - qvar disabled", (long)rc);
    } else {
        s_iis2dulpx_ok = true;
        (void)IKS5A1_MOTION_SENSOR_Enable(IKS5A1_IIS2DULPX_0, MOTION_ACCELERO);
        if (IKS5A1_MOTION_SENSOR_Write_Register(IKS5A1_IIS2DULPX_0,
                                                IIS2DULPX_REG_AH_QVAR_CFG,
                                                IIS2DULPX_AH_QVAR_CFG_ENABLE) == BSP_ERROR_NONE) {
            SID_PAL_LOG_INFO("IKS5A1: IIS2DULPX Qvar enabled");
        } else {
            SID_PAL_LOG_WARNING("IKS5A1: IIS2DULPX Qvar enable write failed");
        }
    }

    /* TODO: 6D orientation via ISM6HG256X. The IKS5A1 BSP wrapper does not
     * expose Enable_6D_Orientation / Get_6D_Orientation_*, so adding it
     * requires either an IKS5A1 BSP patch or direct register access via
     * Write/Read_Register. For now the orientation TLV (tag 0x28) reports
     * UNKNOWN. */

    /* ISM6HG256X MLC — asset-tracking decision tree (same algorithm/classes as
     * the LSM6DSV16X one on IKS4A1). Flat (register, value) write sequence:
     * SW procedure, EMB_FUNC bank, ODR/full-scale (30 Hz LP, +-16 g), filter
     * chain, features, decision tree, and finally back to the main bank.
     * Note the UCF's tail leaves the gyro ODR off (CTRL2=0x00) — same accepted
     * behavior as the IKS4A1 variant; gyro TLVs read zero while MLC is active.
     * MLC needs ~0.5 s before its first stable inference; sensors_iks4a1_read()
     * polls MLC1_SRC each cycle, so we just let it ride. */
    {
        const size_t n = sizeof(ism6hg256x_asset_tracking) / sizeof(ucf_line_t);
        size_t bad = 0u;
        for (size_t i = 0u; i < n; i++) {
            if (IKS5A1_MOTION_SENSOR_Write_Register(IKS5A1_ISM6HG256X_0,
                                                    ism6hg256x_asset_tracking[i].address,
                                                    ism6hg256x_asset_tracking[i].data) != BSP_ERROR_NONE) {
                bad++;
            }
        }
        if (bad != 0u) {
            SID_PAL_LOG_WARNING("IKS5A1: MLC UCF load: %u/%u writes failed",
                                 (unsigned)bad, (unsigned)n);
        } else {
            s_mlc1_ok = true;
            SID_PAL_LOG_INFO("IKS5A1: ISM6HG256X MLC (asset_tracking) loaded (%u writes)",
                              (unsigned)n);
        }
        /* Always force the bank back to main mode, success or failure — same
         * SWD-reflash safety rationale as the IKS4A1 loader (a sensor left in
         * the EMB_FUNC bank fails WHO_AM_I on the next warm Init()). */
        (void)IKS5A1_MOTION_SENSOR_Write_Register(IKS5A1_ISM6HG256X_0,
                                                  ISM6HG256X_REG_FUNC_CFG_ACCESS,
                                                  ISM6HG256X_FUNC_CFG_MAIN_BANK);
    }

    SID_PAL_LOG_INFO("IKS5A1: sensors initialized (ISM6HG256X + IIS2DULPX + ILPS22QS)");
    return 0;
}

int sensors_iks4a1_read(sensors_iks4a1_reading_t *out)
{
    if (out == NULL) {
        return -1;
    }
    memset(out, 0, sizeof(*out));

    IKS5A1_MOTION_SENSOR_Axes_t axes;
    int32_t rc;
    float   v;

    rc = IKS5A1_MOTION_SENSOR_GetAxes(IKS5A1_ISM6HG256X_0, MOTION_ACCELERO, &axes);
    if (rc == BSP_ERROR_NONE) {
        /* BSP returns accel in mg. */
        out->acc_mg[0] = s_clamp_i16(axes.x);
        out->acc_mg[1] = s_clamp_i16(axes.y);
        out->acc_mg[2] = s_clamp_i16(axes.z);
    } else {
        SID_PAL_LOG_WARNING("IKS5A1: ISM6HG256X accel read failed (%ld)", (long)rc);
    }

    rc = IKS5A1_MOTION_SENSOR_GetAxes(IKS5A1_ISM6HG256X_0, MOTION_GYRO, &axes);
    if (rc == BSP_ERROR_NONE) {
        /* BSP returns gyro in mdps. Scale to dps*10 to fit int16 over the full +-2000 dps range. */
        out->gyr_dps_x10[0] = s_clamp_i16(axes.x / 100);
        out->gyr_dps_x10[1] = s_clamp_i16(axes.y / 100);
        out->gyr_dps_x10[2] = s_clamp_i16(axes.z / 100);
    } else {
        SID_PAL_LOG_WARNING("IKS5A1: ISM6HG256X gyro read failed (%ld)", (long)rc);
    }

    /* ILPS22QS temperature — populated under stts22h_c_x100 (no STTS22H die
     * on the IKS5A1; the field name preserves the TLV tag mapping). */
    rc = IKS5A1_ENV_SENSOR_GetValue(IKS5A1_ILPS22QS_0, ENV_TEMPERATURE, &v);
    if (rc == BSP_ERROR_NONE) {
        out->stts22h_c_x100 = s_clamp_i16((int32_t)(v * 100.0f));
    } else {
        SID_PAL_LOG_WARNING("IKS5A1: ILPS22QS temp read failed (%ld)", (long)rc);
    }
    /* No SHT40 on IKS5A1 — sht40_temp_c_x100 / sht40_rh_x100 stay zero. */

    rc = IKS5A1_ENV_SENSOR_GetValue(IKS5A1_ILPS22QS_0, ENV_PRESSURE, &v);
    if (rc == BSP_ERROR_NONE) {
        int32_t scaled = (int32_t)(v * 100.0f);
        if (scaled < 0) {
            scaled = 0;
        }
        out->lps22df_pa_x100 = (uint32_t)scaled;
    } else {
        SID_PAL_LOG_WARNING("IKS5A1: ILPS22QS pressure read failed (%ld)", (long)rc);
    }

    /* Orientation — not yet implemented for IKS5A1; reports UNKNOWN. */
    out->orientation = (uint8_t)SENSORS_IKS4A1_ORIENT_UNKNOWN;

#if (USE_IKS5A1_MOTION_SENSOR_IIS2DULPX_0 == 1)
    /* IIS2DULPX Qvar — same register layout as LIS2DUXS12 (0x2E/0x2F). The
     * Read_Register BSP wrapper does NOT null-check MotionCompObj, so calling
     * it when IIS2DULPX init failed bus-faults. Gate on the runtime flag. */
    if (s_iis2dulpx_ok) {
        uint8_t lo = 0, hi = 0;
        if (IKS5A1_MOTION_SENSOR_Read_Register(IKS5A1_IIS2DULPX_0,
                                               IIS2DULPX_REG_OUT_T_AH_QVAR_L, &lo) == BSP_ERROR_NONE
         && IKS5A1_MOTION_SENSOR_Read_Register(IKS5A1_IIS2DULPX_0,
                                               IIS2DULPX_REG_OUT_T_AH_QVAR_H, &hi) == BSP_ERROR_NONE) {
            out->qvar_raw = (int16_t)(((uint16_t)hi << 8) | lo);
        }
    }
#endif

    /* ISM6HG256X MLC1_SRC inference label. Lives in the EMB_FUNC bank, so we
     * have to flip FUNC_CFG_ACCESS to bank-1 around the read and put it back.
     * Asset-tracking UCF outputs: 0=stationary_upright, 4=stationary_not_upright,
     * 8=in_motion, 12=shaken — identical to the IKS4A1/LSM6DSV16X model, so the
     * shared model id (asset_tracking = 1) and decoder label map apply as-is. */
    if (s_mlc1_ok) {
        if (IKS5A1_MOTION_SENSOR_Write_Register(IKS5A1_ISM6HG256X_0,
                                                ISM6HG256X_REG_FUNC_CFG_ACCESS,
                                                ISM6HG256X_FUNC_CFG_EMB_FUNC_BANK) == BSP_ERROR_NONE) {
            uint8_t mlc_src = 0u;
            if (IKS5A1_MOTION_SENSOR_Read_Register(IKS5A1_ISM6HG256X_0,
                                                   ISM6HG256X_EMB_REG_MLC1_SRC,
                                                   &mlc_src) == BSP_ERROR_NONE) {
                out->mlc1_raw      = mlc_src;
                out->mlc1_model_id = SENSORS_IKS4A1_MLC1_MODEL_ASSET_TRACKING;
            }
            (void)IKS5A1_MOTION_SENSOR_Write_Register(IKS5A1_ISM6HG256X_0,
                                                      ISM6HG256X_REG_FUNC_CFG_ACCESS,
                                                      ISM6HG256X_FUNC_CFG_MAIN_BANK);
        }
    }

    return 0;
}

static int16_t s_clamp_i16(int32_t v)
{
    if (v >  32767)  return  32767;
    if (v < -32768)  return -32768;
    return (int16_t)v;
}
static uint16_t s_clamp_u16(int32_t v)
{
    if (v < 0)        return 0;
    if (v > 0xFFFF)   return 0xFFFF;
    return (uint16_t)v;
}

/* ============================================================================
 * Pack helpers and packers — copied verbatim from sensors_iks4a1.c so the
 * wire format is byte-for-byte identical across the two boards. The shared
 * sensors_iks4a1.h struct lets the decoder + template stay common.
 * ========================================================================== */

static inline uint32_t s_tlv_hdr(uint8_t *buf, uint32_t o, uint8_t tag, uint8_t len)
{
    buf[o++] = (uint8_t)((0u << 6) | (tag & 0x3Fu));
    buf[o++] = len;
    return o;
}
static uint32_t s_tlv_u8(uint8_t *buf, uint32_t o, uint8_t tag, uint8_t v)
{
    o = s_tlv_hdr(buf, o, tag, 1u);
    buf[o++] = v;
    return o;
}
static uint32_t s_tlv_i16le(uint8_t *buf, uint32_t o, uint8_t tag, int16_t v)
{
    o = s_tlv_hdr(buf, o, tag, 2u);
    buf[o++] = (uint8_t)(v & 0xFF);
    buf[o++] = (uint8_t)((v >> 8) & 0xFF);
    return o;
}
static uint32_t s_tlv_u16le(uint8_t *buf, uint32_t o, uint8_t tag, uint16_t v)
{
    o = s_tlv_hdr(buf, o, tag, 2u);
    buf[o++] = (uint8_t)(v & 0xFF);
    buf[o++] = (uint8_t)((v >> 8) & 0xFF);
    return o;
}
static uint32_t s_tlv_u32le(uint8_t *buf, uint32_t o, uint8_t tag, uint32_t v)
{
    o = s_tlv_hdr(buf, o, tag, 4u);
    buf[o++] = (uint8_t)(v & 0xFF);
    buf[o++] = (uint8_t)((v >> 8) & 0xFF);
    buf[o++] = (uint8_t)((v >> 16) & 0xFF);
    buf[o++] = (uint8_t)((v >> 24) & 0xFF);
    return o;
}
static uint32_t s_tlv_i16x3le(uint8_t *buf, uint32_t o, uint8_t tag, const int16_t v[3])
{
    o = s_tlv_hdr(buf, o, tag, 6u);
    for (int i = 0; i < 3; i++) {
        buf[o++] = (uint8_t)(v[i] & 0xFF);
        buf[o++] = (uint8_t)((v[i] >> 8) & 0xFF);
    }
    return o;
}

uint32_t sensors_iks4a1_pack(uint8_t *buf,
                              uint32_t buf_len,
                              uint8_t  seq,
                              uint32_t gps_time_s,
                              const sensors_iks4a1_reading_t *r)
{
    if (buf == NULL || r == NULL || buf_len < SENSORS_IKS4A1_PAYLOAD_MAX_SIZE) {
        return 0;
    }

    uint32_t o = 0;

    /* WORKAROUND: emit CAP msg_desc (0x40) — see sensors_iks4a1.c. */
    buf[o++] = SENSORS_IKS4A1_MSG_DESC_NOTIFY_CAP;

    /* sid_demo standard tags. */
    int16_t whole_c = (int16_t)(r->stts22h_c_x100 / 100);
    o = s_tlv_i16le (buf, o, TAG_TEMPERATURE_SENSOR_DATA_NOTIFY, whole_c);
    o = s_tlv_u32le (buf, o, TAG_CURRENT_GPS_TIME_IN_SECONDS,    gps_time_s);
    o = s_tlv_u8    (buf, o, TAG_LINK_TYPE,                      0x01u);

    /* IKS4A1 / shared high-resolution tags. SHT40 temp + humidity NOT emitted
     * (those sensors don't exist on IKS5A1; the decoder leaves the fields
     * absent / null in /IOTCONNECT). */
    o = s_tlv_u8    (buf, o, TAG_IKS4A1_VERSION,            SENSORS_IKS4A1_PROTO_VERSION);
    o = s_tlv_u8    (buf, o, TAG_IKS4A1_SEQUENCE,           seq);
    o = s_tlv_i16x3le(buf, o, TAG_IKS4A1_ACCEL,             r->acc_mg);
    o = s_tlv_i16x3le(buf, o, TAG_IKS4A1_GYRO,              r->gyr_dps_x10);
    o = s_tlv_i16le (buf, o, TAG_IKS4A1_TEMP_STTS22H_X100,  r->stts22h_c_x100);
    o = s_tlv_u32le (buf, o, TAG_IKS4A1_PRESSURE_X100,      r->lps22df_pa_x100);
    o = s_tlv_u8    (buf, o, TAG_IKS4A1_ORIENTATION,        r->orientation);
    o = s_tlv_i16le (buf, o, TAG_IKS4A1_QVAR_RAW,           r->qvar_raw);
    /* ISM6HG256X MLC1_SRC label + model id (asset_tracking = 1) — same classes
     * and decoder label map as the IKS4A1/LSM6DSV16X build. If the UCF load
     * failed both fields are 0 and the decoder shows mlc1_model_name="none". */
    o = s_tlv_u8    (buf, o, TAG_IKS4A1_MLC1,               r->mlc1_raw);
    o = s_tlv_u8    (buf, o, TAG_IKS4A1_MLC1_MODEL,         r->mlc1_model_id);

    return o;
}

uint32_t sensors_iks4a1_pack_capability(uint8_t *buf, uint32_t buf_len)
{
    /* Capability frame is sensor-board-agnostic. Identical to IKS4A1 path. */
    if (buf == NULL || buf_len < 16u) {
        return 0;
    }
    uint32_t o = 0;
    buf[o++] = SENSORS_IKS4A1_MSG_DESC_NOTIFY_CAP;
    o = s_tlv_hdr(buf, o, TAG_NUMBER_OF_BUTTONS, 0u);
    o = s_tlv_hdr(buf, o, TAG_NUMBER_OF_LEDS,    0u);
    o = s_tlv_u8 (buf, o, TAG_TEMP_SENSOR_AVAILABLE_UNIT, 0x01u);
    o = s_tlv_u8 (buf, o, TAG_LINK_TYPE,                  0x01u);
    o = s_tlv_u8 (buf, o, TAG_OTA_SUPPORTED,              0x00u);
    return o;
}

#endif /* SID_APP_IKS5A1_ENABLED */
