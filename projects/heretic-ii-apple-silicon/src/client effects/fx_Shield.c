//
// fx_Shield.c
//
// Copyright 1998 Raven Software
//

#include "Client Effects.h"
#include "Particle.h"
#include "Random.h"
#include "Utilities.h"
#include "Vector.h"
#include "g_playstats.h"

#define SHIELD_TRAIL_DELAY	100
#define SHIELD_RADIUS		32.0f
#define NUM_SHIELD_SPARKS	16

static struct model_s* shield_model;

void PreCacheShield(void)
{
	shield_model = fxi.RegisterModel("sprites/spells/spark_blue.sp2");
}

static qboolean LightningShieldSparkAddToView(client_entity_t* self, centity_t* owner) //mxd. Named 'FXShieldSparkThink' in original logic.
{
	// Update the angle of the spark.
	VectorMA(self->direction, (float)(fx_time - self->lastThinkTime) / 1000.0f, self->velocity2, self->direction);

	// Update the position of the spark.
	vec3_t forward;
	AngleVectors(self->direction, forward, NULL, NULL);
	VectorMA(owner->origin, self->radius, forward, self->r.origin);

	self->lastThinkTime = fx_time;

	// The original shield drew orbiting spark_blue sprites plus 16x16 spark
	// trails. In OpenGL those sprites are visible diamond/card billboards around
	// the player while the defensive spell is being cooked. Keep the shield
	// timing/effect entity alive, but do not draw that card layer.
	return true;
}

static qboolean LightningShieldSparkUpdate(client_entity_t* self, centity_t* owner) //mxd. Named 'FXShieldTerminate' in original logic.
{
	// Don't instantly delete yourself. Don't accept any more updates and die out within a second.
	self->d_alpha = -1.2f; // Fade out.
	self->SpawnDelay = fx_time + 2000; // No more particles.
	self->updateTime = 1000; // Die in one second.
	self->Update = RemoveSelfAI;

	return true;
}

void FXLightningShield(centity_t* owner, const int type, const int flags, vec3_t origin)
{
	const int count = GetScaledCount(NUM_SHIELD_SPARKS, 0.5f);

	// Add spinning electrical sparks.
	for (int i = 0; i < count; i++)
	{
		client_entity_t* spark = ClientEntity_new(type, flags & (~CEF_OWNERS_ORIGIN), origin, NULL, SHIELD_DURATION * 1000);

		spark->radius = SHIELD_RADIUS;
		spark->flags |= (CEF_ADDITIVE_PARTS | CEF_ABSOLUTE_PARTS | CEF_NO_DRAW);
		spark->r.flags = (RF_TRANS_ADD | RF_TRANS_ADD_ALPHA);
		spark->r.model = &shield_model;
		spark->color = color_white;
		spark->alpha = 0.1f;
		spark->d_alpha = 0.5f;

		VectorClear(spark->direction);

		// This is a velocity around the sphere.
		for (int c = 0; c < 2; c++)
		{
			spark->direction[c] = flrand(0.0f, 360.0f); // This angle is kept at a constant distance from org.
			spark->velocity2[c] = flrand(-180.0f, 180.0f);
			spark->velocity2[c] += 180.0f * Q_signf(spark->velocity2[c]); // Assure that the sparks are moving around at a pretty good clip.
		}

		spark->lastThinkTime = fx_time;
		spark->SpawnDelay = fx_time + SHIELD_TRAIL_DELAY;

		vec3_t forward;
		AngleVectors(spark->direction, forward, NULL, NULL);
		VectorMA(owner->origin, spark->radius, forward, spark->r.origin);

		spark->AddToView = LightningShieldSparkAddToView;
		spark->Update = LightningShieldSparkUpdate;

		AddEffect(owner, spark);
	}
}
