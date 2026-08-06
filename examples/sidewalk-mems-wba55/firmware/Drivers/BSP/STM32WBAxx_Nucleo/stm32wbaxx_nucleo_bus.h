/**
  ******************************************************************************
  * @file    stm32wbaxx_nucleo_bus.h
  * @author  MCD Application Team
  * @brief   Header file for the BSP BUS IO driver
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
  * Modifications by Avnet /IOTCONNECT for the iotc-stm32-sidewalk demo:
  *   - BSP bus glue tailored for the IKS4A1 / IKS5A1 sensor expansion shields
  *     on Nucleo-WBA55CG and Nucleo-WBA65RI.
  *   - Pinout is selected below by the board macro the SDK project defines
  *     (NUCLEO_WBA55_BOARD or NUCLEO_WBA65_BOARD):
  *       NUCLEO-WBA55CG (UM3301 schematic):
  *         D14 ARDUINO = PB1 = I2C1_SDA (AF4)
  *         D15 ARDUINO = PB2 = I2C1_SCL (AF4)
  *       NUCLEO-WBA65RI:
  *         D14/D15 ARDUINO -> I2C1_SDA/I2C1_SCL — see the ">>> VERIFY" note on
  *         the WBA65 branch below. The values default to the WBA55 mapping and
  *         MUST be confirmed against the NUCLEO-WBA65RI schematic before use.
  *   - Clock: I2C1 is sourced from HSI16 (16 MHz) so TIMINGR stays stable
  *     regardless of system clock tweaks. Standard mode (100 kHz).
  *
  * Upstream license terms (BSD-3-Clause) are preserved; refer to the SDK LICENSE
  * file for the full text.
  ******************************************************************************
  */

#ifndef STM32WBAXX_NUCLEO_BUS_H
#define STM32WBAXX_NUCLEO_BUS_H

#ifdef __cplusplus
extern "C" {
#endif

#include "stm32wbaxx_hal.h"
#include "stm32wbaxx_nucleo_errno.h"

#define BUS_I2C1_INSTANCE               I2C1

#if defined(NUCLEO_WBA65_BOARD)
/*
 * >>> VERIFY: NUCLEO-WBA65RI Arduino-I2C pin mapping.
 * These values are defaulted to the known-good NUCLEO-WBA55CG mapping so the
 * project builds, but they have NOT been confirmed against the NUCLEO-WBA65RI
 * schematic. Before trusting sensor data on WBA65, check the Arduino D14 (SDA)
 * / D15 (SCL) net names on the NUCLEO-WBA65RI board schematic and correct the
 * PORT / PIN / AF / I2C-instance below if they differ. The WBA6x package is
 * larger than the WBA5x, so the GPIO behind the Arduino header can change.
 */
#define BUS_I2C1_SCL_GPIO_PORT          GPIOB
#define BUS_I2C1_SCL_GPIO_PIN           GPIO_PIN_2
#define BUS_I2C1_SCL_GPIO_AF            GPIO_AF4_I2C1
#define BUS_I2C1_SCL_GPIO_CLK_ENABLE()  __HAL_RCC_GPIOB_CLK_ENABLE()
#define BUS_I2C1_SDA_GPIO_PORT          GPIOB
#define BUS_I2C1_SDA_GPIO_PIN           GPIO_PIN_1
#define BUS_I2C1_SDA_GPIO_AF            GPIO_AF4_I2C1
#define BUS_I2C1_SDA_GPIO_CLK_ENABLE()  __HAL_RCC_GPIOB_CLK_ENABLE()
#else /* NUCLEO_WBA55_BOARD (default) */
#define BUS_I2C1_SCL_GPIO_PORT          GPIOB
#define BUS_I2C1_SCL_GPIO_PIN           GPIO_PIN_2
#define BUS_I2C1_SCL_GPIO_AF            GPIO_AF4_I2C1
#define BUS_I2C1_SCL_GPIO_CLK_ENABLE()  __HAL_RCC_GPIOB_CLK_ENABLE()
#define BUS_I2C1_SDA_GPIO_PORT          GPIOB
#define BUS_I2C1_SDA_GPIO_PIN           GPIO_PIN_1
#define BUS_I2C1_SDA_GPIO_AF            GPIO_AF4_I2C1
#define BUS_I2C1_SDA_GPIO_CLK_ENABLE()  __HAL_RCC_GPIOB_CLK_ENABLE()
#endif

#ifndef BUS_I2C1_POLL_TIMEOUT
#  define BUS_I2C1_POLL_TIMEOUT         0x1000U
#endif

/* TIMINGR for HSI16 (16 MHz) Standard-mode 100 kHz - per AN4235 / CubeMX. */
#ifndef BUS_I2C1_TIMING
#  define BUS_I2C1_TIMING               0x00303D5BU
#endif

extern I2C_HandleTypeDef hi2c1;

HAL_StatusTypeDef MX_I2C1_Init(I2C_HandleTypeDef *hi2c);

int32_t BSP_I2C1_Init(void);
int32_t BSP_I2C1_DeInit(void);
int32_t BSP_I2C1_IsReady(uint16_t DevAddr, uint32_t Trials);
int32_t BSP_I2C1_WriteReg (uint16_t Addr, uint16_t Reg, uint8_t *pData, uint16_t Length);
int32_t BSP_I2C1_ReadReg  (uint16_t Addr, uint16_t Reg, uint8_t *pData, uint16_t Length);
int32_t BSP_I2C1_WriteReg16(uint16_t Addr, uint16_t Reg, uint8_t *pData, uint16_t Length);
int32_t BSP_I2C1_ReadReg16 (uint16_t Addr, uint16_t Reg, uint8_t *pData, uint16_t Length);
int32_t BSP_I2C1_Send (uint16_t DevAddr, uint8_t *pData, uint16_t Length);
int32_t BSP_I2C1_Recv (uint16_t DevAddr, uint8_t *pData, uint16_t Length);
int32_t BSP_I2C1_SendRecv(uint16_t DevAddr, uint8_t *pTxdata, uint8_t *pRxdata, uint16_t Length);

int32_t BSP_GetTick(void);

#ifdef __cplusplus
}
#endif

#endif /* STM32WBAXX_NUCLEO_BUS_H */
