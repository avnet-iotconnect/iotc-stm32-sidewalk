/**
  ******************************************************************************
  * @file    stm32wbaxx_nucleo_bus.h
  * @brief   BSP bus glue for the IKS4A1 sensor expansion shield on Nucleo-WBA55CG.
  *
  *   Pinout (UM3301 + Nucleo-WBA55CG schematic):
  *     D14 ARDUINO = PB1 = I2C1_SDA (AF4)
  *     D15 ARDUINO = PB2 = I2C1_SCL (AF4)
  *
  *   Clock: I2C1 is sourced from HSI16 (16 MHz) so TIMINGR stays stable
  *   regardless of system clock tweaks. Standard mode (100 kHz).
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
#define BUS_I2C1_SCL_GPIO_PORT          GPIOB
#define BUS_I2C1_SCL_GPIO_PIN           GPIO_PIN_2
#define BUS_I2C1_SCL_GPIO_AF            GPIO_AF4_I2C1
#define BUS_I2C1_SCL_GPIO_CLK_ENABLE()  __HAL_RCC_GPIOB_CLK_ENABLE()
#define BUS_I2C1_SDA_GPIO_PORT          GPIOB
#define BUS_I2C1_SDA_GPIO_PIN           GPIO_PIN_1
#define BUS_I2C1_SDA_GPIO_AF            GPIO_AF4_I2C1
#define BUS_I2C1_SDA_GPIO_CLK_ENABLE()  __HAL_RCC_GPIOB_CLK_ENABLE()

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
