/**
  ******************************************************************************
  * @file    iks5a1_conf.h
  * @author  MEMS Software Solutions Team
  * @brief   This file contains definitions for the MEMS components bus interfaces
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2023 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  *
  * Modifications by Avnet /IOTCONNECT for the iotc-stm32-sidewalk demo
  * (file originally derived from iks5a1_conf_template.h in X-CUBE-MEMS1):
  *   - Mirrors iks4a1_conf.h structure for the Nucleo-WBA55CG / Nucleo-WBA65RI.
  *   - Sensors enabled:  ISM6HG256X, IIS2DULPX, ILPS22QS.
  *   - Sensors disabled: ISM330IS (ISPU IMU — add when ISPU is wired up);
  *                       IIS2MDC (magnetometer — no template field yet).
  *
  * Upstream license terms (BSD-3-Clause) are preserved; refer to the SDK LICENSE
  * file for the full text.
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

/* BSP I2C glue (same I2C1 the IKS4A1 uses on the WBA55 / WBA65 Arduino header). */
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
