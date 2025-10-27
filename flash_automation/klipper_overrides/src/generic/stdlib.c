// Minimal C library routines for bare-metal builds
//
// Copyright (C) 2024  Contributors
//
// This file may be distributed under the terms of the GNU GPLv3 license.

#include <stddef.h>
#include <stdint.h>

void *
memcpy(void *dest, const void *src, size_t n)
{
    uint8_t *d = dest;
    const uint8_t *s = src;
    for (size_t i = 0; i < n; ++i)
        d[i] = s[i];
    return dest;
}

void *
memmove(void *dest, const void *src, size_t n)
{
    uint8_t *d = dest;
    const uint8_t *s = src;
    if (d == s || n == 0)
        return dest;
    if (d < s) {
        for (size_t i = 0; i < n; ++i)
            d[i] = s[i];
    } else {
        for (size_t i = n; i > 0; --i)
            d[i - 1] = s[i - 1];
    }
    return dest;
}

void *
memset(void *dest, int c, size_t n)
{
    uint8_t *d = dest;
    uint8_t v = c;
    for (size_t i = 0; i < n; ++i)
        d[i] = v;
    return dest;
}

int
memcmp(const void *lhs, const void *rhs, size_t n)
{
    const uint8_t *a = lhs;
    const uint8_t *b = rhs;
    for (size_t i = 0; i < n; ++i) {
        if (a[i] != b[i])
            return (int)a[i] - (int)b[i];
    }
    return 0;
}

void *
memchr(const void *ptr, int value, size_t n)
{
    const uint8_t *p = ptr;
    uint8_t v = value;
    for (size_t i = 0; i < n; ++i)
        if (p[i] == v)
            return (void *)(p + i);
    return NULL;
}

size_t
strlen(const char *s)
{
    size_t len = 0;
    while (s[len])
        ++len;
    return len;
}

int
strcmp(const char *a, const char *b)
{
    while (*a && (*a == *b)) {
        ++a;
        ++b;
    }
    return (unsigned char)*a - (unsigned char)*b;
}

int
__ctzsi2(unsigned int value)
{
    if (!value)
        return 32;
    return __builtin_ctz(value);
}

int
__clzsi2(unsigned int value)
{
    if (!value)
        return 32;
    return __builtin_clz(value);
}
