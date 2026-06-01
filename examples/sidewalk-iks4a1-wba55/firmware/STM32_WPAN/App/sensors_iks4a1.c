/**
  ******************************************************************************
  * @file    sensors_iks4a1.c
  * @brief   IKS4A1 sensor abstraction for the Sidewalk-over-BLE example.
  *
  * Depends on the X-CUBE-MEMS1 IKS4A1 BSP. The user must:
  *   1. Add X-CUBE-MEMS1 (>= v11.x) drivers to the project so the headers
  *        - iks4a1_motion_sensors.h
  *        - iks4a1_env_sensors.h
  *      and their PID drivers (LSM6DSV16X, LPS22DF, SHT40AD1B, STTS22H) are
  *      on the include / source path.
  *   2. Implement the BSP I2C glue (iks4a1_bus.c usually shipped with the
  *      X-CUBE-MEMS1 BSP) for the Nucleo-WBA55 Arduino-connector I2C bus.
  *   3. Enable HAL_I2C_MODULE_ENABLED in stm32wbaxx_hal_conf.h.
  *
  * The Sidewalk app pulls this module in only when SID_APP_IKS4A1_ENABLED is
  * defined at compile time (see iotc-stm32-sidewalk example README).
  ******************************************************************************
  */

#include "sensors_iks4a1.h"

#include <string.h>

#include <sid_pal_log_ifc.h>

#if defined(SID_APP_IKS4A1_ENABLED) && (SID_APP_IKS4A1_ENABLED == 1)

#include "iks4a1_motion_sensors.h"
#include "iks4a1_motion_sensors_ex.h"   /* 6D, Read/Write_Register */
#include "iks4a1_env_sensors.h"
#include "stm32wbaxx_nucleo_bus.h"

/* LIS2DUXS12 Qvar registers (datasheet section 9.x). Configured directly via
 * IKS4A1_MOTION_SENSOR_Write_Register since the BSP wrapper has no Qvar API. */
#define LIS2DUXS12_REG_OUT_T_AH_QVAR_L   (0x2Eu)
#define LIS2DUXS12_REG_OUT_T_AH_QVAR_H   (0x2Fu)
#define LIS2DUXS12_REG_AH_QVAR_CFG       (0x31u)
/* AH_QVAR_CFG bit field (little-endian declaration in lis2duxs12_reg.h):
 *   bits 1:0 gain        (00=X1 after default multiplier)
 *   bits 3:2 c_zin       (00=520 MOhm input impedance — best for finger Qvar)
 *   bit  4   notch_cutoff
 *   bit  5   notch_en
 *   bit  6   ah_qvar_en  <- enables the Qvar front-end
 *   bit  7   reserved
 * 0x40 = enable Qvar only, defaults for the rest. */
#define LIS2DUXS12_AH_QVAR_CFG_ENABLE    (0x40u)

/* X-CUBE-MEMS1 IKS4A1 BSP instance ids. These names match the BSP headers
 * shipped with X-CUBE-MEMS1 v11+. If your BSP version uses different macros,
 * remap them here. */
#ifndef SID_IKS4A1_LSM6DSV16X_INSTANCE
#  define SID_IKS4A1_LSM6DSV16X_INSTANCE   IKS4A1_LSM6DSV16X_0
#endif
#ifndef SID_IKS4A1_LPS22DF_INSTANCE
#  define SID_IKS4A1_LPS22DF_INSTANCE      IKS4A1_LPS22DF_0
#endif
#ifndef SID_IKS4A1_SHT40_INSTANCE
#  define SID_IKS4A1_SHT40_INSTANCE        IKS4A1_SHT40AD1B_0
#endif
#ifndef SID_IKS4A1_STTS22H_INSTANCE
#  define SID_IKS4A1_STTS22H_INSTANCE      IKS4A1_STTS22H_0
#endif

static int16_t  s_clamp_i16(int32_t v);
static uint16_t s_clamp_u16(int32_t v);

int sensors_iks4a1_init(void)
{
    int32_t rc;

    /* Bring up I2C1 once for the whole expansion shield. The IKS4A1 BSP will
     * also call IKS4A1_I2C_INIT during per-sensor init; the BSP_I2C1_Init
     * implementation is refcounted, so the double-init is harmless. */
    if (BSP_I2C1_Init() != BSP_ERROR_NONE) {
        SID_PAL_LOG_ERROR("IKS4A1: I2C1 bus init failed");
        return -10;
    }

    rc = IKS4A1_MOTION_SENSOR_Init(SID_IKS4A1_LSM6DSV16X_INSTANCE,
                                    MOTION_ACCELERO | MOTION_GYRO);
    if (rc != BSP_ERROR_NONE) {
        SID_PAL_LOG_ERROR("IKS4A1: LSM6DSV16X init failed (%ld)", (long)rc);
        return -1;
    }
    (void)IKS4A1_MOTION_SENSOR_Enable(SID_IKS4A1_LSM6DSV16X_INSTANCE, MOTION_ACCELERO);
    (void)IKS4A1_MOTION_SENSOR_Enable(SID_IKS4A1_LSM6DSV16X_INSTANCE, MOTION_GYRO);

    rc = IKS4A1_ENV_SENSOR_Init(SID_IKS4A1_LPS22DF_INSTANCE, ENV_PRESSURE);
    if (rc != BSP_ERROR_NONE) {
        SID_PAL_LOG_ERROR("IKS4A1: LPS22DF init failed (%ld)", (long)rc);
        return -2;
    }
    (void)IKS4A1_ENV_SENSOR_Enable(SID_IKS4A1_LPS22DF_INSTANCE, ENV_PRESSURE);

    rc = IKS4A1_ENV_SENSOR_Init(SID_IKS4A1_SHT40_INSTANCE, ENV_HUMIDITY | ENV_TEMPERATURE);
    if (rc != BSP_ERROR_NONE) {
        SID_PAL_LOG_ERROR("IKS4A1: SHT40AD1B init failed (%ld)", (long)rc);
        return -3;
    }
    (void)IKS4A1_ENV_SENSOR_Enable(SID_IKS4A1_SHT40_INSTANCE, ENV_HUMIDITY);
    (void)IKS4A1_ENV_SENSOR_Enable(SID_IKS4A1_SHT40_INSTANCE, ENV_TEMPERATURE);

    rc = IKS4A1_ENV_SENSOR_Init(SID_IKS4A1_STTS22H_INSTANCE, ENV_TEMPERATURE);
    if (rc != BSP_ERROR_NONE) {
        SID_PAL_LOG_ERROR("IKS4A1: STTS22H init failed (%ld)", (long)rc);
        return -4;
    }
    (void)IKS4A1_ENV_SENSOR_Enable(SID_IKS4A1_STTS22H_INSTANCE, ENV_TEMPERATURE);

#if (USE_IKS4A1_MOTION_SENSOR_LIS2DUXS12_0 == 1)
    /* LIS2DUXS12 — accelerometer + Qvar capacitive front-end. We don't read
     * its accel (the LSM6DSV16X is already the primary IMU); we use it solely
     * for the AH/Qvar channel wired to the IKS4A1's edge pads. */
    rc = IKS4A1_MOTION_SENSOR_Init(IKS4A1_LIS2DUXS12_0, MOTION_ACCELERO);
    if (rc != BSP_ERROR_NONE) {
        SID_PAL_LOG_WARNING("IKS4A1: LIS2DUXS12 init failed (%ld) - qvar disabled", (long)rc);
    } else {
        (void)IKS4A1_MOTION_SENSOR_Enable(IKS4A1_LIS2DUXS12_0, MOTION_ACCELERO);
        if (IKS4A1_MOTION_SENSOR_Write_Register(IKS4A1_LIS2DUXS12_0,
                                                LIS2DUXS12_REG_AH_QVAR_CFG,
                                                LIS2DUXS12_AH_QVAR_CFG_ENABLE) == BSP_ERROR_NONE) {
            SID_PAL_LOG_INFO("IKS4A1: LIS2DUXS12 Qvar enabled");
        } else {
            SID_PAL_LOG_WARNING("IKS4A1: LIS2DUXS12 Qvar enable write failed");
        }
    }
#endif

    /* LSM6DSV16X native 6D orientation detection. The Enable function requires
     * an interrupt-pin argument; we pass INT1 to satisfy the API but never
     * wire the pin — orientation is polled via the D6D_SRC status bits each
     * sensors_iks4a1_read() cycle. Threshold 2 ≈ 60° tilt before a face flip. */
    (void)IKS4A1_MOTION_SENSOR_Set_6D_Orientation_Threshold(SID_IKS4A1_LSM6DSV16X_INSTANCE, 2u);
    rc = IKS4A1_MOTION_SENSOR_Enable_6D_Orientation(SID_IKS4A1_LSM6DSV16X_INSTANCE,
                                                    IKS4A1_MOTION_SENSOR_INT1_PIN);
    if (rc != BSP_ERROR_NONE) {
        SID_PAL_LOG_WARNING("IKS4A1: LSM6DSV16X 6D enable failed (%ld)", (long)rc);
    } else {
        SID_PAL_LOG_INFO("IKS4A1: LSM6DSV16X 6D orientation enabled");
    }

    SID_PAL_LOG_INFO("IKS4A1: sensors initialized");
    return 0;
}

int sensors_iks4a1_read(sensors_iks4a1_reading_t *out)
{
    if (out == NULL) {
        return -1;
    }
    memset(out, 0, sizeof(*out));

    IKS4A1_MOTION_SENSOR_Axes_t axes;
    int32_t rc;
    float   v;

    rc = IKS4A1_MOTION_SENSOR_GetAxes(SID_IKS4A1_LSM6DSV16X_INSTANCE, MOTION_ACCELERO, &axes);
    if (rc == BSP_ERROR_NONE) {
        /* BSP returns accel in mg already */
        out->acc_mg[0] = s_clamp_i16(axes.x);
        out->acc_mg[1] = s_clamp_i16(axes.y);
        out->acc_mg[2] = s_clamp_i16(axes.z);
    } else {
        SID_PAL_LOG_WARNING("IKS4A1: accel read failed (%ld)", (long)rc);
    }

    rc = IKS4A1_MOTION_SENSOR_GetAxes(SID_IKS4A1_LSM6DSV16X_INSTANCE, MOTION_GYRO, &axes);
    if (rc == BSP_ERROR_NONE) {
        /* BSP returns gyro in mdps. Scale to dps*10 to fit int16 over the full +-2000 dps range. */
        out->gyr_dps_x10[0] = s_clamp_i16(axes.x / 100);
        out->gyr_dps_x10[1] = s_clamp_i16(axes.y / 100);
        out->gyr_dps_x10[2] = s_clamp_i16(axes.z / 100);
    } else {
        SID_PAL_LOG_WARNING("IKS4A1: gyro read failed (%ld)", (long)rc);
    }

    rc = IKS4A1_ENV_SENSOR_GetValue(SID_IKS4A1_STTS22H_INSTANCE, ENV_TEMPERATURE, &v);
    if (rc == BSP_ERROR_NONE) {
        out->stts22h_c_x100 = s_clamp_i16((int32_t)(v * 100.0f));
    } else {
        SID_PAL_LOG_WARNING("IKS4A1: STTS22H temp read failed (%ld)", (long)rc);
    }

    rc = IKS4A1_ENV_SENSOR_GetValue(SID_IKS4A1_SHT40_INSTANCE, ENV_TEMPERATURE, &v);
    if (rc == BSP_ERROR_NONE) {
        out->sht40_temp_c_x100 = s_clamp_i16((int32_t)(v * 100.0f));
    } else {
        SID_PAL_LOG_WARNING("IKS4A1: SHT40 temp read failed (%ld)", (long)rc);
    }

    rc = IKS4A1_ENV_SENSOR_GetValue(SID_IKS4A1_SHT40_INSTANCE, ENV_HUMIDITY, &v);
    if (rc == BSP_ERROR_NONE) {
        out->sht40_rh_x100 = s_clamp_u16((int32_t)(v * 100.0f));
    } else {
        SID_PAL_LOG_WARNING("IKS4A1: SHT40 humidity read failed (%ld)", (long)rc);
    }

    rc = IKS4A1_ENV_SENSOR_GetValue(SID_IKS4A1_LPS22DF_INSTANCE, ENV_PRESSURE, &v);
    if (rc == BSP_ERROR_NONE) {
        /* BSP returns pressure in hPa as float; transmit as hPa*100 (centi-hPa)
         * which fits 4 bytes for any plausible atmospheric pressure. */
        int32_t scaled = (int32_t)(v * 100.0f);
        if (scaled < 0) {
            scaled = 0;
        }
        out->lps22df_pa_x100 = (uint32_t)scaled;
    } else {
        SID_PAL_LOG_WARNING("IKS4A1: LPS22DF pressure read failed (%ld)", (long)rc);
    }

    /* 6D orientation — which face is currently up. D6D_SRC has six axis bits;
     * exactly one is set when the device is within the 6D threshold of an
     * axis-aligned orientation. UNKNOWN otherwise (mid-tilt). */
    out->orientation = (uint8_t)SENSORS_IKS4A1_ORIENT_UNKNOWN;
    {
        uint8_t xl = 0, xh = 0, yl = 0, yh = 0, zl = 0, zh = 0;
        if (IKS4A1_MOTION_SENSOR_Get_6D_Orientation_XL(SID_IKS4A1_LSM6DSV16X_INSTANCE, &xl) == BSP_ERROR_NONE
         && IKS4A1_MOTION_SENSOR_Get_6D_Orientation_XH(SID_IKS4A1_LSM6DSV16X_INSTANCE, &xh) == BSP_ERROR_NONE
         && IKS4A1_MOTION_SENSOR_Get_6D_Orientation_YL(SID_IKS4A1_LSM6DSV16X_INSTANCE, &yl) == BSP_ERROR_NONE
         && IKS4A1_MOTION_SENSOR_Get_6D_Orientation_YH(SID_IKS4A1_LSM6DSV16X_INSTANCE, &yh) == BSP_ERROR_NONE
         && IKS4A1_MOTION_SENSOR_Get_6D_Orientation_ZL(SID_IKS4A1_LSM6DSV16X_INSTANCE, &zl) == BSP_ERROR_NONE
         && IKS4A1_MOTION_SENSOR_Get_6D_Orientation_ZH(SID_IKS4A1_LSM6DSV16X_INSTANCE, &zh) == BSP_ERROR_NONE) {
            if      (zh) out->orientation = (uint8_t)SENSORS_IKS4A1_ORIENT_Z_POS_UP;
            else if (zl) out->orientation = (uint8_t)SENSORS_IKS4A1_ORIENT_Z_NEG_UP;
            else if (yh) out->orientation = (uint8_t)SENSORS_IKS4A1_ORIENT_Y_POS_UP;
            else if (yl) out->orientation = (uint8_t)SENSORS_IKS4A1_ORIENT_Y_NEG_UP;
            else if (xh) out->orientation = (uint8_t)SENSORS_IKS4A1_ORIENT_X_POS_UP;
            else if (xl) out->orientation = (uint8_t)SENSORS_IKS4A1_ORIENT_X_NEG_UP;
        }
    }

#if (USE_IKS4A1_MOTION_SENSOR_LIS2DUXS12_0 == 1)
    /* LIS2DUXS12 Qvar — combine LSB+MSB at OUT_T_AH_QVAR. The reading swings
     * sharply (signed) when a finger touches the IKS4A1 edge pads. */
    {
        uint8_t lo = 0, hi = 0;
        if (IKS4A1_MOTION_SENSOR_Read_Register(IKS4A1_LIS2DUXS12_0,
                                               LIS2DUXS12_REG_OUT_T_AH_QVAR_L, &lo) == BSP_ERROR_NONE
         && IKS4A1_MOTION_SENSOR_Read_Register(IKS4A1_LIS2DUXS12_0,
                                               LIS2DUXS12_REG_OUT_T_AH_QVAR_H, &hi) == BSP_ERROR_NONE) {
            out->qvar_raw = (int16_t)(((uint16_t)hi << 8) | lo);
        }
    }
#endif

    return 0;
}

#else /* SID_APP_IKS4A1_ENABLED disabled — provide stubs to keep linker happy
       * if the symbols are referenced through an unused #if branch.        */

int sensors_iks4a1_init(void)                            { return -1; }
int sensors_iks4a1_read(sensors_iks4a1_reading_t *out)
{
    if (out != NULL) memset(out, 0, sizeof(*out));
    return -1;
}

#endif /* SID_APP_IKS4A1_ENABLED */

/* TLV writer helpers. Header byte = (size_type << 6) | (tag & 0x3F). All our
 * values are <= 6 bytes, so size_type is always 0 (1-byte length field). */

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
    buf[o++] = (uint8_t)((v >>  8) & 0xFF);
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

    /* WORKAROUND: emit the CAP msg_desc (0x40) instead of the semantically-
     * correct ACTION msg_desc (0x41). The currently-deployed /IOTCONNECT
     * decoder has a bug in _maybe_unwrap_hex_string that only unwraps
     * hex-ASCII payloads starting with "40", so action frames are silently
     * dropped. Sending 0x40 lets the deployed decoder unwrap and parse the
     * sensor TLVs (records appear with id="2-0-0" but populated sensor
     * fields). Revert to SENSORS_IKS4A1_MSG_DESC_NOTIFY_ACTION once the
     * fixed decoder (commit b0307c6 on iotc-stm32-sidewalk main) is live. */
    buf[o++] = SENSORS_IKS4A1_MSG_DESC_NOTIFY_CAP;

    /* sid_demo standard tags expected by the /IOTCONNECT sid_demo decoder. */
    int16_t stts22h_whole_c = (int16_t)(r->stts22h_c_x100 / 100);
    o = s_tlv_i16le (buf, o, TAG_TEMPERATURE_SENSOR_DATA_NOTIFY, stts22h_whole_c);
    o = s_tlv_u32le (buf, o, TAG_CURRENT_GPS_TIME_IN_SECONDS,    gps_time_s);
    o = s_tlv_u8    (buf, o, TAG_LINK_TYPE,                      0x01u);   /* 1 = BLE */

    /* IKS4A1 high-resolution / multi-sensor tags. Unknown to the standard
     * sid_demo decoder (silently skipped); read by sidewalk-iks4a1-tlv.py. */
    o = s_tlv_u8    (buf, o, TAG_IKS4A1_VERSION,            SENSORS_IKS4A1_PROTO_VERSION);
    o = s_tlv_u8    (buf, o, TAG_IKS4A1_SEQUENCE,           seq);
    o = s_tlv_i16x3le(buf, o, TAG_IKS4A1_ACCEL,              r->acc_mg);
    o = s_tlv_i16x3le(buf, o, TAG_IKS4A1_GYRO,               r->gyr_dps_x10);
    o = s_tlv_i16le (buf, o, TAG_IKS4A1_TEMP_STTS22H_X100,  r->stts22h_c_x100);
    o = s_tlv_i16le (buf, o, TAG_IKS4A1_TEMP_SHT40_X100,    r->sht40_temp_c_x100);
    o = s_tlv_u16le (buf, o, TAG_IKS4A1_HUMIDITY_X100,      r->sht40_rh_x100);
    o = s_tlv_u32le (buf, o, TAG_IKS4A1_PRESSURE_X100,      r->lps22df_pa_x100);
    o = s_tlv_u8    (buf, o, TAG_IKS4A1_ORIENTATION,        r->orientation);
    o = s_tlv_i16le (buf, o, TAG_IKS4A1_QVAR_RAW,           r->qvar_raw);

    return o;
}

uint32_t sensors_iks4a1_pack_capability(uint8_t *buf, uint32_t buf_len)
{
    /* Worst case: msg_desc + 5 tags * (1+1+1) = 16 bytes */
    if (buf == NULL || buf_len < 16u) {
        return 0;
    }

    uint32_t o = 0;

    /* msg_desc: opc=NOTIFY (2), cmd_class=DEMO_APP (0), cmd_id=CAP_DISCOVERY (0). */
    buf[o++] = SENSORS_IKS4A1_MSG_DESC_NOTIFY_CAP;

    /* Minimal capability advertisement so the destination Lambda accepts us
     * as a registered sid_demo device. Values mirror the device's actual
     * capabilities: 3 buttons (B1/B2/B3), 1 user LED (LED_BLUE), one
     * temperature sensor (Celsius), BLE link, no OTA. */
    /* Tag NUMBER_OF_BUTTONS - length 0 declares "no actionable buttons"
     * to keep the cap message minimal. Bump to 3 with the IDs 1/2/3 if
     * you want the dashboard to acknowledge B1/B2/B3 individually. */
    o = s_tlv_hdr(buf, o, TAG_NUMBER_OF_BUTTONS, 0u);
    o = s_tlv_hdr(buf, o, TAG_NUMBER_OF_LEDS,    0u);
    o = s_tlv_u8 (buf, o, TAG_TEMP_SENSOR_AVAILABLE_UNIT, 0x01u); /* 1 = Celsius */
    o = s_tlv_u8 (buf, o, TAG_LINK_TYPE,                  0x01u); /* 1 = BLE     */
    o = s_tlv_u8 (buf, o, TAG_OTA_SUPPORTED,              0x00u);

    return o;
}

#if defined(SID_APP_IKS4A1_ENABLED) && (SID_APP_IKS4A1_ENABLED == 1)
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
#endif
