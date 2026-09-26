#pragma once

#ifndef _WIN32

#include <ctype.h>
#include <errno.h>
#include <limits.h>
#include <pthread.h>
#include <stdarg.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <time.h>
#include <unistd.h>

#ifndef __declspec
#define __declspec(x) __attribute__((visibility("default")))
#endif

#ifndef _inline
#define _inline static inline
#endif

#define _In_
#define _In_opt_
#define _Out_

typedef int errno_t;

#define strcpy_s(dst, dstsz, src) ((void)snprintf((dst), (dstsz), "%s", (src)))
#define strcat_s(dst, dstsz, src) ((void)strncat((dst), (src), (dstsz) - strlen(dst) - 1))
#define strncat_s(dst, dstsz, src, count) ((void)strncat((dst), (src), min((size_t)(count), (dstsz) - strlen(dst) - 1)))
#define strncpy_s(dst, dstsz, src, count) ((void)(strncpy((dst), (src), (count)), (dst)[(dstsz) - 1] = '\0'))
#define sprintf_s(dst, dstsz, ...) snprintf((dst), (dstsz), __VA_ARGS__)
#define vsprintf_s(dst, dstsz, fmt, ap) vsnprintf((dst), (dstsz), (fmt), (ap))
#define sscanf_s sscanf
#define _stricmp strcasecmp
#define stricmp strcasecmp
#define _strnicmp strncasecmp
#define _strdup strdup

#ifndef min
#define min(a, b) ((a) < (b) ? (a) : (b))
#endif
#ifndef max
#define max(a, b) ((a) > (b) ? (a) : (b))
#endif

static inline int fopen_s(FILE** fp, const char* path, const char* mode)
{
	*fp = fopen(path, mode);
	return *fp == NULL ? errno : 0;
}

static inline errno_t memmove_s(void* dest, size_t destsz, const void* src, size_t count)
{
	if (dest == NULL || src == NULL || count > destsz)
		return EINVAL;
	memmove(dest, src, count);
	return 0;
}

static inline errno_t memcpy_s(void* dest, size_t destsz, const void* src, size_t count)
{
	if (dest == NULL || src == NULL || count > destsz)
		return EINVAL;
	memcpy(dest, src, count);
	return 0;
}

static inline size_t fread_s(void* buffer, size_t buffer_size, size_t element_size, size_t count, FILE* stream)
{
	if (buffer == NULL || stream == NULL || element_size != 0 && count > buffer_size / element_size)
		return 0;
	return fread(buffer, element_size, count, stream);
}

static inline errno_t localtime_s(struct tm* result, const time_t* timer)
{
	return localtime_r(timer, result) == NULL ? EINVAL : 0;
}

static inline char* strtok_s(char* str, const char* delim, char** ctx)
{
	return strtok_r(str, delim, ctx);
}

#endif
