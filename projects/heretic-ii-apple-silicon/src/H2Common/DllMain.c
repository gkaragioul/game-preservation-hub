//
// DllMain.c
//
// Copyright 1998 Raven Software
//

#include <windows.h>
#include "ResourceManager.h"
#include "SinglyLinkedList.h"

extern ResourceManager_t sllist_nodes_mgr;

static void H2Common_Attach(void)
{
	ResMngr_Con(&sllist_nodes_mgr, SLL_NODE_SIZE, SLL_NODE_BLOCK_SIZE);
}

static void H2Common_Detach(void)
{
	ResMngr_Des(&sllist_nodes_mgr);
}

#ifdef __MACOS_NATIVE__
__attribute__((constructor))
static void H2Common_MacOSConstructor(void)
{
	H2Common_Attach();
}

__attribute__((destructor))
static void H2Common_MacOSDestructor(void)
{
	H2Common_Detach();
}
#endif

BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpvReserved)
{
	switch (fdwReason)
	{
		case DLL_PROCESS_ATTACH:
			H2Common_Attach();
			break;

		case DLL_PROCESS_DETACH:
			H2Common_Detach();
			break;

		default:
			break;
	}

	return TRUE;
}
