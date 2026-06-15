#pragma once

#ifndef _WIN32

#include <dlfcn.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

typedef void* HINSTANCE;
typedef void* HMODULE;
typedef void* HANDLE;
typedef void* HWND;
typedef unsigned long DWORD;
typedef int BOOL;
typedef unsigned char BYTE;
typedef wchar_t WCHAR;
typedef long LONG;
typedef long long LONGLONG;
typedef void* LPVOID;
typedef char* LPSTR;
typedef const char* LPCSTR;
typedef unsigned int UINT;

#define WINAPI
#define CALLBACK
typedef DWORD (WINAPI *LPTHREAD_START_ROUTINE)(LPVOID);
#define TRUE 1
#define FALSE 0
#ifndef NULL
#define NULL 0
#endif
#define MAX_PATH 260
#define MB_OK 0
#define MB_ICONWARNING 0
#define INVALID_HANDLE_VALUE ((HANDLE)(intptr_t)-1)
#define INFINITE 0xffffffffu
#define WAIT_OBJECT_0 0
#define DLL_PROCESS_DETACH 0
#define DLL_PROCESS_ATTACH 1

typedef struct win_thread_s {
	pthread_t thread;
	int joined;
	LPTHREAD_START_ROUTINE start;
	LPVOID param;
	DWORD result;
} win_thread_t;

static inline void* win_thread_trampoline(void* arg)
{
	win_thread_t* thread = (win_thread_t*)arg;
	thread->result = thread->start(thread->param);
	return NULL;
}

static inline HANDLE CreateThread(void* attrs, size_t stack_size, LPTHREAD_START_ROUTINE start, LPVOID param, DWORD flags, DWORD* thread_id)
{
	(void)attrs;
	(void)flags;
	win_thread_t* thread = (win_thread_t*)calloc(1, sizeof(*thread));
	if (thread == NULL)
		return NULL;

	thread->start = start;
	thread->param = param;
	if (pthread_create(&thread->thread, NULL, win_thread_trampoline, thread) != 0)
	{
		free(thread);
		return NULL;
	}

	if (thread_id != NULL)
		*thread_id = (DWORD)(uintptr_t)thread->thread;
	(void)stack_size;
	return (HANDLE)thread;
}

static inline DWORD WaitForSingleObject(HANDLE handle, DWORD milliseconds)
{
	(void)milliseconds;
	win_thread_t* thread = (win_thread_t*)handle;
	if (thread == NULL)
		return (DWORD)-1;
	if (!thread->joined)
	{
		pthread_join(thread->thread, NULL);
		thread->joined = 1;
	}
	return WAIT_OBJECT_0;
}

static inline BOOL CloseHandle(HANDLE handle)
{
	win_thread_t* thread = (win_thread_t*)handle;
	if (thread == NULL)
		return FALSE;
	if (!thread->joined)
		pthread_detach(thread->thread);
	free(thread);
	return TRUE;
}

static inline void win_make_dylib_name(const char* path, char* out, size_t out_size)
{
	const char* dot = strrchr(path, '.');
	if (dot != NULL && strcmp(dot, ".dll") == 0)
		snprintf(out, out_size, "%.*s.dylib", (int)(dot - path), path);
	else
		snprintf(out, out_size, "%s.dylib", path);
}

static inline HMODULE win_try_dlopen(const char* path)
{
	return dlopen(path, RTLD_NOW | RTLD_GLOBAL);
}

static inline HMODULE LoadLibraryA(const char* path)
{
	if (path == NULL || path[0] == '\0')
		return NULL;

	HMODULE module = win_try_dlopen(path);
	if (module != NULL)
		return module;

	char dylib[MAX_PATH * 2];
	win_make_dylib_name(path, dylib, sizeof(dylib));
	module = win_try_dlopen(dylib);
	if (module != NULL)
		return module;

	char candidate[MAX_PATH * 2];
	snprintf(candidate, sizeof(candidate), "./%s", dylib);
	module = win_try_dlopen(candidate);
	if (module != NULL)
		return module;

	snprintf(candidate, sizeof(candidate), "base/%s", dylib);
	module = win_try_dlopen(candidate);
	if (module != NULL)
		return module;

	return NULL;
}
static inline HMODULE LoadLibrary(const char* path) { return LoadLibraryA(path); }
static inline void* GetProcAddress(HMODULE handle, const char* name) { return dlsym(handle, name); }
static inline int FreeLibrary(HMODULE handle) { return dlclose(handle) == 0; }
static inline void Sleep(DWORD ms) { usleep(ms * 1000); }
static inline LONG InterlockedExchange(volatile LONG* target, LONG value)
{
	return __sync_lock_test_and_set(target, value);
}
static inline LONG InterlockedCompareExchange(volatile LONG* target, LONG exchange, LONG comparand)
{
	return __sync_val_compare_and_swap(target, comparand, exchange);
}
static inline int MessageBox(HWND hwnd, const char* text, const char* caption, unsigned int type)
{
	(void)hwnd; (void)type;
	fprintf(stderr, "%s: %s\n", caption ? caption : "Message", text ? text : "");
	return 0;
}
static inline void OutputDebugString(const char* text)
{
	if (text != NULL)
		fputs(text, stderr);
}

#ifdef false
#undef false
#endif
#ifdef true
#undef true
#endif

#endif
