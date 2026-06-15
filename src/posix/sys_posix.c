#include "Quake2Main.h"
#include "windows.h"
#include "qcommon.h"
#include "input.h"

#include <dlfcn.h>
#include <libgen.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int sys_argc;
static char** sys_argv;

static void BuildModuleName(const char* dll_name, char* out, size_t out_size)
{
	if (strstr(dll_name, ".dylib") != NULL || strchr(dll_name, '/') != NULL)
		snprintf(out, out_size, "%s", dll_name);
	else
		snprintf(out, out_size, "%s.dylib", dll_name);
}

void Sys_LoadGameDll(const char* dll_name, HINSTANCE* hinst, DWORD* checksum)
{
	char module[MAX_OSPATH];
	char candidate[MAX_OSPATH];
	BuildModuleName(dll_name, module, sizeof(module));

	char* path = NULL;
	while ((path = FS_NextPath(path)) != NULL)
	{
		snprintf(candidate, sizeof(candidate), "%s/%s", path, module);
		*hinst = dlopen(candidate, RTLD_NOW | RTLD_LOCAL);
		if (*hinst != NULL)
			break;
	}

	if (*hinst == NULL)
	{
		snprintf(candidate, sizeof(candidate), "base/%s", module);
		*hinst = dlopen(candidate, RTLD_NOW | RTLD_LOCAL);
	}

	if (*hinst == NULL)
	{
		snprintf(candidate, sizeof(candidate), "%s", module);
		*hinst = dlopen(candidate, RTLD_NOW | RTLD_LOCAL);
	}

	if (*hinst == NULL)
		Sys_Error("Failed to load %s: %s", dll_name, dlerror());

	if (checksum != NULL)
		*checksum = 0;

	Com_DDPrintf(2, "dlopen (%s)\n", candidate);
}

void Sys_UnloadGameDll(const char* name, HINSTANCE* hinst)
{
	if (hinst != NULL && *hinst != NULL)
	{
		if (dlclose(*hinst) != 0)
			Sys_Error("Failed to unload %s: %s", name, dlerror());
		*hinst = NULL;
	}
}

H2R_NORETURN void Sys_Error(const char* error, ...)
{
	va_list argptr;
	char text[2048];

	va_start(argptr, error);
	vsnprintf(text, sizeof(text), error, argptr);
	va_end(argptr);

	fprintf(stderr, "Sys_Error: %s\n", text);
	CL_Shutdown();
	exit(1);
}

H2R_NORETURN void Sys_Quit(void)
{
	CL_Shutdown();
	exit(0);
}

void Sys_Init(void)
{
	Set_Com_Printf(Com_Printf);
}

char* Sys_ConsoleInput(void)
{
	return NULL;
}

void Sys_ConsoleOutput(const char* string)
{
	fputs(string, stdout);
}

int Quake2Main(int argc, char** argv)
{
	sys_argc = argc;
	sys_argv = argv;

	Qcommon_Init(sys_argc, sys_argv);

	long long oldtime = Sys_Microseconds();
	while (true)
	{
		Sys_Nanosleep(100000);
		const long long newtime = Sys_Microseconds();
		curtime = (int)(newtime / 1000ll);
		Qcommon_Frame((int)(newtime - oldtime));
		oldtime = newtime;
	}
}
