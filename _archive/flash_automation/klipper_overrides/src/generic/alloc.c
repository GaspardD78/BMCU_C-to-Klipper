// Dynamic memory pool tailored for CH32V20x builds
//
// Copyright (C) 2024  Contributors
//
// This file may be distributed under the terms of the GNU GPLv3 license.

#include "autoconf.h"
#include "misc.h" // dynmem_start

// The CH32V203 provides 20 KiB of SRAM but we must reserve space for the
// stack, peripheral buffers, and firmware globals. A 12 KiB pool
// keeps the linker within the available RAM while leaving headroom
// for the runtime.
static char dynmem_pool[12 * 1024];

void *
dynmem_start(void)
{
    return dynmem_pool;
}

void *
dynmem_end(void)
{
    return &dynmem_pool[sizeof(dynmem_pool)];
}
