/* SPDX-License-Identifier: GPL-2.0-only
 *
 * NB4+ external NOR reader - runs from SRAM only, loaded through the STM32
 * ROM DFU bootloader. It never writes internal flash and only ever sends the
 * read commands 0x9F (JEDEC ID) and 0x03 (READ) to the SPI NOR.
 *
 * Memory map (outside the ROM bootloader's working RAM):
 *   0x20008000  this program (vector table first, entered via DfuSe "leave")
 *   0x20007F00  parameter block written by the PC together with the program
 *   0x2000FF00  result header, followed directly by the data at 0x20010000
 *
 * NOR wiring as used by the stock firmware: PG6 CS, PG12 MISO, PG13 SCK,
 * PG14 MOSI. The pins are bit-banged as plain GPIO (SPI mode 0).
 */
#include <stdint.h>

#define REG(a) (*(volatile uint32_t *)(a))

#define RCC_BASE        0x40023800u
#define RCC_CR          REG(RCC_BASE + 0x00)
#define RCC_PLLCFGR     REG(RCC_BASE + 0x04)
#define RCC_CFGR        REG(RCC_BASE + 0x08)
#define RCC_CIR         REG(RCC_BASE + 0x0C)
#define RCC_AHB2RSTR    REG(RCC_BASE + 0x14)
#define RCC_AHB1ENR     REG(RCC_BASE + 0x30)
#define RCC_APB2ENR     REG(RCC_BASE + 0x44)

#define GPIOG           0x40021800u
#define GPIOI           0x40022000u
#define GPIO_MODER(p)   REG((p) + 0x00)
#define GPIO_OSPEEDR(p) REG((p) + 0x08)
#define GPIO_PUPDR(p)   REG((p) + 0x0C)
#define GPIO_IDR(p)     REG((p) + 0x10)
#define GPIO_BSRR(p)    REG((p) + 0x18)

#define SYSCFG_MEMRMP   REG(0x40013800u)
#define SYST_CSR        REG(0xE000E010u)
#define SCB_VTOR        REG(0xE000ED08u)
#define SCB_AIRCR       REG(0xE000ED0Cu)
#define NVIC_ICER(n)    REG(0xE000E180u + 4u * (n))
#define NVIC_ICPR(n)    REG(0xE000E280u + 4u * (n))

#define PIN_CS          6u
#define PIN_MISO        12u
#define PIN_SCK         13u
#define PIN_MOSI        14u
#define PIN_PWR_HOLD    14u   /* PI14, power latch as set by the stock firmware */

#define PARAM_MAGIC     0x4E4F5251u   /* "QRON" */
#define RESULT_MAGIC    0x4E4F5244u   /* "DRON" */
#define MAX_CHUNK       0x20000u      /* 128 KiB */
#define MAX_NOR         0x1000000u    /* 16 MiB address space of a 24-bit READ */

#define FLAG_RESET_INSTEAD_OF_JUMP  1u

enum {
  ST_OK = 1,
  ST_BAD_PARAMS = 2,
  ST_NO_FLASH = 3,
  ST_REREAD_MISMATCH = 4,
};

struct params {
  uint32_t magic;
  uint32_t start;
  uint32_t length;
  uint32_t flags;
};

struct result {
  uint32_t magic;
  uint32_t status;
  uint32_t jedec;
  uint32_t start;
  uint32_t length;
  uint32_t crc_first;
  uint32_t crc_second;
  uint32_t seq;
};

#define PARAMS  ((volatile struct params *)0x20007F00u)
#define RESULT  ((volatile struct result *)0x2000FF00u)
#define BUFFER  ((volatile uint8_t *)0x20010000u)

static inline void pin_hi(uint32_t port, uint32_t pin) { GPIO_BSRR(port) = 1u << pin; }
static inline void pin_lo(uint32_t port, uint32_t pin) { GPIO_BSRR(port) = 1u << (pin + 16u); }

static void set_mode(uint32_t port, uint32_t pin, uint32_t mode)
{
  GPIO_MODER(port) = (GPIO_MODER(port) & ~(3u << (2u * pin))) | (mode << (2u * pin));
}

static void set_pull(uint32_t port, uint32_t pin, uint32_t pull)
{
  GPIO_PUPDR(port) = (GPIO_PUPDR(port) & ~(3u << (2u * pin))) | (pull << (2u * pin));
}

static void short_delay(void)
{
  for (volatile int i = 0; i < 2; i++) {
  }
}

/* SPI mode 0: set MOSI, rising edge, sample MISO while SCK is high, falling edge. */
static uint8_t spi_xfer(uint8_t out)
{
  uint8_t in = 0;
  for (int bit = 7; bit >= 0; bit--) {
    if (out & (1u << bit)) pin_hi(GPIOG, PIN_MOSI);
    else pin_lo(GPIOG, PIN_MOSI);
    short_delay();
    pin_hi(GPIOG, PIN_SCK);
    short_delay();
    in = (uint8_t)((in << 1) | ((GPIO_IDR(GPIOG) >> PIN_MISO) & 1u));
    pin_lo(GPIOG, PIN_SCK);
  }
  return in;
}

static void cs_low(void) { pin_lo(GPIOG, PIN_CS); short_delay(); }
static void cs_high(void) { short_delay(); pin_hi(GPIOG, PIN_CS); short_delay(); }

static uint32_t read_jedec(void)
{
  cs_low();
  spi_xfer(0x9F);
  uint32_t id = (uint32_t)spi_xfer(0) << 16;
  id |= (uint32_t)spi_xfer(0) << 8;
  id |= spi_xfer(0);
  cs_high();
  return id;
}

static uint32_t crc32_update(uint32_t crc, uint8_t byte)
{
  crc ^= byte;
  for (int i = 0; i < 8; i++)
    crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
  return crc;
}

/* Reads [start, start+length) once; stores it when store != 0. Returns the CRC-32. */
static uint32_t read_range(uint32_t start, uint32_t length, int store)
{
  uint32_t crc = 0xFFFFFFFFu;
  cs_low();
  spi_xfer(0x03);
  spi_xfer((uint8_t)(start >> 16));
  spi_xfer((uint8_t)(start >> 8));
  spi_xfer((uint8_t)start);
  for (uint32_t i = 0; i < length; i++) {
    uint8_t b = spi_xfer(0);
    if (store) BUFFER[i] = b;
    crc = crc32_update(crc, b);
  }
  cs_high();
  return ~crc;
}

static void pins_init(void)
{
  RCC_AHB1ENR |= (1u << 6) | (1u << 8);   /* GPIOG, GPIOI clocks */
  (void)RCC_AHB1ENR;

  pin_hi(GPIOI, PIN_PWR_HOLD);            /* keep the radio powered */
  set_mode(GPIOI, PIN_PWR_HOLD, 1u);

  pin_hi(GPIOG, PIN_CS);                  /* deselect before driving the pin */
  pin_lo(GPIOG, PIN_SCK);
  pin_lo(GPIOG, PIN_MOSI);
  set_mode(GPIOG, PIN_CS, 1u);
  set_mode(GPIOG, PIN_SCK, 1u);
  set_mode(GPIOG, PIN_MOSI, 1u);
  set_mode(GPIOG, PIN_MISO, 0u);
  set_pull(GPIOG, PIN_MISO, 1u);
  set_pull(GPIOG, PIN_CS, 1u);
}

static void pins_release(void)
{
  pin_hi(GPIOG, PIN_CS);
  set_mode(GPIOG, PIN_SCK, 0u);
  set_mode(GPIOG, PIN_MOSI, 0u);
  set_mode(GPIOG, PIN_CS, 0u);            /* pull-up keeps the NOR deselected */
}

__attribute__((noreturn)) static void back_to_rom_dfu(uint32_t flags)
{
  __asm volatile("cpsid i" ::: "memory");
  SYST_CSR = 0;
  for (int n = 0; n < 8; n++) {
    NVIC_ICER(n) = 0xFFFFFFFFu;
    NVIC_ICPR(n) = 0xFFFFFFFFu;
  }

  if (flags & FLAG_RESET_INSTEAD_OF_JUMP) {
    /* Fallback: system reset; SRAM is retained and BOOT0 (held DFU button) selects ROM DFU. */
    SCB_AIRCR = 0x05FA0004u;
    for (;;) {
    }
  }

  /* Clock tree back to reset defaults (HSI) so the ROM bootloader can set it up again. */
  RCC_CR |= 1u;                           /* HSION */
  while (!(RCC_CR & 2u)) {
  }
  RCC_CFGR = 0;                           /* SYSCLK = HSI */
  while (RCC_CFGR & 0xCu) {
  }
  RCC_CR &= ~((1u << 16) | (1u << 18) | (1u << 19) | (1u << 24) | (1u << 26) | (1u << 28));
  RCC_PLLCFGR = 0x24003010u;
  RCC_CIR = 0;

  RCC_AHB2RSTR |= 1u << 7;                /* reset USB OTG FS */
  RCC_AHB2RSTR &= ~(1u << 7);

  RCC_APB2ENR |= 1u << 14;                /* SYSCFG clock */
  (void)RCC_APB2ENR;
  SYSCFG_MEMRMP = 1u;                     /* system memory at 0x00000000 */
  SCB_VTOR = 0;

  const uint32_t sp = REG(0x1FFF0000u);
  const uint32_t pc = REG(0x1FFF0004u);
  __asm volatile(
      "msr msp, %0\n"
      "cpsie i\n"
      "bx %1\n" ::"r"(sp), "r"(pc) : "memory");
  for (;;) {
  }
}

__attribute__((noreturn)) void dumper_main(void)
{
  struct params p;
  p.magic = PARAMS->magic;
  p.start = PARAMS->start;
  p.length = PARAMS->length;
  p.flags = PARAMS->flags;
  PARAMS->magic = 0;                      /* a stale block must never run twice */

  RESULT->magic = 0;
  RESULT->status = 0;
  RESULT->jedec = 0;
  RESULT->start = p.start;
  RESULT->length = p.length;
  RESULT->crc_first = 0;
  RESULT->crc_second = 0;
  RESULT->seq = RESULT->seq + 1u;

  uint32_t status;
  if (p.magic != PARAM_MAGIC || p.length == 0 || p.length > MAX_CHUNK ||
      p.start >= MAX_NOR || p.length > MAX_NOR - p.start) {
    status = ST_BAD_PARAMS;
  } else {
    pins_init();
    uint32_t id = read_jedec();
    RESULT->jedec = id;
    if (id == 0 || id == 0xFFFFFFu) {
      status = ST_NO_FLASH;
    } else {
      uint32_t c1 = read_range(p.start, p.length, 1);
      uint32_t c2 = read_range(p.start, p.length, 0);
      RESULT->crc_first = c1;
      RESULT->crc_second = c2;
      status = (c1 == c2) ? ST_OK : ST_REREAD_MISMATCH;
    }
    pins_release();
  }

  RESULT->status = status;
  RESULT->magic = RESULT_MAGIC;
  back_to_rom_dfu(p.flags);
}

/* Minimal vector table: initial SP and reset handler. */
extern uint32_t _stack_top;
__attribute__((section(".vectors"), used)) const uint32_t vectors[2] = {
  (uint32_t)&_stack_top,
  (uint32_t)&dumper_main,
};
