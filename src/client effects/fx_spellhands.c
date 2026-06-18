//
// fx_spellhands.c
//
// Copyright 1998 Raven Software
//

#include "Client Effects.h"
#include "Matrix.h"
#include "Particle.h"
#include "Reference.h"
#include "Utilities.h"
#include "Vector.h"
#include "g_playstats.h"

#define SH_MAX_TRAIL_SCALE			8.0f //mxd
#define SH_TRAIL_SCALE_INCREMENT	0.35f //mxd

static qboolean SpellHandsTrailUpdate(client_entity_t* self, centity_t* owner) //mxd. Named 'FXSpellHandsThink' in original logic.
{
#define SH_PARTICLE_DURATION	400 //mxd

	// If we've timed out, stop the effect (allow for fading). If we're not on a time limit, check the EF flag.
	if ((self->LifeTime > 0 && self->LifeTime < fx_time) || (self->LifeTime <= 0 && !(owner->current.effects & EF_TRAILS_ENABLED)))
	{
		self->Update = RemoveSelfAI;
		self->updateTime = SH_PARTICLE_DURATION; //BUGFIX: mxd. 'fxi.cl->time + 500' in original logic (makes no sense: updateTime is ADDED to fxi.cl->time in UpdateEffects()).

		return true;
	}

	// Spell cooking previously emitted atlas particles from the hands. Even soft
	// cells are still billboard quads in OpenGL and can show diamond/card edges
	// in both graphics profiles, so keep the timing carrier alive but do not draw
	// this particle layer.
	return true;
}

void FXSpellHands(centity_t* owner, const int type, const int flags, vec3_t origin)
{
	char lifetime;
	fxi.GetEffect(owner, flags, clientEffectSpawners[FX_SPELLHANDS].formatString, &lifetime);

	short refpoints = (1 << CORVUS_RIGHTHAND);
	if (flags & CEF_FLAG6)
		refpoints |= (1 << CORVUS_LEFTHAND);

	// Add a fiery trail effect to the player's hands / feet etc.
	int next_think_time;

	switch (R_DETAIL) //mxd. DETAIL_LOW ? 75 : 50 in original logic.
	{
		default:
		case DETAIL_LOW:		next_think_time = 75; break;
		case DETAIL_NORMAL:		next_think_time = 50; break;
		case DETAIL_HIGH:		next_think_time = 25; break;
		case DETAIL_UBERHIGH:	next_think_time = 0; break; // Update each frame --mxd.
	}

	for (short p = 0; p < 16; p++)
	{
		if (!(refpoints & (1 << p)))
			continue;

		client_entity_t* trail = ClientEntity_new(type, flags, origin, NULL, next_think_time);

		// Keep spell-hand aura particles on the normal alpha atlas. The additive
		// atlas contains spark/fire cells that can read as cards while cooking.
		trail->flags = (trail->flags | CEF_NO_DRAW) & ~CEF_ADDITIVE_PARTS;
		trail->SpawnInfo = (flags & (CEF_FLAG7 | CEF_FLAG8)) >> 6;
		trail->LifeTime = ((lifetime > 0) ? fx_time + lifetime * 100 : -1);
		trail->refPoint = p;
		trail->Scale = 3.0f; //mxd
		trail->AddToView = LinkedEntityUpdatePlacement;
		trail->Update = SpellHandsTrailUpdate;

		AddEffect(owner, trail);
	}
}
