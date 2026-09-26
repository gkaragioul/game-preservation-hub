//
// menu_addons.c
//

#include "client.h"
#include "menu_addons.h"
#include "menu_game.h"

typedef struct
{
	const char* title;
	const char* game_dir;
	const char* start_cmd;
	qboolean coop;
} addon_entry_t;

static const addon_entry_t addons[] =
{
	{ "Shadow Slayer", "lanius", "skin lanius ; skill 1 ; map hcanyon", false },
	{ "Zombie Town", "rodent_zone", "coop 1 ; skill 2 ; r_fog_mode 1 ; map rodent_zone/ZTown-Part-1", true },
	{ "Sacred Idol", "sidol", "skill 1 ; r_farclipdist 8192 ; map itown", false },
	{ "Treasure Hunter", "trhunter", "skill 1 ; r_farclipdist 8192 ; map RCanyon", false },
	{ "Yak 1999", "yak1999", "skill 1 ; map game1", false },
	{ "Gates of Atlantis", "gates", "skill 0 ; map entrance", false },
	{ "Atlantis", "atlantis", "skill 0 ; map city", false },
	{ "Andoria Waterworks", "andoria_waterworks", "skill 1 ; map ws_and1", false },
	{ "Corvus Chronicles", "corvcron", "skill 1 ; map CORVCRON", false },
	{ "A Forgotten Island", "island", "skill 1 ; map island1", false },
	{ "Phantasmagoria", "phantasmagoria", "skill 1 ; map phant", false },
	{ "Sacrifist", "sacrifist", "skill 1 ; map sacrifist", false },
	{ "Silver Spring Asylum", "ssasylum", "skill 1 ; map ssasylum", false },
	{ "Blupipe", "blupipe", "skill 1 ; map blupipe", false },
	{ "Head", "head", "skill 1 ; map head", false },
};

static menuframework_t s_addons_menu;
static menuaction_t s_addon_actions[sizeof(addons) / sizeof(addons[0])];
static char s_addon_names[sizeof(addons) / sizeof(addons[0])][MAX_QPATH];

static void StartAddon(const addon_entry_t* addon)
{
	cl.servercount = -1;
	M_ForceMenuOff();

	Cbuf_AddText(va(
		"loading ; killserver ; wait ; game %s ; wait ; deathmatch 0 ; coop %i ; maxclients %i ; %s\n",
		addon->game_dir,
		addon->coop ? 1 : 0,
		addon->coop ? 4 : 1,
		addon->start_cmd));

	cls.key_dest = key_game;
}

static void AddonFunc(void* data)
{
	const menucommon_t* item = data;
	const int index = item->localdata[0];

	if (index >= 0 && index < (int)(sizeof(addons) / sizeof(addons[0])))
		StartAddon(&addons[index]);
}

static void Addons_MenuInit(void)
{
	s_addons_menu.nitems = 0;

	for (int i = 0; i < (int)(sizeof(addons) / sizeof(addons[0])); i++)
	{
		menuaction_t* action = &s_addon_actions[i];

		Com_sprintf(s_addon_names[i], sizeof(s_addon_names[i]), "\x02%s", addons[i].title);
		action->generic.type = MTYPE_ACTION;
		action->generic.flags = QMF_LEFT_JUSTIFY | QMF_SELECT_SOUND;
		action->generic.x = 0;
		action->generic.y = i * 18;
		action->generic.name = s_addon_names[i];
		action->generic.width = re.BF_Strlen(s_addon_names[i]);
		action->generic.callback = AddonFunc;
		action->generic.localdata[0] = i;

		Menu_AddItem(&s_addons_menu, action);
	}

	Menu_Center(&s_addons_menu);
}

static void Addons_MenuDraw(void)
{
	char title[MAX_QPATH];

	Menu_DrawBG("book/back/b_conback8.bk", cls.m_menuscale);

	if (cls.m_menualpha == 0.0f)
		return;

	Com_sprintf(title, sizeof(title), "\x03%s", "Game Add-ons");
	const int x = M_GetMenuLabelX(re.BF_Strlen(title));
	const int y = M_GetMenuOffsetY(&s_addons_menu);
	re.DrawBigFont(x, y, title, cls.m_menualpha);

	s_addons_menu.x = M_GetMenuLabelX(s_addons_menu.width);
	Menu_AdjustCursor(&s_addons_menu, 1);
	Menu_Draw(&s_addons_menu);
}

static const char* Addons_MenuKey(const int key)
{
	return Default_MenuKey(&s_addons_menu, key);
}

void M_Menu_Addons_f(void)
{
	Addons_MenuInit();
	M_PushMenu(Addons_MenuDraw, Addons_MenuKey);
}
