//
// menu_video.c
//
// Copyright 1998 Raven Software
//

#include "client.h"
#include "vid_dll.h"
#include "menu_video.h"

cvar_t* m_banner_video;

cvar_t* m_item_driver; // "Renderer"
cvar_t* m_item_vidmode; // "Video resolution"
cvar_t* m_item_target_fps; //mxd. "Target FPS"
cvar_t* m_item_gamma;
cvar_t* m_item_brightness;
cvar_t* m_item_contrast;
cvar_t* m_item_minlight; // YQ2
cvar_t* m_item_detail;
cvar_t* m_item_graphics_profile;
cvar_t* m_item_custom_max_fps;
cvar_t* m_item_hd_mode;
cvar_t* m_item_antialiasing;

static float m_gamma;
static float m_brightness;
static float m_contrast;
static float m_minlight; //mxd. gl_minlight when entering menu.
static float m_antialiasing; //mxd. r_antialiasing when entering menu.
static cvar_t* m_graphics_profile;
static cvar_t* m_graphics_profile_version;
static cvar_t* m_custom_maxfps;

static menuframework_t s_video_menu;

static menulist_t s_ref_list;
static menulist_t s_mode_list;
static menulist_t s_graphics_profile_list;
static menufield_t s_custom_maxfps_field;
static menuslider_t s_gamma_slider;
static menuslider_t s_brightness_slider;
static menuslider_t s_contrast_slider;

static const char* ref_list_titles[MAX_REFLIBS + 1];
static int initial_reflib_index; // vid_ref index when entering menu.

#define MAX_DISPLAYED_VIDMODES	64 //mxd. This is kinda ugly, since vid_modes array itself is dynamically allocated...
static const char* vid_mode_titles[MAX_DISPLAYED_VIDMODES + 1];
static int initial_vid_mode; // vid_mode when entering menu.

#define FULL_POWER_TARGET_FPS	120.0f

#pragma region ========================== MENU ITEM CALLBACKS ==========================

typedef struct graphics_profile_s
{
	const char* name;
	const char* benefit1;
	const char* benefit2;
	float hd_textures;
	float antialiasing;
	float bloom;
	float ssao;
	float shadows;
	float reflections;
	float detail;
	float vsync;
} graphics_profile_t;

static const graphics_profile_t graphics_profiles[] =
{
	{ "Full Power", "Best for plugged-in Macs and fast displays.", "Aims for 120 FPS with richer effects.", 1.0f, 0.0f, 1.0f, 0.0f, 0.0f, 0.0f, 2.0f, 0.0f },
	{ "Power Saver", "Best for MacBooks on battery or cooler play.", "Locks to 60 FPS and avoids costly extras.", 1.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, 1.0f }
};

static int NormalizeGraphicsProfileIndex(const int profile_index)
{
	return ClampI(profile_index, 0, (int)ARRAY_SIZE(graphics_profiles) - 1);
}

static void MigrateOldGraphicsProfile(void)
{
	if ((int)m_graphics_profile_version->value >= 2)
		return;

	const int old_profile = (int)m_graphics_profile->value;
	const int new_profile = (old_profile == 0 ? 1 : 0);

	Cvar_SetValue("r_graphics_profile", (float)new_profile);
	Cvar_SetValue("r_graphics_profile_version", 2.0f);
}

static float GetDisplayRefreshForFrameCap(void)
{
	const float refresh_rate = Cvar_VariableValue("vid_display_refresh");

	if (refresh_rate >= 30.0f)
		return refresh_rate;

	return Clamp(vid_maxfps->value, 30.0f, 240.0f);
}

static float GetCustomMaxFPS(void)
{
	if (s_custom_maxfps_field.buffer[0] == 0)
		return 0.0f;

	return Clamp((float)atoi(s_custom_maxfps_field.buffer), 30.0f, 240.0f);
}

static float ResolveGraphicsProfileFPS(const int profile_index)
{
	const float display_cap = Clamp(GetDisplayRefreshForFrameCap(), 30.0f, 240.0f);
	const float custom_cap = GetCustomMaxFPS();

	if (custom_cap >= 30.0f)
		return min(custom_cap, display_cap);

	if (NormalizeGraphicsProfileIndex(profile_index) == 1)
		return min(60.0f, display_cap);

	return min(FULL_POWER_TARGET_FPS, display_cap);
}

static void ApplyGraphicsFrameCap(const int profile_index)
{
	const float frame_cap = ResolveGraphicsProfileFPS(profile_index);

	Cvar_SetValue("vid_maxfps", frame_cap);
	Cvar_SetValue("cl_maxfps", frame_cap);
	Cvar_SetValue("scr_adaptive_fps", 0.0f);
}

static void ApplyGraphicsProfile(const int profile_index)
{
	const int index = NormalizeGraphicsProfileIndex(profile_index);
	const graphics_profile_t* profile = &graphics_profiles[index];

	if ((int)m_antialiasing != (int)profile->antialiasing)
		vid_restart_required = true;

	Cvar_SetValue("r_graphics_profile", (float)index);
	ApplyGraphicsFrameCap(index);
	Cvar_SetValue("r_hd_textures", profile->hd_textures);
	Cvar_SetValue("r_antialiasing", profile->antialiasing);
	Cvar_SetValue("r_bloom", profile->bloom);
	Cvar_SetValue("r_ssao", profile->ssao);
	Cvar_SetValue("r_shadows", profile->shadows);
	Cvar_SetValue("r_reflections", profile->reflections);
	Cvar_SetValue("r_detail", profile->detail);
	Cvar_SetValue("r_vsync", profile->vsync);
}

static void UpdateGraphicsProfileFunc(void* self)
{
	const menulist_t* list = (menulist_t*)self;
	ApplyGraphicsProfile(list->curvalue);
}

static void UpdateCustomMaxFPSFunc(void* self)
{
	menufield_t* field = (menufield_t*)self;
	const float custom_fps = (field->buffer[0] == 0 ? 0.0f : Clamp((float)atoi(field->buffer), 30.0f, 240.0f));

	Cvar_SetValue("r_custom_maxfps", custom_fps);

	if (custom_fps > 0.0f)
	{
		Com_sprintf(field->buffer, sizeof(field->buffer), "%.0f", custom_fps);
		field->cursor = (int)strlen(field->buffer);
		field->visible_offset = 0;
	}

	ApplyGraphicsFrameCap(s_graphics_profile_list.curvalue);
}

static void UpdateGammaFunc(void* self) // H2
{
	const menuslider_t* slider = (menuslider_t*)self;
	Cvar_SetValue("vid_gamma", (16.0f - slider->curvalue) / 16.0f);
}

static void UpdateBrightnessFunc(void* self)
{
	const menuslider_t* slider = (menuslider_t*)self;
	Cvar_SetValue("vid_brightness", slider->curvalue / 16.0f);
}

static void UpdateContrastFunc(void* self) // H2
{
	const menuslider_t* slider = (menuslider_t*)self;
	Cvar_SetValue("vid_contrast", slider->curvalue / 16.0f);
}

static void ApplyChanges(const qboolean close_menu) //mxd. +close_menu arg.
{
	UpdateCustomMaxFPSFunc(&s_custom_maxfps_field);

	if (initial_reflib_index != s_ref_list.curvalue && s_ref_list.curvalue >= 0 && s_ref_list.curvalue < num_reflib_infos)
	{
		Cvar_Set("vid_ref", reflib_infos[s_ref_list.curvalue].id);
		initial_reflib_index = s_ref_list.curvalue;
		vid_restart_required = true;
	}

	if (initial_vid_mode != s_mode_list.curvalue && s_mode_list.curvalue >= 0 && s_mode_list.curvalue < min(MAX_DISPLAYED_VIDMODES, num_vid_modes))
	{
		Cvar_SetValue("vid_mode", (float)s_mode_list.curvalue);
		initial_vid_mode = s_mode_list.curvalue;
		vid_restart_required = true;
	}

	if ((int)m_minlight != (int)m_gl_minlight->value) // YQ2
		vid_restart_required = true;

	if (vid_restart_required)
	{
		M_ForceMenuOff();
		return;
	}

	if (close_menu)
	{
		//mxd. These don't require vid_restart, but we still need to update ALL textures in RI_BeginFrame() AFTER menu is closed.
		// (only it_pic/it_sky textures are updated by R_GammaAffect() when menus are open (for performance reasons)).
		if (m_gamma != vid_gamma->value || m_brightness != vid_brightness->value || m_contrast != vid_contrast->value)
			Cvar_SetValue("vid_textures_refresh_required", 1.0f);

		M_PopMenu();
	}
}

#pragma endregion

void VID_PreMenuInit(void)
{
	initial_reflib_index = 0;
	s_ref_list.curvalue = 0;

	//mxd. Refresher library titles.
	for (int i = 0; i < num_reflib_infos; i++)
	{
		ref_list_titles[i] = reflib_infos[i].title;

		if (Q_stricmp(vid_ref->string, reflib_infos[i].id) == 0)
		{
			initial_reflib_index = i;
			s_ref_list.curvalue = i;
		}
	}

	ref_list_titles[num_reflib_infos] = NULL;

	//mxd. Window resolution labels.
	const int displayed_vid_modes = min(MAX_DISPLAYED_VIDMODES, num_vid_modes);

	for (int i = 0; i < displayed_vid_modes; i++)
		vid_mode_titles[i] = vid_modes[i].description;

	vid_mode_titles[displayed_vid_modes] = NULL;

	if (vid_mode == NULL)
	{
		vid_mode = Cvar_Get("vid_mode", "0", 0);
		vid_restart_required = true;
	}

	initial_vid_mode = (int)vid_mode->value; //mxd

	if (scr_viewsize == NULL)
		scr_viewsize = Cvar_Get("viewsize", "100", CVAR_ARCHIVE);
}

static void VID_MenuInit(void)
{
		static const char* graphics_profile_names[] = { "Full Power", "Power Saver", NULL };

		static char name_driver[MAX_QPATH];
		static char name_vidmode[MAX_QPATH];
		static char name_graphics_profile[MAX_QPATH];
		static char name_custom_maxfps[MAX_QPATH];
		static char name_gamma[MAX_QPATH];
		static char name_brightness[MAX_QPATH];
		static char name_contrast[MAX_QPATH];

		VID_PreMenuInit();
		m_graphics_profile = Cvar_Get("r_graphics_profile", "1", CVAR_ARCHIVE);
		m_graphics_profile_version = Cvar_Get("r_graphics_profile_version", "0", CVAR_ARCHIVE);
		m_custom_maxfps = Cvar_Get("r_custom_maxfps", "0", CVAR_ARCHIVE);
		Cvar_Get("vid_display_refresh", "0", 0);
		MigrateOldGraphicsProfile();

		m_gamma = Cvar_VariableValue("vid_gamma");
		m_brightness = Cvar_VariableValue("vid_brightness");
	m_contrast = Cvar_VariableValue("vid_contrast");
	m_minlight = Cvar_VariableValue("gl_minlight"); // YQ2
	m_antialiasing = Cvar_VariableValue("r_antialiasing");

		s_video_menu.nitems = 0;

		Cvar_SetValue("r_detail", Clamp(m_r_detail->value, 0.0f, 3.0f));
		Cvar_SetValue("gl_minlight", Clamp(m_gl_minlight->value, 0.0f, 32.0f)); //mxd
		Cvar_SetValue("vid_maxfps", Clamp(vid_maxfps->value, 30.0f, 240.0f)); //mxd
		Cvar_SetValue("r_antialiasing", Clamp(Cvar_VariableValue("r_antialiasing"), 0.0f, 2.0f));
		Cvar_SetValue("r_custom_maxfps", Clamp(m_custom_maxfps->value, 0.0f, 240.0f));

		Com_sprintf(name_graphics_profile, sizeof(name_graphics_profile), "\x02%s", m_item_graphics_profile->string);
		s_graphics_profile_list.generic.type = MTYPE_SPINCONTROL;
		s_graphics_profile_list.generic.x = 0;
		s_graphics_profile_list.generic.y = 0;
		s_graphics_profile_list.generic.name = name_graphics_profile;
		s_graphics_profile_list.generic.width = re.BF_Strlen(name_graphics_profile);
		s_graphics_profile_list.generic.flags = QMF_SINGLELINE;
		s_graphics_profile_list.generic.callback = UpdateGraphicsProfileFunc;
		s_graphics_profile_list.curvalue = NormalizeGraphicsProfileIndex((int)m_graphics_profile->value);
		s_graphics_profile_list.itemnames = graphics_profile_names;

		Com_sprintf(name_custom_maxfps, sizeof(name_custom_maxfps), "\x02%s", m_item_custom_max_fps->string);
		s_custom_maxfps_field.generic.type = MTYPE_FIELD;
		s_custom_maxfps_field.generic.flags = QMF_NUMBERSONLY | QMF_SELECT_SOUND;
		s_custom_maxfps_field.generic.x = 0;
		s_custom_maxfps_field.generic.y = 40;
		s_custom_maxfps_field.generic.name = name_custom_maxfps;
		s_custom_maxfps_field.generic.width = re.BF_Strlen(name_custom_maxfps);
		s_custom_maxfps_field.generic.callback = UpdateCustomMaxFPSFunc;
		s_custom_maxfps_field.cursor = 0;
		s_custom_maxfps_field.length = 4;
		s_custom_maxfps_field.visible_length = 3;
		s_custom_maxfps_field.visible_offset = 0;
		s_custom_maxfps_field.buffer[0] = 0;

		if (m_custom_maxfps->value >= 1.0f)
		{
			Com_sprintf(s_custom_maxfps_field.buffer, sizeof(s_custom_maxfps_field.buffer), "%.0f", Clamp(m_custom_maxfps->value, 30.0f, 240.0f));
			s_custom_maxfps_field.cursor = (int)strlen(s_custom_maxfps_field.buffer);
		}

		Com_sprintf(name_driver, sizeof(name_driver), "\x02%s", m_item_driver->string);
		s_ref_list.generic.type = MTYPE_SPINCONTROL;
		s_ref_list.generic.x = 0;
		s_ref_list.generic.y = 100;
		s_ref_list.generic.name = name_driver;
		s_ref_list.generic.width = re.BF_Strlen(name_driver);
		s_ref_list.curvalue = initial_reflib_index;
		s_ref_list.itemnames = ref_list_titles;
	
		Com_sprintf(name_vidmode, sizeof(name_vidmode), "\x02%s", m_item_vidmode->string);
		s_mode_list.generic.type = MTYPE_SPINCONTROL;
		s_mode_list.generic.x = 0;
		s_mode_list.generic.y = 140;
		s_mode_list.generic.name = name_vidmode;
		s_mode_list.generic.width = re.BF_Strlen(name_vidmode);
		s_mode_list.curvalue = initial_vid_mode;
		s_mode_list.itemnames = vid_mode_titles;
	
		Com_sprintf(name_gamma, sizeof(name_gamma), "\x02%s", m_item_gamma->string);
		s_gamma_slider.generic.type = MTYPE_SLIDER;
		s_gamma_slider.generic.flags = QMF_SELECT_SOUND;
		s_gamma_slider.generic.x = 0;
		s_gamma_slider.generic.y = 180;
		s_gamma_slider.generic.name = name_gamma;
		s_gamma_slider.generic.width = re.BF_Strlen(name_gamma);
		s_gamma_slider.generic.callback = UpdateGammaFunc;
		s_gamma_slider.minvalue = 0.0f;
	s_gamma_slider.maxvalue = 16.0f;
	s_gamma_slider.curvalue = 16.0f - vid_gamma->value * 16.0f;

		Com_sprintf(name_brightness, sizeof(name_brightness), "\x02%s", m_item_brightness->string);
			s_brightness_slider.generic.type = MTYPE_SLIDER;
			s_brightness_slider.generic.flags = QMF_SELECT_SOUND;
			s_brightness_slider.generic.x = 0;
			s_brightness_slider.generic.y = 220;
		s_brightness_slider.generic.name = name_brightness;
		s_brightness_slider.generic.width = re.BF_Strlen(name_brightness);
		s_brightness_slider.generic.callback = UpdateBrightnessFunc;
		s_brightness_slider.minvalue = 0.0f;
	s_brightness_slider.maxvalue = 16.0f;
	s_brightness_slider.curvalue = vid_brightness->value * 16.0f;

		Com_sprintf(name_contrast, sizeof(name_contrast), "\x02%s", m_item_contrast->string);
			s_contrast_slider.generic.type = MTYPE_SLIDER;
			s_contrast_slider.generic.flags = QMF_SELECT_SOUND;
			s_contrast_slider.generic.x = 0;
			s_contrast_slider.generic.y = 260;
		s_contrast_slider.generic.name = name_contrast;
		s_contrast_slider.generic.width = re.BF_Strlen(name_contrast);
		s_contrast_slider.generic.callback = UpdateContrastFunc;
		s_contrast_slider.minvalue = 1.6f;
	s_contrast_slider.maxvalue = 14.4f;
	s_contrast_slider.curvalue = vid_contrast->value * 16.0f;

			Menu_AddItem(&s_video_menu, &s_graphics_profile_list);
			Menu_AddItem(&s_video_menu, &s_custom_maxfps_field);
			Menu_AddItem(&s_video_menu, &s_ref_list);
			Menu_AddItem(&s_video_menu, &s_mode_list);
			Menu_AddItem(&s_video_menu, &s_gamma_slider);
			Menu_AddItem(&s_video_menu, &s_brightness_slider);
			Menu_AddItem(&s_video_menu, &s_contrast_slider);

		Menu_Center(&s_video_menu);
	}

static void VID_DrawProfileBenefit(void)
{
	const graphics_profile_t* profile = &graphics_profiles[ClampI(s_graphics_profile_list.curvalue, 0, (int)ARRAY_SIZE(graphics_profiles) - 1)];
	const float alpha = cls.m_menualpha;
	paletteRGBA_t color = TextPalette[P_MENUFIELD];
	char cap_text[160];
	color.a = (byte)(alpha * 210.0f);

	const int center_x = (M_GetMenuLabelX(0) * ui_screen_width / DEF_WIDTH) + ui_screen_offset_x;
	const int y1 = (s_video_menu.y + 300) * viddef.height / DEF_HEIGHT;
	const int y2 = y1 + ui_line_height;
	const int y3 = y2 + ui_line_height;
	const int x1 = center_x - ((int)strlen(profile->benefit1) * ui_char_size) / 2;
	const int x2 = center_x - ((int)strlen(profile->benefit2) * ui_char_size) / 2;

	DrawString(x1, y1, profile->benefit1, color, -1);
	DrawString(x2, y2, profile->benefit2, color, -1);

	if (GetCustomMaxFPS() >= 30.0f)
		Com_sprintf(cap_text, sizeof(cap_text), "Custom FPS overrides this mode: %.0f FPS cap", ResolveGraphicsProfileFPS(s_graphics_profile_list.curvalue));
	else
		Com_sprintf(cap_text, sizeof(cap_text), "Blank Custom FPS uses this mode: %.0f FPS cap", ResolveGraphicsProfileFPS(s_graphics_profile_list.curvalue));

	const int x3 = center_x - ((int)strlen(cap_text) * ui_char_size) / 2;
	DrawString(x3, y3, cap_text, color, -1);
}

static void VID_MenuDraw(void)
{
	char title[MAX_QPATH];

	// Draw menu BG.
	Menu_DrawBG("book/back/b_conback8.bk", cls.m_menuscale);

	if (cls.m_menualpha == 0.0f)
		return;

	// Draw menu title.
	Com_sprintf(title, sizeof(title), "\x03%s", m_banner_video->string);
	const int x = M_GetMenuLabelX(re.BF_Strlen(title));
	const int y = M_GetMenuOffsetY(&s_video_menu);
	re.DrawBigFont(x, y, title, cls.m_menualpha);

	s_video_menu.x = M_GetMenuLabelX(s_video_menu.width);
	Menu_AdjustCursor(&s_video_menu, 1);
	Menu_Draw(&s_video_menu);
	VID_DrawProfileBenefit();
}

static const char* VID_MenuKey(const int key)
{
	if (cls.m_menustate != MS_OPENED)
		return NULL;

	menucommon_t* item = Menu_ItemAtCursor(&s_video_menu);
	if (item != NULL && item->type == MTYPE_FIELD && Field_Key((menufield_t*)item, key))
		return NULL;

	switch (key)
	{
		case K_ENTER:
		case K_KP_ENTER:
			if (item != NULL && item->type == MTYPE_FIELD && Menu_SelectItem(&s_video_menu))
				return SND_MENU_ENTER;

			ApplyChanges(false);
			return SND_MENU_ENTER;

		case K_ESCAPE:
			ApplyChanges(true);
			return SND_MENU_CLOSE;

		case K_UPARROW:
		case K_KP_UPARROW:
		case K_AUX8:	// D-pad up
		case 'w':
		case 'W':
			s_video_menu.cursor--;
			Menu_AdjustCursor(&s_video_menu, -1);
			return SND_MENU_SELECT;

		case K_DOWNARROW:
		case K_KP_DOWNARROW:
		case K_AUX9:	// D-pad down
		case 's':
		case 'S':
			s_video_menu.cursor++;
			Menu_AdjustCursor(&s_video_menu, 1);
			return SND_MENU_SELECT;

		case K_LEFTARROW:
		case K_KP_LEFTARROW:
		case K_AUX10:	// D-pad left
		case 'a':
		case 'A':
			//mxd. Original logic calls se.StopAllSounds_Sounding() here - no longer needed.
			return (Menu_SlideItem(&s_video_menu, -1) ? SND_MENU_TOGGLE : NULL); //mxd. Add sound.

		case K_RIGHTARROW:
		case K_KP_RIGHTARROW:
		case K_AUX11:	// D-pad right
		case 'd':
		case 'D':
			//mxd. Original logic calls se.StopAllSounds_Sounding() here - no longer needed.
			return (Menu_SlideItem(&s_video_menu, 1) ? SND_MENU_TOGGLE : NULL); //mxd. Add sound.

		default:
			break;
	}

	return NULL;
}

// Q2 counterpart
void M_Menu_Video_f(void)
{
	VID_MenuInit();
	M_PushMenu(VID_MenuDraw, VID_MenuKey);
}
