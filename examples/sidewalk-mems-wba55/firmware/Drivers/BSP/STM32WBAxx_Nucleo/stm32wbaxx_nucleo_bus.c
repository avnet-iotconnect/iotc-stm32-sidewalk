/**
  ******************************************************************************
  * @file    stm32wbaxx_nucleo_bus.c
  * @author  MCD Application Team
  * @brief   Source file for the BSP BUS IO driver
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
  *   - I2C1 bus implementation tailored for Nucleo-WBA55CG (Arduino D14/D15
  *     pins, PB1=SDA / PB2=SCL), used by the IKS4A1 / IKS5A1 sensor expansion
  *     shields through the X-CUBE-MEMS1 BSP and PID component drivers.
  *   - Refcounted Init/DeInit so multiple sensor modules sharing the bus do
  *     not double-init / prematurely tear down the peripheral.
  *
  * Upstream license terms (BSD-3-Clause) are preserved; refer to the SDK LICENSE
  * file for the full text.
  ******************************************************************************
  */

#include "stm32wbaxx_nucleo_bus.h"

I2C_HandleTypeDef hi2c1;

static uint32_t s_i2c1_init_refcount = 0;

/* ----------------------------------------------------------------------------
 * MX_I2C1_Init: peripheral-init equivalent of STM32CubeMX-generated code.
 * I2C1 clock is sourced from HSI16 so the TIMINGR value is stable regardless
 * of any downstream system-clock retuning.
 * --------------------------------------------------------------------------*/
HAL_StatusTypeDef MX_I2C1_Init(I2C_HandleTypeDef *hi2c)
{
    RCC_PeriphCLKInitTypeDef pclk = {0};

    /* Ensure HSI16 is on (it's safe to enable redundantly). */
    if (__HAL_RCC_GET_FLAG(RCC_FLAG_HSIRDY) == RESET) {
        __HAL_RCC_HSI_ENABLE();
        uint32_t t0 = HAL_GetTick();
        while (__HAL_RCC_GET_FLAG(RCC_FLAG_HSIRDY) == RESET) {
            if ((HAL_GetTick() - t0) > 10u) {
                return HAL_TIMEOUT;
            }
        }
    }

    pclk.PeriphClockSelection = RCC_PERIPHCLK_I2C1;
    pclk.I2c1ClockSelection   = RCC_I2C1CLKSOURCE_HSI;
    if (HAL_RCCEx_PeriphCLKConfig(&pclk) != HAL_OK) {
        return HAL_ERROR;
    }

    hi2c->Instance              = BUS_I2C1_INSTANCE;
    hi2c->Init.Timing           = BUS_I2C1_TIMING;
    hi2c->Init.OwnAddress1      = 0;
    hi2c->Init.AddressingMode   = I2C_ADDRESSINGMODE_7BIT;
    hi2c->Init.DualAddressMode  = I2C_DUALADDRESS_DISABLE;
    hi2c->Init.OwnAddress2      = 0;
    hi2c->Init.OwnAddress2Masks = I2C_OA2_NOMASK;
    hi2c->Init.GeneralCallMode  = I2C_GENERALCALL_DISABLE;
    hi2c->Init.NoStretchMode    = I2C_NOSTRETCH_DISABLE;

    if (HAL_I2C_Init(hi2c) != HAL_OK) {
        return HAL_ERROR;
    }
    if (HAL_I2CEx_ConfigAnalogFilter(hi2c, I2C_ANALOGFILTER_ENABLE) != HAL_OK) {
        return HAL_ERROR;
    }
    if (HAL_I2CEx_ConfigDigitalFilter(hi2c, 0) != HAL_OK) {
        return HAL_ERROR;
    }
    return HAL_OK;
}

/* ----------------------------------------------------------------------------
 * GPIO + I2C1 clock setup. Called by HAL_I2C_Init via HAL_I2C_MspInit override.
 * --------------------------------------------------------------------------*/
void HAL_I2C_MspInit(I2C_HandleTypeDef *hi2c)
{
    if (hi2c->Instance != BUS_I2C1_INSTANCE) {
        return;
    }

    GPIO_InitTypeDef g = {0};
    BUS_I2C1_SCL_GPIO_CLK_ENABLE();
    BUS_I2C1_SDA_GPIO_CLK_ENABLE();

    g.Mode      = GPIO_MODE_AF_OD;
    g.Pull      = GPIO_NOPULL;
    g.Speed     = GPIO_SPEED_FREQ_LOW;
    g.Alternate = BUS_I2C1_SCL_GPIO_AF;
    g.Pin       = BUS_I2C1_SCL_GPIO_PIN;
    HAL_GPIO_Init(BUS_I2C1_SCL_GPIO_PORT, &g);

    g.Pin       = BUS_I2C1_SDA_GPIO_PIN;
    g.Alternate = BUS_I2C1_SDA_GPIO_AF;
    HAL_GPIO_Init(BUS_I2C1_SDA_GPIO_PORT, &g);

    __HAL_RCC_I2C1_CLK_ENABLE();
}

void HAL_I2C_MspDeInit(I2C_HandleTypeDef *hi2c)
{
    if (hi2c->Instance != BUS_I2C1_INSTANCE) {
        return;
    }
    __HAL_RCC_I2C1_CLK_DISABLE();
    HAL_GPIO_DeInit(BUS_I2C1_SCL_GPIO_PORT, BUS_I2C1_SCL_GPIO_PIN);
    HAL_GPIO_DeInit(BUS_I2C1_SDA_GPIO_PORT, BUS_I2C1_SDA_GPIO_PIN);
}

/* ----------------------------------------------------------------------------
 * BSP entry points
 * --------------------------------------------------------------------------*/
int32_t BSP_I2C1_Init(void)
{
    if (s_i2c1_init_refcount++ == 0u) {
        if (MX_I2C1_Init(&hi2c1) != HAL_OK) {
            s_i2c1_init_refcount = 0u;
            return BSP_ERROR_BUS_FAILURE;
        }
    }
    return BSP_ERROR_NONE;
}

int32_t BSP_I2C1_DeInit(void)
{
    if (s_i2c1_init_refcount == 0u) {
        return BSP_ERROR_NONE;
    }
    if (--s_i2c1_init_refcount == 0u) {
        if (HAL_I2C_DeInit(&hi2c1) != HAL_OK) {
            return BSP_ERROR_BUS_FAILURE;
        }
    }
    return BSP_ERROR_NONE;
}

int32_t BSP_I2C1_IsReady(uint16_t DevAddr, uint32_t Trials)
{
    return (HAL_I2C_IsDeviceReady(&hi2c1, DevAddr, Trials, BUS_I2C1_POLL_TIMEOUT) == HAL_OK)
        ? BSP_ERROR_NONE : BSP_ERROR_BUSY;
}

int32_t BSP_I2C1_WriteReg(uint16_t Addr, uint16_t Reg, uint8_t *pData, uint16_t Length)
{
    return (HAL_I2C_Mem_Write(&hi2c1, Addr, Reg, I2C_MEMADD_SIZE_8BIT,
                              pData, Length, BUS_I2C1_POLL_TIMEOUT) == HAL_OK)
        ? BSP_ERROR_NONE : BSP_ERROR_BUS_FAILURE;
}

int32_t BSP_I2C1_ReadReg(uint16_t Addr, uint16_t Reg, uint8_t *pData, uint16_t Length)
{
    return (HAL_I2C_Mem_Read(&hi2c1, Addr, Reg, I2C_MEMADD_SIZE_8BIT,
                             pData, Length, BUS_I2C1_POLL_TIMEOUT) == HAL_OK)
        ? BSP_ERROR_NONE : BSP_ERROR_BUS_FAILURE;
}

int32_t BSP_I2C1_WriteReg16(uint16_t Addr, uint16_t Reg, uint8_t *pData, uint16_t Length)
{
    return (HAL_I2C_Mem_Write(&hi2c1, Addr, Reg, I2C_MEMADD_SIZE_16BIT,
                              pData, Length, BUS_I2C1_POLL_TIMEOUT) == HAL_OK)
        ? BSP_ERROR_NONE : BSP_ERROR_BUS_FAILURE;
}

int32_t BSP_I2C1_ReadReg16(uint16_t Addr, uint16_t Reg, uint8_t *pData, uint16_t Length)
{
    return (HAL_I2C_Mem_Read(&hi2c1, Addr, Reg, I2C_MEMADD_SIZE_16BIT,
                             pData, Length, BUS_I2C1_POLL_TIMEOUT) == HAL_OK)
        ? BSP_ERROR_NONE : BSP_ERROR_BUS_FAILURE;
}

int32_t BSP_I2C1_Send(uint16_t DevAddr, uint8_t *pData, uint16_t Length)
{
    return (HAL_I2C_Master_Transmit(&hi2c1, DevAddr, pData, Length, BUS_I2C1_POLL_TIMEOUT) == HAL_OK)
        ? BSP_ERROR_NONE : BSP_ERROR_BUS_FAILURE;
}

int32_t BSP_I2C1_Recv(uint16_t DevAddr, uint8_t *pData, uint16_t Length)
{
    return (HAL_I2C_Master_Receive(&hi2c1, DevAddr, pData, Length, BUS_I2C1_POLL_TIMEOUT) == HAL_OK)
        ? BSP_ERROR_NONE : BSP_ERROR_BUS_FAILURE;
}

int32_t BSP_I2C1_SendRecv(uint16_t DevAddr, uint8_t *pTxdata, uint8_t *pRxdata, uint16_t Length)
{
    if (HAL_I2C_Master_Transmit(&hi2c1, DevAddr, pTxdata, Length, BUS_I2C1_POLL_TIMEOUT) != HAL_OK) {
        return BSP_ERROR_BUS_FAILURE;
    }
    if (HAL_I2C_Master_Receive(&hi2c1, DevAddr, pRxdata, Length, BUS_I2C1_POLL_TIMEOUT) != HAL_OK) {
        return BSP_ERROR_BUS_FAILURE;
    }
    return BSP_ERROR_NONE;
}

int32_t BSP_GetTick(void)
{
    return (int32_t)HAL_GetTick();
}
