/**
  ******************************************************************************
  * @file    iks5a1_conf.h
  * @brief   IKS5A1 configuration for Nucleo-WBA55CG + Sidewalk demo.
  *          Mirrors iks4a1_conf.h. Sensors enabled:
  *            - ISM6HG256X  (motion: 6-axis IMU, high-g)
  *            - IIS2DULPX   (motion: accel + Qvar capacitive front-end)
  *            - ILPS22QS    (env:    pressure + on-die temperature)
  *          Disabled to keep flash small:
  *            - ISM330IS    (ISPU IMU - add when ISPU is wired up)
  *            - IIS2MDC     (magnetometer - no template field yet)
  ******************************************************************************
  */
#ifndef IKS5A1_CONF_H
#define IKS5A1_CONF_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/
#include "stm32wbaxx_hal.h"
#include "stm32wbaxx_nucleo_bus.h"
#include "stm32wbaxx_nucleo_errno.h"

/* Sensors enabled: only the three we ship code for here. */
#define USE_IKS5A1_ENV_SENSOR_ILPS22QS_0       1U
#define USE_IKS5A1_MOTION_SENSOR_ISM6HG256X_0  1U
#define USE_IKS5A1_MOTION_SENSOR_ISM330IS_0    0U
#define USE_IKS5A1_MOTION_SENSOR_IIS2DULPX_0   1U
#define USE_IKS5A1_MOTION_SENSOR_IIS2MDC_0     0U

/* BSP I2C glue (same I2C1 the IKS4A1 uses on the WBA55 Arduino header). */
#define IKS5A1_I2C_INIT       BSP_I2C1_Init
#define IKS5A1_I2C_DEINIT     BSP_I2C1_DeInit
#define IKS5A1_I2C_READ_REG   BSP_I2C1_ReadReg
#define IKS5A1_I2C_WRITE_REG  BSP_I2C1_WriteReg
#define IKS5A1_I2C_READ       BSP_I2C1_Recv
#define IKS5A1_I2C_WRITE      BSP_I2C1_Send
#define IKS5A1_GET_TICK       BSP_GetTick
#define IKS5A1_DELAY          HAL_Delay

#ifdef __cplusplus
}
#endif

#endif /* IKS5A1_CONF_H */
