//
// fx_spellchange.c
//
// Copyright 1998 Raven Software
//

#include "Client Effects.h"
#include "Particle.h"
#include "Random.h"
#include "Vector.h"
#include "ce_DLight.h"

#define NUM_SPELL_BITS	12
#define LIGHT_LIFETIME	1000

static qboolean SpellChangePuffUpdate(client_entity_t* self, centity_t* owner) //mxd. Named 'FXSpellChangeLightThink' in original logic.
{
	if (fx_time - self->startTime <= LIGHT_LIFETIME)
	{
		self->dlight->intensity = 200.0f * (float)(LIGHT_LIFETIME - (fx_time - self->startTime)) / (float)LIGHT_LIFETIME;
		return true;
	}

	return false;
}

void FXSpellChange(centity_t* owner, const int type, const int flags, vec3_t origin)
{
	vec3_t dir;
	int spell_type = 0;
	fxi.GetEffect(owner, flags, clientEffectSpawners[FX_SPELL_CHANGE].formatString, dir, &spell_type);

	paletteRGBA_t color;

	switch (spell_type)
	{
		case 1: // Red / fireball.
			color.c = 0xFF0000FF;
			break;

		case 2: // Indigo / array.
			color.c = 0xFFFF0080;
			break;

		case 3: // Blue / sphere.
			color.c = 0xFFFF0000;
			break;

		case 4: // Green / mace ball.
			color.c = 0xFF00FF00;
			break;

		case 5: // Yellow / firewall.
			color.c = 0xFF0080FF;
			break;

		case 6: // Big red / red rain bow. //TODO: same as case 1...
			color.c = 0xFF0000FF;
			break;

		case 7: // Big yellow / phoenix.
			color.c = 0xFF00FFFF;
			break;

		case 0: // Default color--white.
		default:
			color.c = 0x80FFFFFF;
			break;
	}

	Vec3ScaleAssign(-32.0f, dir);

	// Create the new effect. Keep spell-change particles on the normal alpha
	// atlas; the additive spark cells read as diamond/card flecks while a spell
	// is being selected and cooked.
	client_entity_t* spell_puff = ClientEntity_new(type, (int)(flags | CEF_OWNERS_ORIGIN | CEF_NO_DRAW), origin, NULL, 100);

	spell_puff->radius = 32.0f;
	spell_puff->dlight = CE_DLight_new(color, 150.0f, 0.0f);
	spell_puff->startTime = fx_time;
	spell_puff->Update = SpellChangePuffUpdate;

	// No visible particles here. The old additive spark/mist bits are billboard
	// quads and can read as diamonds/cards during spell cooking. The fading
	// dlight above preserves the selection feedback without drawing card art.

	AddEffect(owner, spell_puff);
}
