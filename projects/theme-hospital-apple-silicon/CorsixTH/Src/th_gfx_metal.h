#ifndef CORSIX_TH_TH_GFX_METAL_H_
#define CORSIX_TH_TH_GFX_METAL_H_

#include <SDL.h>

#include <cstdint>
#include <memory>
#include <vector>

struct metal_creation_params {
  int width;
  int height;
  bool fullscreen;
  int min_width;
  int min_height;
};

enum class metal_pixel_format {
  BGRA8Unorm = 0,  // CAMetalLayer and render-target texture format.
  RGBA8Unorm,      // CPU palette pixels are stored in byte order R, G, B, A.
  R8Unorm,
};

class metal_renderer;

//! A native Metal texture mirroring a CPU pixel buffer.
class metal_texture {
 public:
  metal_texture(class metal_renderer* renderer, int width, int height,
                metal_pixel_format format, const void* data);
  ~metal_texture();

  metal_texture(const metal_texture&) = delete;
  metal_texture& operator=(const metal_texture&) = delete;

  int width() const { return width_; }
  int height() const { return height_; }
  metal_pixel_format format() const { return format_; }

  // Returns the underlying id<MTLTexture> as an opaque void*.
  // Caller must NOT release this handle; it is owned by the metal_texture.
  void* texture_handle() const { return texture_; }

 private:
  // Internal: replace the texture handle (used when wrapping a pre-existing
  // texture, e.g., a render target).
  void set_texture_handle(void* handle) { texture_ = handle; }
  void* get_texture_handle() const { return texture_; }

  friend class metal_renderer;

  class metal_renderer* renderer_;
  int width_;
  int height_;
  metal_pixel_format format_;
  void* texture_;  // id<MTLTexture>, owned via CFBridgingRetain
};

class metal_renderer {
 public:
  metal_renderer(SDL_Window* window, const metal_creation_params& params);
  ~metal_renderer();

  metal_renderer(const metal_renderer&) = delete;
  metal_renderer& operator=(const metal_renderer&) = delete;

  bool valid() const;

  const char* device_name() const;

  // Returns the underlying id<MTLDevice> as an opaque void*.
  // For use by metal_texture and other native code.
  void* device_handle() const { return device_; }

  // Returns the underlying id<MTLCommandQueue> as an opaque void*.
  void* command_queue_handle() const { return command_queue_; }

  bool start_frame();
  bool end_frame(std::vector<uint8_t>* bgra_pixels = nullptr,
                 int* capture_width = nullptr, int* capture_height = nullptr);

  // Begin a render pass to a custom render target texture.
  // The previous render pass (if any) is ended before this.
  // Pass nullptr to render to the main drawable.
  bool begin_render_pass(metal_texture* target, bool clear = true);
  void end_render_pass();

  // Create an off-screen render target texture. The texture has both
  // ShaderRead and RenderTarget usage, so it can be drawn to and sampled
  // from. Caller owns the returned metal_texture.
  std::unique_ptr<metal_texture> create_render_target(int width, int height);

  // Draw the contents of a texture (typically a render target) to the
  // current render target. This is a "blit" or composite operation.
  // For now, draws full-texel-to-full-target.
  void blit_texture(metal_texture* source);

  void on_resize(int width, int height);

  // Apply or clear the current clip rectangle for native Metal draws.
  // The rect is in the current render-target coordinate space.
  void set_clip_rect(const SDL_Rect* rect);

  int width() const { return width_; }
  int height() const { return height_; }

  // Create a native Metal texture from CPU pixel data.
  // Caller owns the returned metal_texture.
  std::unique_ptr<metal_texture> create_texture(
      int width, int height, metal_pixel_format format, const void* data);

  // Draw a sprite. The dst_rect is in pixel coordinates (top-left origin).
  // Pass a null src_rect to draw the full texture.
  // flags: bitfield of thdf_* values for flips/alpha modulation (M20).
  void draw_sprite(metal_texture* tex, const SDL_Rect* src_rect,
                   const SDL_FRect* dst_rect, int flags = 0);

  // Draw a solid-color rectangle (M17). r, g, b, a are in [0, 1].
  void draw_color_rect(const SDL_FRect* rect, float r, float g, float b,
                       float a);

  // Draw a solid-color line (M17). r, g, b, a are in [0, 1].
  void draw_color_line(float x1, float y1, float x2, float y2, float r,
                      float g, float b, float a);

  // Tracks created textures for diagnostics.
  size_t texture_count() const { return live_textures_; }
  size_t total_textures_created() const { return total_textures_created_; }

 private:
  SDL_Window* window_;
  int width_;
  int height_;
  int min_width_;
  int min_height_;
  int drawable_width_;
  int drawable_height_;
  double drawable_scale_x_{1.0};
  double drawable_scale_y_{1.0};

  void* device_;             // id<MTLDevice>
  void* command_queue_;      // id<MTLCommandQueue>
  void* layer_;              // CAMetalLayer* (deferred)
  void* current_drawable_;   // id<CAMetalDrawable>
  void* current_cmd_buf_;    // id<MTLCommandBuffer>
  void* current_enc_;        // id<MTLRenderCommandEncoder>
  void* current_target_;     // metal_texture* for non-drawable target (M16)
  int current_target_width_;
  int current_target_height_;

  void* pipeline_state_;     // id<MTLRenderPipelineState> (sprite)
  void* color_pipeline_state_;  // id<MTLRenderPipelineState> (color-only)
  void* sampler_state_;      // id<MTLSamplerState>

  void* vertex_buffer_;     // id<MTLBuffer> (M19: persistent buffer pool)
  size_t vertex_buffer_size_{1 << 20};  // 1MB pool
  size_t vertex_buffer_used_{0};         // Current write offset

  size_t live_textures_{0};
  size_t total_textures_created_{0};

  bool has_clip_rect_{false};
  int clip_x_{0};
  int clip_y_{0};
  int clip_w_{0};
  int clip_h_{0};

  // M19: Write data to the persistent buffer. Returns the offset where the
  // data was written. Returns SIZE_MAX on overflow (caller should fall back
  // to allocating a new buffer).
  size_t write_to_vertex_buffer(const void* data, size_t size);

  bool setup_layer();
  void update_drawable_size();
  bool init_pipeline();
  void apply_clip_rect();
};

#endif
