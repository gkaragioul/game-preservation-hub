//
// gl3_SDL.c
//
// OpenGL 4.6 Core Profile SDL context management.
//

#include "gl3_SDL.h"
#include "gl3_Local.h"
#include <SDL3/SDL.h>

static SDL_Window* window = NULL;
static SDL_GLContext context = NULL;

static float RI_GetDisplayRefreshRate(void)
{
	SDL_DisplayID display = SDL_GetDisplayForWindow(window);
	if (display == 0)
		display = SDL_GetPrimaryDisplay();

	const SDL_DisplayMode* mode = SDL_GetCurrentDisplayMode(display);
	if (mode == NULL || mode->refresh_rate <= 0.0f)
		mode = SDL_GetDesktopDisplayMode(display);

	if (mode == NULL || mode->refresh_rate <= 0.0f)
		return 0.0f;

	return mode->refresh_rate;
}

static int RI_GetGraphicsProfile(void)
{
	cvar_t* r_graphics_profile = ri.Cvar_Get("r_graphics_profile", "1", CVAR_ARCHIVE);
	cvar_t* r_graphics_profile_version = ri.Cvar_Get("r_graphics_profile_version", "0", CVAR_ARCHIVE);

	if ((int)r_graphics_profile_version->value < 2)
	{
		const int old_profile = (int)r_graphics_profile->value;
		const int new_profile = (old_profile == 0 ? 1 : 0);

		ri.Cvar_SetValue("r_graphics_profile", (float)new_profile);
		ri.Cvar_SetValue("r_graphics_profile_version", 2.0f);
		return new_profile;
	}

	return ClampI((int)r_graphics_profile->value, 0, 1);
}

static float RI_ResolveFrameCap(const float refresh_rate, const int graphics_profile)
{
	const cvar_t* r_custom_maxfps = ri.Cvar_Get("r_custom_maxfps", "0", CVAR_ARCHIVE);
	const float display_cap = Clamp(refresh_rate, 30.0f, 240.0f);
	const float custom_cap = Clamp(r_custom_maxfps->value, 0.0f, 240.0f);

	if (custom_cap >= 30.0f)
		return min(custom_cap, display_cap);

	if (graphics_profile == 1)
		return min(72.0f, display_cap);

	return display_cap;
}

static void RI_SetDisplayRefreshDefaults(void)
{
	float refresh_rate = RI_GetDisplayRefreshRate();
	if (refresh_rate < 30.0f)
		refresh_rate = 60.0f;

	const int graphics_profile = RI_GetGraphicsProfile();
	const float render_fps = RI_ResolveFrameCap(refresh_rate, graphics_profile);
	const float client_fps = render_fps;

	ri.Cvar_SetValue("vid_display_refresh", refresh_rate);
	ri.Cvar_SetValue("vid_maxfps", render_fps);
	ri.Cvar_SetValue("cl_maxfps", client_fps);
	ri.Con_Printf(PRINT_ALL, "Display refresh %.1f Hz: profile %i, vid_maxfps %.0f, cl_maxfps %.0f\n", refresh_rate, graphics_profile, render_fps, client_fps);
}

// Swaps the buffers and shows the next frame.
void RI_EndFrame(void)
{
	SDL_GL_SwapWindow(window);
}

// Returns the flags used at the SDL window creation.
// In case of error -1 is returned.
int RI_PrepareForWindow(void)
{
	// Request the highest core profile available on the target platform.
	SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 4);
#ifdef __MACOS_NATIVE__
	SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 1);
#else
	SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 6);
#endif
	SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_CORE);

#ifdef _DEBUG
	SDL_GL_SetAttribute(SDL_GL_CONTEXT_FLAGS, SDL_GL_CONTEXT_DEBUG_FLAG);
#endif

	// Set GL context attributes bound to the window.
	SDL_GL_SetAttribute(SDL_GL_RED_SIZE, 8);
	SDL_GL_SetAttribute(SDL_GL_GREEN_SIZE, 8);
	SDL_GL_SetAttribute(SDL_GL_BLUE_SIZE, 8);
	SDL_GL_SetAttribute(SDL_GL_DEPTH_SIZE, 24);
	SDL_GL_SetAttribute(SDL_GL_STENCIL_SIZE, 8);
	SDL_GL_SetAttribute(SDL_GL_DOUBLEBUFFER, 1);
	SDL_GL_SetAttribute(SDL_GL_ACCELERATED_VISUAL, 1);

	if ((int)r_antialiasing->value == 1) // MSAA
	{
		SDL_GL_SetAttribute(SDL_GL_MULTISAMPLEBUFFERS, 1);
		SDL_GL_SetAttribute(SDL_GL_MULTISAMPLESAMPLES, 4);
		ri.Con_Printf(PRINT_ALL, "Requested MSAA 4x\n");
	}
	else
	{
		SDL_GL_SetAttribute(SDL_GL_MULTISAMPLEBUFFERS, 0);
		SDL_GL_SetAttribute(SDL_GL_MULTISAMPLESAMPLES, 0);
	}

	return SDL_WINDOW_OPENGL;
}

// Enables or disables the vsync.
void R_SetVsync(void)
{
	int vsync = 0;

	if (r_vsync->value == 1.0f)
		vsync = 1;
	else if (r_vsync->value == 2.0f)
		vsync = -1;

	if (!SDL_GL_SetSwapInterval(vsync) && vsync == -1)
	{
		ri.Con_Printf(PRINT_ALL, "Failed to set adaptive VSync, reverting to normal VSync.\n");
		SDL_GL_SetSwapInterval(1);
	}

	if (!SDL_GL_GetSwapInterval(&vsync))
		ri.Con_Printf(PRINT_ALL, "Failed to get VSync state, assuming no VSync.\n");
}

// Initializes the OpenGL 4.6 Core context.
qboolean RI_InitContext(void* win)
{
	if (win == NULL)
	{
		ri.Sys_Error(ERR_FATAL, "RI_InitContext() called with NULL argument!");
		return false;
	}

	window = (SDL_Window*)win;

	// Initialize GL context.
	context = SDL_GL_CreateContext(window);

	if (context == NULL)
	{
		ri.Con_Printf(PRINT_ALL, "RI_InitContext(): failed to create OpenGL context: %s\n", SDL_GetError());
		window = NULL;

		return false;
	}

	// Load OpenGL function pointers through GLAD.
	if (!gladLoadGLLoader((GLADloadproc)SDL_GL_GetProcAddress))
	{
		ri.Con_Printf(PRINT_ALL, "RI_InitContext(): failed to initialize OpenGL via GLAD\n");
		return false;
	}

	// Check OpenGL version.
#ifdef __MACOS_NATIVE__
	if (!GLAD_GL_VERSION_4_1)
	{
		ri.Con_Printf(PRINT_ALL, "RI_InitContext(): unsupported OpenGL version. Expected 4.1, got %i.%i!\n", GLVersion.major, GLVersion.minor);
		return false;
	}
#else
	if (!GLAD_GL_VERSION_4_6)
	{
		ri.Con_Printf(PRINT_ALL, "RI_InitContext(): unsupported OpenGL version. Expected 4.6, got %i.%i!\n", GLVersion.major, GLVersion.minor);
		return false;
	}
#endif

	RI_SetDisplayRefreshDefaults();
	R_SetVsync();
	vid_gamma->modified = true; // Force R_UpdateGamma() call in R_BeginFrame().

	return true;
}

// Shuts the GL context down.
void RI_ShutdownContext(void)
{
	if (window != NULL && context != NULL)
	{
		SDL_GL_DestroyContext(context);
		context = NULL;
	}
}
