#include "th_gfx_metal.h"

#import <Metal/Metal.h>
#import <QuartzCore/CAMetalLayer.h>
#import <SDL_syswm.h>

#import <Cocoa/Cocoa.h>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <os/signpost.h>

// M21: Signpost log for GPU profiling (visible in Instruments.app)
static os_log_t metal_signpost_log(void) {
  static dispatch_once_t once;
  static os_log_t log;
  dispatch_once(&once, ^{
    log = os_log_create("org.corsixth.corsixth.metal", "render");
  });
  return log;
}

namespace {

// Basic sprite shader: a textured quad with orthographic projection.
// Each vertex has position (pixel space) and texcoord (UV space, 0..1).
// M20: added per-draw alpha multiplier for sprite alpha flags.
NSString* const kSpriteShaderSource = @R"msl(
#include <metal_stdlib>
using namespace metal;

struct VertexIn {
    float2 position;
    float2 texcoord;
};

struct VertexOut {
    float4 position [[position]];
    float2 texcoord;
};

struct DrawParams {
    float4x4 projection;
    float alpha;
};

vertex VertexOut sprite_vertex(uint vid [[vertex_id]],
                                constant VertexIn* vertices [[buffer(0)]],
                                constant DrawParams& params [[buffer(1)]]) {
    VertexOut out;
    out.position = params.projection * float4(vertices[vid].position, 0.0, 1.0);
    out.texcoord = vertices[vid].texcoord;
    return out;
}

fragment float4 sprite_fragment(VertexOut in [[stage_in]],
                                texture2d<float> tex [[texture(0)]],
                                sampler smp [[sampler(0)]],
                                constant DrawParams& params [[buffer(1)]]) {
    float4 color = tex.sample(smp, in.texcoord);
    return float4(color.rgb, color.a * params.alpha);
}
)msl";

// Color-only shader: for fills and lines (no texture sampling).
// Each vertex has position and color; fragment outputs the color.
NSString* const kColorShaderSource = @R"msl(
#include <metal_stdlib>
using namespace metal;

struct ColorVertexIn {
    float2 position;
    float4 color;
};

struct ColorVertexOut {
    float4 position [[position]];
    float4 color;
};

struct Projection {
    float4x4 matrix;
};

vertex ColorVertexOut color_vertex(uint vid [[vertex_id]],
                                    constant ColorVertexIn* vertices [[buffer(0)]],
                                    constant Projection& proj [[buffer(1)]]) {
    ColorVertexOut out;
    out.position = proj.matrix * float4(vertices[vid].position, 0.0, 1.0);
    out.color = vertices[vid].color;
    return out;
}

fragment float4 color_fragment(ColorVertexOut in [[stage_in]]) {
    return in.color;
}
)msl";

bool metal_debug_draw_enabled() {
  static const bool enabled = std::getenv("CORSIXTH_METAL_DEBUG_DRAW") != nullptr;
  return enabled;
}

}  // namespace

metal_renderer::metal_renderer(SDL_Window* window,
                               const metal_creation_params& params)
    : window_(window),
      width_(params.width),
      height_(params.height),
      min_width_(params.min_width),
      min_height_(params.min_height),
      drawable_width_(params.width),
      drawable_height_(params.height),
      device_(nullptr),
      command_queue_(nullptr),
      layer_(nullptr),
      current_drawable_(nullptr),
      current_cmd_buf_(nullptr),
      current_enc_(nullptr),
      current_target_(nullptr),
      current_target_width_(params.width),
      current_target_height_(params.height),
      pipeline_state_(nullptr),
      color_pipeline_state_(nullptr),
      sampler_state_(nullptr),
      vertex_buffer_(nullptr) {
  // Create Metal device
  id<MTLDevice> device = MTLCreateSystemDefaultDevice();
  if (!device) {
    return;
  }
  device_ = (void*)CFBridgingRetain(device);

  // Create command queue
  id<MTLCommandQueue> queue = [device newCommandQueue];
  if (!queue) {
    CFRelease((CFTypeRef)device_);
    device_ = nullptr;
    return;
  }
  command_queue_ = (void*)CFBridgingRetain(queue);

  // M19: Create the persistent vertex buffer pool (1MB)
  id<MTLBuffer> vbuf =
      [device newBufferWithLength:vertex_buffer_size_
                          options:MTLResourceStorageModeShared];
  if (vbuf) {
    vertex_buffer_ = (void*)CFBridgingRetain(vbuf);
  }

  CAMetalLayer* layer = [CAMetalLayer layer];
  layer.device = device;
  layer.pixelFormat = MTLPixelFormatBGRA8Unorm;
  layer.framebufferOnly = NO;
  layer.opaque = YES;
  layer.drawableSize =
      CGSizeMake(static_cast<CGFloat>(drawable_width_),
                 static_cast<CGFloat>(drawable_height_));
  layer_ = (void*)CFBridgingRetain(layer);
  if (!setup_layer()) {
    std::fprintf(stderr, "Warning: Metal layer setup failed\n");
    return;
  }

  // M13 probe: device and queue created successfully. CAMetalLayer
  // integration is deferred to M15 (native render path).
  // M14: native texture creation is now supported via create_texture().
  // M15: pipeline state for sprite rendering.
  if (!init_pipeline()) {
    std::fprintf(stderr, "Warning: Metal pipeline init failed\n");
  }

  // M21: Log startup info for diagnostics
  NSString* devName = [device name];
  std::printf("[Metal] Initialized: device='%s' pool=%zuKB\n",
              devName ? [devName UTF8String] : "unknown",
              vertex_buffer_size_ / 1024);
}

metal_renderer::~metal_renderer() {
  if (current_enc_) {
    CFRelease((CFTypeRef)current_enc_);
    current_enc_ = nullptr;
  }
  if (current_cmd_buf_) {
    CFRelease((CFTypeRef)current_cmd_buf_);
    current_cmd_buf_ = nullptr;
  }
  if (current_drawable_) {
    CFRelease((CFTypeRef)current_drawable_);
    current_drawable_ = nullptr;
  }
  if (sampler_state_) {
    CFRelease((CFTypeRef)sampler_state_);
    sampler_state_ = nullptr;
  }
  if (color_pipeline_state_) {
    CFRelease((CFTypeRef)color_pipeline_state_);
    color_pipeline_state_ = nullptr;
  }
  if (pipeline_state_) {
    CFRelease((CFTypeRef)pipeline_state_);
    pipeline_state_ = nullptr;
  }
  if (layer_) {
    CFRelease((CFTypeRef)layer_);
    layer_ = nullptr;
  }
  if (command_queue_) {
    CFRelease((CFTypeRef)command_queue_);
    command_queue_ = nullptr;
  }
  if (vertex_buffer_) {
    CFRelease((CFTypeRef)vertex_buffer_);
    vertex_buffer_ = nullptr;
  }
  if (device_) {
    CFRelease((CFTypeRef)device_);
    device_ = nullptr;
  }
}

bool metal_renderer::valid() const {
  return device_ != nullptr && command_queue_ != nullptr;
}

const char* metal_renderer::device_name() const {
  if (!device_) {
    return "none";
  }
  id<MTLDevice> device = (__bridge id<MTLDevice>)device_;
  return [[device name] UTF8String];
}

// ---- metal_texture implementation ----

metal_texture::metal_texture(metal_renderer* renderer, int width, int height,
                             metal_pixel_format format, const void* data)
    : renderer_(renderer), width_(width), height_(height), format_(format),
      texture_(nullptr) {
  if (!renderer_ || !renderer_->valid()) {
    return;
  }

  id<MTLDevice> device = (__bridge id<MTLDevice>)renderer_->device_handle();

  // Map our enum to Metal's MTLPixelFormat
  MTLPixelFormat mtl_format;
  size_t bytes_per_pixel;
  switch (format) {
    case metal_pixel_format::BGRA8Unorm:
      mtl_format = MTLPixelFormatBGRA8Unorm;
      bytes_per_pixel = 4;
      break;
    case metal_pixel_format::RGBA8Unorm:
      mtl_format = MTLPixelFormatRGBA8Unorm;
      bytes_per_pixel = 4;
      break;
    case metal_pixel_format::R8Unorm:
      mtl_format = MTLPixelFormatR8Unorm;
      bytes_per_pixel = 1;
      break;
    default:
      mtl_format = MTLPixelFormatBGRA8Unorm;
      bytes_per_pixel = 4;
      break;
  }

  // Create texture descriptor
  MTLTextureDescriptor* desc =
      [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:mtl_format
                                                          width:width
                                                         height:height
                                                      mipmapped:NO];
  desc.usage = MTLTextureUsageShaderRead;
  desc.storageMode = MTLStorageModeShared;
  desc.cpuCacheMode = MTLCPUCacheModeDefaultCache;

  id<MTLTexture> texture = [device newTextureWithDescriptor:desc];
  if (!texture) {
    return;
  }

  // Upload the pixel data
  if (data) {
    MTLRegion region = MTLRegionMake2D(0, 0, width, height);
    NSUInteger bytes_per_row = width * bytes_per_pixel;
    [texture replaceRegion:region
               mipmapLevel:0
                 withBytes:data
               bytesPerRow:bytes_per_row];

    static int texture_log_count = 0;
    if (metal_debug_draw_enabled() && texture_log_count < 24) {
      const uint8_t* bytes = static_cast<const uint8_t*>(data);
      const int sample_pixels = std::min(width * height, 4096);
      int opaque = 0;
      int transparent = 0;
      if (bytes_per_pixel == 4) {
        for (int i = 0; i < sample_pixels; ++i) {
          uint8_t alpha = bytes[i * 4 + 3];
          if (alpha == 0) {
            ++transparent;
          } else {
            ++opaque;
          }
        }
      }
      std::fprintf(stderr,
                   "[MetalDebug] upload #%d %dx%d fmt=%d first=%u,%u,%u,%u "
                   "sample_opaque=%d sample_transparent=%d\n",
                   texture_log_count, width, height, static_cast<int>(format),
                   bytes_per_pixel >= 1 ? bytes[0] : 0,
                   bytes_per_pixel >= 2 ? bytes[1] : 0,
                   bytes_per_pixel >= 3 ? bytes[2] : 0,
                   bytes_per_pixel >= 4 ? bytes[3] : 0,
                   opaque, transparent);
      ++texture_log_count;
    }
  }

  texture_ = (void*)CFBridgingRetain(texture);
}

metal_texture::~metal_texture() {
  if (texture_) {
    CFRelease((CFTypeRef)texture_);
    texture_ = nullptr;
  }
}

std::unique_ptr<metal_texture> metal_renderer::create_texture(
    int width, int height, metal_pixel_format format, const void* data) {
  if (!valid()) {
    return nullptr;
  }
  auto tex = std::make_unique<metal_texture>(this, width, height, format, data);
  if (tex->texture_handle()) {
    live_textures_++;
    total_textures_created_++;
  }
  return tex;
}

bool metal_renderer::setup_layer() {
  if (!layer_) {
    return false;
  }

  // Re-setup after resize
  SDL_SysWMinfo wmInfo;
  SDL_VERSION(&wmInfo.version);
  if (!SDL_GetWindowWMInfo(window_, &wmInfo)) {
    return false;
  }
  NSWindow* ns_window = wmInfo.info.cocoa.window;
  NSView* content_view = [ns_window contentView];
  if (!content_view) {
    return false;
  }

  CAMetalLayer* layer = (__bridge CAMetalLayer*)layer_;
  layer.frame = content_view.bounds;
  layer.contentsScale = [ns_window backingScaleFactor];
  update_drawable_size();
  layer.autoresizingMask = kCALayerWidthSizable | kCALayerHeightSizable;

  content_view.wantsLayer = YES;
  content_view.layer = layer;
  return true;
}

void metal_renderer::update_drawable_size() {
  if (!layer_) {
    return;
  }

  CAMetalLayer* layer = (__bridge CAMetalLayer*)layer_;
  CGSize point_size = layer.bounds.size;
  CGFloat scale = layer.contentsScale > 0.0 ? layer.contentsScale : 1.0;

  drawable_width_ = std::max(
      1, static_cast<int>(std::lround(point_size.width * scale)));
  drawable_height_ = std::max(
      1, static_cast<int>(std::lround(point_size.height * scale)));

  if (width_ > 0) {
    drawable_scale_x_ = static_cast<double>(drawable_width_) / width_;
  } else {
    drawable_scale_x_ = 1.0;
  }
  if (height_ > 0) {
    drawable_scale_y_ = static_cast<double>(drawable_height_) / height_;
  } else {
    drawable_scale_y_ = 1.0;
  }

  layer.drawableSize =
      CGSizeMake(static_cast<CGFloat>(drawable_width_),
                 static_cast<CGFloat>(drawable_height_));
}

bool metal_renderer::start_frame() {
  if (!valid()) return false;

  // M21: Signpost for frame start (visible in Instruments.app)
  os_signpost_interval_begin(metal_signpost_log(), OS_SIGNPOST_ID_EXCLUSIVE,
                              "Frame", "start");

  // M19: Reset the persistent vertex buffer for this frame
  vertex_buffer_used_ = 0;

  CAMetalLayer* layer = (__bridge CAMetalLayer*)layer_;

  // Get the next drawable
  id<CAMetalDrawable> drawable = [layer nextDrawable];
  if (!drawable) {
    os_signpost_interval_end(metal_signpost_log(), OS_SIGNPOST_ID_EXCLUSIVE,
                              "Frame");
    return false;
  }
  current_drawable_ = (void*)CFBridgingRetain(drawable);

  // Create command buffer
  id<MTLCommandQueue> queue = (__bridge id<MTLCommandQueue>)command_queue_;
  id<MTLCommandBuffer> cmd_buf = [queue commandBuffer];
  current_cmd_buf_ = (void*)CFBridgingRetain(cmd_buf);

  // Initial target is the drawable
  current_target_ = nullptr;
  current_target_width_ = width_;
  current_target_height_ = height_;

  // Create render pass descriptor with clear to black
  MTLRenderPassDescriptor* pass_desc = [MTLRenderPassDescriptor renderPassDescriptor];
  pass_desc.colorAttachments[0].texture = drawable.texture;
  pass_desc.colorAttachments[0].loadAction = MTLLoadActionClear;
  pass_desc.colorAttachments[0].storeAction = MTLStoreActionStore;
  pass_desc.colorAttachments[0].clearColor = MTLClearColorMake(0.0, 0.0, 0.0, 1.0);

  // Create render command encoder
  id<MTLCommandBuffer> cb = (__bridge id<MTLCommandBuffer>)current_cmd_buf_;
  id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:pass_desc];
  if (!enc) {
    return false;
  }
  current_enc_ = (void*)CFBridgingRetain(enc);
  apply_clip_rect();

  return true;
}

bool metal_renderer::end_frame(std::vector<uint8_t>* bgra_pixels,
                               int* capture_width, int* capture_height) {
  if (!current_cmd_buf_ || !current_drawable_) return false;

  id<MTLCommandBuffer> cmd_buf = (__bridge id<MTLCommandBuffer>)current_cmd_buf_;
  id<CAMetalDrawable> drawable =
      (__bridge id<CAMetalDrawable>)current_drawable_;
  id<MTLRenderCommandEncoder> enc = (__bridge id<MTLRenderCommandEncoder>)current_enc_;

  // End encoding
  if (enc) {
    [enc endEncoding];
  }

  id<MTLBuffer> readback = nil;
  int readback_width = 0;
  int readback_height = 0;
  NSUInteger readback_bytes_per_row = 0;
  if (bgra_pixels) {
    readback_width = static_cast<int>(drawable.texture.width);
    readback_height = static_cast<int>(drawable.texture.height);
    readback_bytes_per_row = static_cast<NSUInteger>(readback_width * 4);
    id<MTLDevice> device = (__bridge id<MTLDevice>)device_;
    readback = [device newBufferWithLength:readback_bytes_per_row * readback_height
                                    options:MTLResourceStorageModeShared];
    if (readback) {
      id<MTLBlitCommandEncoder> blit = [cmd_buf blitCommandEncoder];
      MTLOrigin origin = MTLOriginMake(0, 0, 0);
      MTLSize size = MTLSizeMake(static_cast<NSUInteger>(readback_width),
                                 static_cast<NSUInteger>(readback_height), 1);
      [blit copyFromTexture:drawable.texture
                sourceSlice:0
                sourceLevel:0
               sourceOrigin:origin
                 sourceSize:size
                   toBuffer:readback
          destinationOffset:0
     destinationBytesPerRow:readback_bytes_per_row
   destinationBytesPerImage:readback_bytes_per_row * readback_height];
      [blit endEncoding];
    }
  }

  // Present the drawable
  [cmd_buf presentDrawable:drawable];
  [cmd_buf commit];

  if (readback) {
    [cmd_buf waitUntilCompleted];
    const size_t byte_count =
        static_cast<size_t>(readback_bytes_per_row) * readback_height;
    bgra_pixels->resize(byte_count);
    std::memcpy(bgra_pixels->data(), [readback contents], byte_count);
    if (capture_width) {
      *capture_width = readback_width;
    }
    if (capture_height) {
      *capture_height = readback_height;
    }
    [readback release];
  }

  // M21: Signpost for frame end
  os_signpost_interval_end(metal_signpost_log(), OS_SIGNPOST_ID_EXCLUSIVE,
                            "Frame");

  // Clean up
  if (current_enc_) {
    CFRelease((CFTypeRef)current_enc_);
    current_enc_ = nullptr;
  }
  if (current_cmd_buf_) {
    CFRelease((CFTypeRef)current_cmd_buf_);
    current_cmd_buf_ = nullptr;
  }
  if (current_drawable_) {
    CFRelease((CFTypeRef)current_drawable_);
    current_drawable_ = nullptr;
  }

  return true;
}

void metal_renderer::on_resize(int width, int height) {
  width_ = width;
  height_ = height;

  if (layer_) {
    CAMetalLayer* layer = (__bridge CAMetalLayer*)layer_;
    layer.frame = layer.superlayer ? layer.superlayer.bounds : layer.frame;
    update_drawable_size();
  }
}

void metal_renderer::set_clip_rect(const SDL_Rect* rect) {
  if (rect) {
    has_clip_rect_ = true;
    clip_x_ = rect->x;
    clip_y_ = rect->y;
    clip_w_ = rect->w;
    clip_h_ = rect->h;
  } else {
    has_clip_rect_ = false;
  }
  apply_clip_rect();
}

void metal_renderer::apply_clip_rect() {
  if (!current_enc_) {
    return;
  }

  int x = 0;
  int y = 0;
  int w = current_target_width_;
  int h = current_target_height_;

  if (has_clip_rect_) {
    const int right = std::min(current_target_width_, clip_x_ + clip_w_);
    const int bottom = std::min(current_target_height_, clip_y_ + clip_h_);
    x = std::max(0, clip_x_);
    y = std::max(0, clip_y_);
    w = std::max(0, right - x);
    h = std::max(0, bottom - y);
  }

  int pixel_x = x;
  int pixel_y = y;
  int pixel_w = w;
  int pixel_h = h;

  if (current_target_ == nullptr) {
    const int pixel_right = std::min(
        drawable_width_,
        static_cast<int>(std::ceil((x + w) * drawable_scale_x_)));
    const int pixel_bottom = std::min(
        drawable_height_,
        static_cast<int>(std::ceil((y + h) * drawable_scale_y_)));
    pixel_x = std::max(
        0, static_cast<int>(std::floor(x * drawable_scale_x_)));
    pixel_y = std::max(
        0, static_cast<int>(std::floor(y * drawable_scale_y_)));
    pixel_w = std::max(0, pixel_right - pixel_x);
    pixel_h = std::max(0, pixel_bottom - pixel_y);
  }

  MTLScissorRect scissor = {
      static_cast<NSUInteger>(pixel_x),
      static_cast<NSUInteger>(pixel_y),
      static_cast<NSUInteger>(pixel_w),
      static_cast<NSUInteger>(pixel_h),
  };
  id<MTLRenderCommandEncoder> enc =
      (__bridge id<MTLRenderCommandEncoder>)current_enc_;
  [enc setScissorRect:scissor];
}

bool metal_renderer::init_pipeline() {
  if (!device_) return false;

  id<MTLDevice> device = (__bridge id<MTLDevice>)device_;

  NSError* err = nil;

  // Compile the shader library from source
  id<MTLLibrary> lib =
      [device newLibraryWithSource:kSpriteShaderSource options:nil error:&err];
  if (!lib) {
    std::fprintf(stderr, "Failed to compile Metal shader: %s\n",
                 err ? [[err localizedDescription] UTF8String] : "unknown");
    return false;
  }

  id<MTLFunction> vert = [lib newFunctionWithName:@"sprite_vertex"];
  id<MTLFunction> frag = [lib newFunctionWithName:@"sprite_fragment"];
  if (!vert || !frag) {
    std::fprintf(stderr, "Failed to find shader functions\n");
    return false;
  }

  // Create the render pipeline state
  MTLRenderPipelineDescriptor* desc = [MTLRenderPipelineDescriptor new];
  desc.vertexFunction = vert;
  desc.fragmentFunction = frag;
  desc.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;

  // Alpha blending (matches SDL_BLENDMODE_BLEND)
  desc.colorAttachments[0].blendingEnabled = YES;
  desc.colorAttachments[0].rgbBlendOperation = MTLBlendOperationAdd;
  desc.colorAttachments[0].alphaBlendOperation = MTLBlendOperationAdd;
  desc.colorAttachments[0].sourceRGBBlendFactor = MTLBlendFactorSourceAlpha;
  desc.colorAttachments[0].sourceAlphaBlendFactor = MTLBlendFactorSourceAlpha;
  desc.colorAttachments[0].destinationRGBBlendFactor =
      MTLBlendFactorOneMinusSourceAlpha;
  desc.colorAttachments[0].destinationAlphaBlendFactor =
      MTLBlendFactorOneMinusSourceAlpha;

  id<MTLRenderPipelineState> ps =
      [device newRenderPipelineStateWithDescriptor:desc error:&err];
  if (!ps) {
    std::fprintf(stderr, "Failed to create pipeline state: %s\n",
                 err ? [[err localizedDescription] UTF8String] : "unknown");
    return false;
  }
  pipeline_state_ = (void*)CFBridgingRetain(ps);

  // M17: Create a separate color-only pipeline state
  NSError* color_err = nil;
  id<MTLLibrary> color_lib =
      [device newLibraryWithSource:kColorShaderSource options:nil error:&color_err];
  if (!color_lib) {
    std::fprintf(stderr, "Failed to compile color shader: %s\n",
                 color_err ? [[color_err localizedDescription] UTF8String] : "unknown");
  } else {
    id<MTLFunction> color_vert = [color_lib newFunctionWithName:@"color_vertex"];
    id<MTLFunction> color_frag = [color_lib newFunctionWithName:@"color_fragment"];
    if (color_vert && color_frag) {
      MTLRenderPipelineDescriptor* color_desc = [MTLRenderPipelineDescriptor new];
      color_desc.vertexFunction = color_vert;
      color_desc.fragmentFunction = color_frag;
      color_desc.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
      // Alpha blending matches SDL_BLENDMODE_BLEND
      color_desc.colorAttachments[0].blendingEnabled = YES;
      color_desc.colorAttachments[0].rgbBlendOperation = MTLBlendOperationAdd;
      color_desc.colorAttachments[0].alphaBlendOperation = MTLBlendOperationAdd;
      color_desc.colorAttachments[0].sourceRGBBlendFactor = MTLBlendFactorSourceAlpha;
      color_desc.colorAttachments[0].sourceAlphaBlendFactor = MTLBlendFactorSourceAlpha;
      color_desc.colorAttachments[0].destinationRGBBlendFactor = MTLBlendFactorOneMinusSourceAlpha;
      color_desc.colorAttachments[0].destinationAlphaBlendFactor = MTLBlendFactorOneMinusSourceAlpha;
      id<MTLRenderPipelineState> color_ps =
          [device newRenderPipelineStateWithDescriptor:color_desc error:&color_err];
      if (color_ps) {
        color_pipeline_state_ = (void*)CFBridgingRetain(color_ps);
      } else {
        std::fprintf(stderr, "Failed to create color pipeline state: %s\n",
                     color_err ? [[color_err localizedDescription] UTF8String] : "unknown");
      }
    } else {
      std::fprintf(stderr, "Failed to find color shader functions\n");
    }
  }

  // Create a sampler state (linear filter, clamp-to-edge)
  MTLSamplerDescriptor* smp_desc = [MTLSamplerDescriptor new];
  smp_desc.minFilter = MTLSamplerMinMagFilterLinear;
  smp_desc.magFilter = MTLSamplerMinMagFilterLinear;
  smp_desc.sAddressMode = MTLSamplerAddressModeClampToEdge;
  smp_desc.tAddressMode = MTLSamplerAddressModeClampToEdge;
  id<MTLSamplerState> smp = [device newSamplerStateWithDescriptor:smp_desc];
  sampler_state_ = (void*)CFBridgingRetain(smp);

  return true;
}

bool metal_renderer::begin_render_pass(metal_texture* target, bool clear) {
  if (!current_cmd_buf_ || !pipeline_state_) return false;

  id<MTLCommandBuffer> cmd_buf = (__bridge id<MTLCommandBuffer>)current_cmd_buf_;

  // End any previous encoder before starting a new pass
  if (current_enc_) {
    [(id<MTLRenderCommandEncoder>)current_enc_ endEncoding];
    CFRelease((CFTypeRef)current_enc_);
    current_enc_ = nullptr;
  }

  // Determine the target texture
  id<MTLTexture> tex = nil;
  if (target) {
    tex = (__bridge id<MTLTexture>)target->texture_handle();
    current_target_ = target;
    current_target_width_ = target->width();
    current_target_height_ = target->height();
  } else {
    // Use drawable texture
    if (!current_drawable_) return false;
    id<CAMetalDrawable> drawable =
        (__bridge id<CAMetalDrawable>)current_drawable_;
    tex = drawable.texture;
    current_target_ = nullptr;
    current_target_width_ = width_;
    current_target_height_ = height_;
  }

  MTLRenderPassDescriptor* pass_desc =
      [MTLRenderPassDescriptor renderPassDescriptor];
  pass_desc.colorAttachments[0].texture = tex;
  pass_desc.colorAttachments[0].loadAction =
      clear ? MTLLoadActionClear : MTLLoadActionLoad;
  pass_desc.colorAttachments[0].storeAction = MTLStoreActionStore;
  pass_desc.colorAttachments[0].clearColor =
      target ? MTLClearColorMake(0.0, 0.0, 0.0, 0.0)
             : MTLClearColorMake(0.0, 0.0, 0.0, 1.0);

  id<MTLRenderCommandEncoder> enc =
      [cmd_buf renderCommandEncoderWithDescriptor:pass_desc];
  if (!enc) return false;

  current_enc_ = (void*)CFBridgingRetain(enc);
  apply_clip_rect();
  return true;
}

void metal_renderer::end_render_pass() {
  if (current_enc_) {
    id<MTLRenderCommandEncoder> enc =
        (__bridge id<MTLRenderCommandEncoder>)current_enc_;
    [enc endEncoding];
    CFRelease((CFTypeRef)current_enc_);
    current_enc_ = nullptr;
  }
}

void metal_renderer::draw_sprite(metal_texture* tex, const SDL_Rect* src_rect,
                                 const SDL_FRect* dst_rect, int flags) {
  if (!tex || !tex->texture_handle() || !current_enc_ || !pipeline_state_) {
    return;
  }
  if (!dst_rect) return;

  id<MTLDevice> device = (__bridge id<MTLDevice>)device_;
  id<MTLRenderCommandEncoder> enc =
      (__bridge id<MTLRenderCommandEncoder>)current_enc_;
  id<MTLRenderPipelineState> ps =
      (__bridge id<MTLRenderPipelineState>)pipeline_state_;
  id<MTLSamplerState> smp = (__bridge id<MTLSamplerState>)sampler_state_;
  id<MTLTexture> mtl_tex = (__bridge id<MTLTexture>)tex->texture_handle();

  // Compute the source UV rect (normalized 0..1)
  float tex_w = static_cast<float>(tex->width());
  float tex_h = static_cast<float>(tex->height());
  float u0, v0, u1, v1;
  if (src_rect) {
    u0 = src_rect->x / tex_w;
    v0 = src_rect->y / tex_h;
    u1 = (src_rect->x + src_rect->w) / tex_w;
    v1 = (src_rect->y + src_rect->h) / tex_h;
  } else {
    u0 = 0.0f;
    v0 = 0.0f;
    u1 = 1.0f;
    v1 = 1.0f;
  }

  // M20: Handle flip flags by swapping UVs
  const bool flip_h = (flags & 0x0001) != 0;  // thdf_flip_horizontal
  const bool flip_v = (flags & 0x0002) != 0;  // thdf_flip_vertical
  if (flip_h) std::swap(u0, u1);
  if (flip_v) std::swap(v0, v1);

  // M20: Compute alpha multiplier from flags
  // thdf_alpha_50 = 0x0004 -> alpha 0.5
  // thdf_alpha_75 = 0x0008 -> alpha 0.25
  float alpha_mult = 1.0f;
  if (flags & 0x0004) alpha_mult = 0.5f;
  if (flags & 0x0008) alpha_mult = 0.25f;

  // 4 vertices in triangle-strip order: TL, TR, BL, BR (in pixel space)
  struct VertexIn {
    float position[2];
    float texcoord[2];
  };
  VertexIn vertices[4] = {
      {{dst_rect->x, dst_rect->y}, {u0, v0}},
      {{dst_rect->x + dst_rect->w, dst_rect->y}, {u1, v0}},
      {{dst_rect->x, dst_rect->y + dst_rect->h}, {u0, v1}},
      {{dst_rect->x + dst_rect->w, dst_rect->y + dst_rect->h}, {u1, v1}},
  };

  // M20: Pack projection matrix and alpha into a single DrawParams struct
  // (4x4 matrix + 1 float = 17 floats = 68 bytes, padded to 80 for alignment)
  struct DrawParams {
    float proj[16];
    float alpha;
    float pad[3];
  };
  float W = static_cast<float>(current_target_width_);
  float H = static_cast<float>(current_target_height_);
  DrawParams params = {{
      2.0f / W, 0.0f,      0.0f, 0.0f,
      0.0f,     -2.0f / H, 0.0f, 0.0f,
      0.0f,     0.0f,      1.0f, 0.0f,
      -1.0f,    1.0f,      0.0f, 1.0f,
  }, alpha_mult, {0.0f, 0.0f, 0.0f}};

  static int sprite_log_count = 0;
  if (metal_debug_draw_enabled() && sprite_log_count < 64) {
    std::fprintf(stderr,
                 "[MetalDebug] sprite #%d target=%dx%d tex=%dx%d src=%d,%d,%d,%d "
                 "dst=%.2f,%.2f,%.2f,%.2f uv=%.3f,%.3f,%.3f,%.3f flags=%d "
                 "alpha=%.2f\n",
                 sprite_log_count, current_target_width_, current_target_height_,
                 tex->width(), tex->height(), src_rect ? src_rect->x : 0,
                 src_rect ? src_rect->y : 0, src_rect ? src_rect->w : tex->width(),
                 src_rect ? src_rect->h : tex->height(), dst_rect->x,
                 dst_rect->y, dst_rect->w, dst_rect->h, u0, v0, u1, v1, flags,
                 alpha_mult);
    ++sprite_log_count;
  }

  [enc setRenderPipelineState:ps];
  [enc setVertexBytes:vertices length:sizeof(vertices) atIndex:0];
  [enc setVertexBytes:&params length:sizeof(params) atIndex:1];
  [enc setFragmentBytes:&params length:sizeof(params) atIndex:1];
  [enc setFragmentTexture:mtl_tex atIndex:0];
  [enc setFragmentSamplerState:smp atIndex:0];
  [enc drawPrimitives:MTLPrimitiveTypeTriangleStrip vertexStart:0 vertexCount:4];
}

std::unique_ptr<metal_texture> metal_renderer::create_render_target(
    int width, int height) {
  if (!valid()) {
    return nullptr;
  }

  id<MTLDevice> device = (__bridge id<MTLDevice>)device_;

  // Render target texture needs RenderTarget + ShaderRead usage
  MTLTextureDescriptor* desc =
      [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm
                                                          width:width
                                                         height:height
                                                      mipmapped:NO];
  desc.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
  desc.storageMode = MTLStorageModePrivate;
  desc.cpuCacheMode = MTLCPUCacheModeDefaultCache;

  id<MTLTexture> tex = [device newTextureWithDescriptor:desc];
  if (!tex) {
    return nullptr;
  }

  // Create a metal_texture with null data first, then swap in our pre-created
  // texture. The first allocation will be a "staging" texture that gets
  // immediately replaced.
  auto wrapper = std::make_unique<metal_texture>(this, width, height,
                                                metal_pixel_format::BGRA8Unorm,
                                                nullptr);
  // Swap: release the staging texture, take ownership of our render target
  if (wrapper->get_texture_handle()) {
    CFRelease((CFTypeRef)wrapper->get_texture_handle());
  }
  wrapper->set_texture_handle((void*)CFBridgingRetain(tex));

  live_textures_++;
  total_textures_created_++;
  return wrapper;
}

void metal_renderer::blit_texture(metal_texture* source) {
  if (!source || !source->texture_handle() || !current_enc_) {
    return;
  }
  // Draw the source texture to fill the current render target
  SDL_FRect dst_rect = {0.0f, 0.0f,
                        static_cast<float>(current_target_width_),
                        static_cast<float>(current_target_height_)};
  draw_sprite(source, nullptr, &dst_rect);
}

// ---- Color drawing (M17) ----

void metal_renderer::draw_color_rect(const SDL_FRect* rect, float r, float g,
                                     float b, float a) {
  if (!rect || !current_enc_ || !color_pipeline_state_) {
    return;
  }

  id<MTLDevice> device = (__bridge id<MTLDevice>)device_;
  id<MTLRenderCommandEncoder> enc =
      (__bridge id<MTLRenderCommandEncoder>)current_enc_;
  id<MTLRenderPipelineState> ps =
      (__bridge id<MTLRenderPipelineState>)color_pipeline_state_;

  // 4 vertices in triangle-strip order: TL, TR, BL, BR
  struct ColorVertex {
    float position[4];
    float color[4];
  };
  ColorVertex vertices[4] = {
      {{rect->x, rect->y, 0.0f, 0.0f}, {r, g, b, a}},
      {{rect->x + rect->w, rect->y, 0.0f, 0.0f}, {r, g, b, a}},
      {{rect->x, rect->y + rect->h, 0.0f, 0.0f}, {r, g, b, a}},
      {{rect->x + rect->w, rect->y + rect->h, 0.0f, 0.0f}, {r, g, b, a}},
  };

  // Compute the orthographic projection matrix
  float W = static_cast<float>(current_target_width_);
  float H = static_cast<float>(current_target_height_);
  float proj[16] = {
      2.0f / W, 0.0f,      0.0f, 0.0f,
      0.0f,     -2.0f / H, 0.0f, 0.0f,
      0.0f,     0.0f,      1.0f, 0.0f,
      -1.0f,    1.0f,      0.0f, 1.0f,
  };

  [enc setRenderPipelineState:ps];
  [enc setVertexBytes:vertices length:sizeof(vertices) atIndex:0];
  [enc setVertexBytes:proj length:sizeof(proj) atIndex:1];
  [enc drawPrimitives:MTLPrimitiveTypeTriangleStrip vertexStart:0 vertexCount:4];
}

void metal_renderer::draw_color_line(float x1, float y1, float x2, float y2,
                                    float r, float g, float b, float a) {
  if (!current_enc_ || !color_pipeline_state_) {
    return;
  }

  id<MTLDevice> device = (__bridge id<MTLDevice>)device_;
  id<MTLRenderCommandEncoder> enc =
      (__bridge id<MTLRenderCommandEncoder>)current_enc_;
  id<MTLRenderPipelineState> ps =
      (__bridge id<MTLRenderPipelineState>)color_pipeline_state_;

  struct ColorVertex {
    float position[4];
    float color[4];
  };
  ColorVertex vertices[2] = {
      {{x1, y1, 0.0f, 0.0f}, {r, g, b, a}},
      {{x2, y2, 0.0f, 0.0f}, {r, g, b, a}},
  };

  float W = static_cast<float>(current_target_width_);
  float H = static_cast<float>(current_target_height_);
  float proj[16] = {
      2.0f / W, 0.0f,      0.0f, 0.0f,
      0.0f,     -2.0f / H, 0.0f, 0.0f,
      0.0f,     0.0f,      1.0f, 0.0f,
      -1.0f,    1.0f,      0.0f, 1.0f,
  };

  static int line_log_count = 0;
  if (metal_debug_draw_enabled() && line_log_count < 32) {
    std::fprintf(stderr,
                 "[MetalDebug] line #%d target=%dx%d %.2f,%.2f -> %.2f,%.2f "
                 "rgba=%.2f,%.2f,%.2f,%.2f\n",
                 line_log_count, current_target_width_, current_target_height_, x1,
                 y1, x2, y2, r, g, b, a);
    ++line_log_count;
  }

  [enc setRenderPipelineState:ps];
  [enc setVertexBytes:vertices length:sizeof(vertices) atIndex:0];
  [enc setVertexBytes:proj length:sizeof(proj) atIndex:1];
  [enc drawPrimitives:MTLPrimitiveTypeLine vertexStart:0 vertexCount:2];
}

// ---- M19: Persistent vertex buffer pool ----

size_t metal_renderer::write_to_vertex_buffer(const void* data, size_t size) {
  if (!vertex_buffer_) {
    return SIZE_MAX;
  }
  // Align to 16 bytes
  size_t aligned_size = (size + 15) & ~static_cast<size_t>(15);
  if (vertex_buffer_used_ + aligned_size > vertex_buffer_size_) {
    return SIZE_MAX;  // Pool exhausted
  }

  id<MTLBuffer> buf = (__bridge id<MTLBuffer>)vertex_buffer_;
  void* contents = [buf contents];
  std::memcpy(static_cast<char*>(contents) + vertex_buffer_used_, data, size);

  size_t offset = vertex_buffer_used_;
  vertex_buffer_used_ += aligned_size;
  return offset;
}
