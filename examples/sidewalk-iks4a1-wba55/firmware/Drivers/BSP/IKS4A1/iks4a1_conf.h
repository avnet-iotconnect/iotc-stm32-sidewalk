/**
  ******************************************************************************
  * @file    iks4a1_conf.h
  * @brief   IKS4A1 configuration for Nucleo-WBA55CG + Sidewalk demo.
  *          Generated from iks4a1_conf_template.h with:
  *            - WBA HAL header
  *            - WBA Nucleo BSP I2C bus glue (PB1=SDA / PB2=SCL via I2C1)
  *            - Only the four sensors we ship PID drivers for enabled
  ******************************************************************************
  */
#ifndef IKS4A1_CONF_H
#define IKS4A1_CONF_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/
#include "stm32wbaxx_hal.h"
#include "stm32wbaxx_nucleo_bus.h"
#include "stm32wbaxx_nucleo_errno.h"

/* Sensors enabled: only the four we ship PID drivers for. The others must
 * stay disabled, otherwise the BSP would reference symbols that the linker
 * cannot resolve (no PID source compiled for them). */
#define USE_IKS4A1_ENV_SENSOR_SHT40AD1B_0                      1U
#define USE_IKS4A1_ENV_SENSOR_LPS22DF_0                        1U
#define USE_IKS4A1_ENV_SENSOR_STTS22H_0                        1U

#define USE_IKS4A1_MOTION_SENSOR_LSM6DSV16X_0                  1U
#define USE_IKS4A1_MOTION_SENSOR_LIS2DUXS12_0                  0U
#define USE_IKS4A1_MOTION_SENSOR_LIS2MDL_0                     0U
#define USE_IKS4A1_MOTION_SENSOR_LSM6DSO16IS_0                 0U

/* BSP I2C glue */
#define IKS4A1_I2C_INIT       BSP_I2C1_Init
#define IKS4A1_I2C_DEINIT     BSP_I2C1_DeInit
#define IKS4A1_I2C_READ_REG   BSP_I2C1_ReadReg
#define IKS4A1_I2C_WRITE_REG  BSP_I2C1_WriteReg
#define IKS4A1_I2C_READ       BSP_I2C1_Recv
#define IKS4A1_I2C_WRITE      BSP_I2C1_Send
#define IKS4A1_GET_TICK       BSP_GetTick
#define IKS4A1_DELAY          HAL_Delay

#ifdef __cplusplus
}
#endif

#endif /* IKS4A1_CONF_H */
