//
// Hunk.c
//
// Copyright 1998 Raven Software
//

#include "Hunk.h"
#include "gl3_Local.h"

static byte* membase;

static int hunkcount;
static uint hunkmaxsize;
static uint cursize;

// Q2 counterpart
void* Hunk_Begin(const int maxsize)
{
	// Reserve a huge chunk of memory, but don't commit any yet
	// YQ2: plus 32 bytes for cacheline
	hunkmaxsize = maxsize + sizeof(uint) + 32;
	cursize = 0;

#ifdef _WIN32
	membase = VirtualAlloc(NULL, maxsize, MEM_RESERVE, PAGE_NOACCESS);
	if (membase == NULL)
		ri.Sys_Error(ERR_DROP, "VirtualAlloc reserve failed");
#else
	membase = aligned_alloc(32, (size_t)((hunkmaxsize + 31) & ~31));
	if (membase == NULL)
		ri.Sys_Error(ERR_DROP, "Hunk_Begin allocation failed");
#endif

	return membase;
}

// Q2 counterpart
void* Hunk_Alloc(int size)
{
	// Round to cacheline.
	size = (size + 31) & ~31;

	// Commit pages as needed.
	cursize += size;

	if (cursize > hunkmaxsize)
		ri.Sys_Error(ERR_DROP, "Hunk_Alloc overflow");

	return membase + cursize - size;
}

// Q2 counterpart
int Hunk_End(void)
{
	hunkcount++;
	return (int)cursize;
}

// Q2 counterpart
void Hunk_Free(void* buf)
{
	if (buf != NULL)
#ifdef _WIN32
		VirtualFree(buf, 0, MEM_RELEASE);
#else
		free(buf);
#endif

	hunkcount--;
}
