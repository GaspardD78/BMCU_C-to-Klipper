// Startup for CH32V20x

#include "autoconf.h"
#include "sched.h"
#include "internal.h"

extern void SystemInit(void);

void __attribute__((noreturn))
riscv_main(void)
{
    SystemInit();
    clock_init();
    gpio_init();
    timer_init();
#ifdef CONFIG_SERIAL
    serial_init();
#endif
    sched_main();
    for (;;)
        ;
}
