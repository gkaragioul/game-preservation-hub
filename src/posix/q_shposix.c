#include "qcommon.h"

#include <dirent.h>
#include <errno.h>
#include <glob.h>
#include <mach/mach_time.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

int curtime;

static glob_t find_glob;
static size_t find_index;
static char findpath[MAX_OSPATH];
static qboolean find_active;

long long Sys_Microseconds(void)
{
	static mach_timebase_info_data_t timebase;
	static uint64_t base;

	if (timebase.denom == 0)
		mach_timebase_info(&timebase);
	if (base == 0)
		base = mach_absolute_time();

	const uint64_t elapsed = mach_absolute_time() - base;
	return (long long)(elapsed * timebase.numer / timebase.denom / 1000);
}

void Sys_Nanosleep(const int nanosec)
{
	struct timespec ts;
	ts.tv_sec = nanosec / 1000000000;
	ts.tv_nsec = nanosec % 1000000000;
	nanosleep(&ts, NULL);
}

void Sys_Mkdir(const char* path)
{
	mkdir(path, 0755);
}

qboolean Sys_IsDir(const char* path)
{
	struct stat st;
	return stat(path, &st) == 0 && S_ISDIR(st.st_mode);
}

qboolean Sys_IsFile(const char* path)
{
	struct stat st;
	return stat(path, &st) == 0 && S_ISREG(st.st_mode);
}

qboolean Sys_GetWorkingDir(char* buffer, const size_t len)
{
	return getcwd(buffer, len) != NULL;
}

qboolean Sys_GetOSUserDir(char* buffer, const size_t len)
{
	const char* home = getenv("HOME");
	if (home == NULL || *home == '\0')
		return false;

	snprintf(buffer, len, "%s/Library/Application Support", home);
	return true;
}

static qboolean MatchAttributes(const char* path, const uint musthave, const uint canthave)
{
	struct stat st;
	if (stat(path, &st) != 0)
		return false;

	const qboolean is_dir = S_ISDIR(st.st_mode);
	if ((musthave & SFF_SUBDIR) && !is_dir)
		return false;
	if ((canthave & SFF_SUBDIR) && is_dir)
		return false;

	return true;
}

char* Sys_FindFirst(const char* path, const uint musthave, const uint canthave)
{
	if (find_active)
		Sys_Error("Sys_FindFirst called without close");

	memset(&find_glob, 0, sizeof(find_glob));
	find_index = 0;
	find_active = (glob(path, 0, NULL, &find_glob) == 0);
	if (!find_active)
		return NULL;

	return Sys_FindNext(musthave, canthave);
}

char* Sys_FindNext(const uint musthave, const uint canthave)
{
	if (!find_active)
		return NULL;

	while (find_index < find_glob.gl_pathc)
	{
		const char* path = find_glob.gl_pathv[find_index++];
		const char* name = strrchr(path, '/');
		name = (name != NULL ? name + 1 : path);
		if (strcmp(name, ".") == 0 || strcmp(name, "..") == 0)
			continue;
		if (!MatchAttributes(path, musthave, canthave))
			continue;

		snprintf(findpath, sizeof(findpath), "%s", path);
		return findpath;
	}

	return NULL;
}

void Sys_FindClose(void)
{
	if (find_active)
		globfree(&find_glob);
	find_active = false;
	find_index = 0;
}
