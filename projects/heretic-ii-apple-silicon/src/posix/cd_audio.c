#include "qcommon.h"
#include "cd_audio.h"

void CDAudio_Init(void) { (void)Cvar_Get("cd_volume", "0.5", CVAR_ARCHIVE); }
void CDAudio_Shutdown(void) { }
void CDAudio_Play(int track, qboolean looping) { (void)track; (void)looping; }
void CDAudio_Stop(void) { }
void CDAudio_Update(void) { }
qboolean CDAudio_IsActive(void) { return false; }
