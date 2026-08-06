/**
  ******************************************************************************
  * @file    iks4a1_conf.h
  * @author  MEMS Software Solutions Team
  * @brief   This file contains definitions for the MEMS components bus interfaces
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2022 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  *
  * Modifications by Avnet /IOTCONNECT for the iotc-stm32-sidewalk demo
  * (file originally derived from iks4a1_conf_template.h in X-CUBE-MEMS1):
  *   - Includes stm32wbaxx_hal.h and the WBA Nucleo BSP I2C bus glue header
  *     (I2C1; concrete SDA/SCL pins selected per board in that header — WBA55
  *     PB1/PB2, WBA65 see its VERIFY note) instead of the generic template.
  *   - Enables only the four sensors we ship PID drivers for.
  *
  * Upstream license terms (BSD-3-Clause) are preserved; refer to the SDK LICENSE
  * file for the full text.
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
#define USE_IKS4A1_MOTION_SENSOR_LIS2DUXS12_0                  1U   /* Qvar capacitive sensing */
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
