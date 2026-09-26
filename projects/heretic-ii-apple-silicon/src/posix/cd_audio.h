#pragma once

#include "q_shared.h"

void CDAudio_Init(void);
void CDAudio_Shutdown(void);
void CDAudio_Play(int track, qboolean looping);
void CDAudio_Stop(void);
void CDAudio_Update(void);
qboolean CDAudio_IsActive(void);
