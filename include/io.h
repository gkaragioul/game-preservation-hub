#pragma once

#ifndef _WIN32

#include <glob.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#define _A_SUBDIR 0x10

struct _finddata_t
{
	unsigned attrib;
	char name[260];
};

typedef struct h2_find_handle_s
{
	glob_t glob;
	size_t index;
} h2_find_handle_t;

static inline void h2_find_fill(const char* path, struct _finddata_t* out)
{
	const char* slash = strrchr(path, '/');
	const char* name = slash != NULL ? slash + 1 : path;
	snprintf(out->name, sizeof(out->name), "%s", name);

	struct stat st;
	out->attrib = (stat(path, &st) == 0 && S_ISDIR(st.st_mode)) ? _A_SUBDIR : 0;
}

static inline intptr_t _findfirst(const char* pattern, struct _finddata_t* out)
{
	h2_find_handle_t* handle = (h2_find_handle_t*)calloc(1, sizeof(*handle));
	if (handle == NULL)
		return -1;

	if (glob(pattern, 0, NULL, &handle->glob) != 0 || handle->glob.gl_pathc == 0)
	{
		globfree(&handle->glob);
		free(handle);
		return -1;
	}

	handle->index = 0;
	h2_find_fill(handle->glob.gl_pathv[0], out);
	return (intptr_t)handle;
}

static inline int _findnext(intptr_t raw_handle, struct _finddata_t* out)
{
	h2_find_handle_t* handle = (h2_find_handle_t*)raw_handle;
	if (handle == NULL)
		return -1;

	handle->index++;
	if (handle->index >= handle->glob.gl_pathc)
		return -1;

	h2_find_fill(handle->glob.gl_pathv[handle->index], out);
	return 0;
}

static inline int _findclose(intptr_t raw_handle)
{
	h2_find_handle_t* handle = (h2_find_handle_t*)raw_handle;
	if (handle == NULL)
		return -1;

	globfree(&handle->glob);
	free(handle);
	return 0;
}

#else
#include_next <io.h>
#endif
