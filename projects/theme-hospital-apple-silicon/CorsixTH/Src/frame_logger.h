#ifndef CORSIXTH_FRAME_LOGGER_H
#define CORSIXTH_FRAME_LOGGER_H

#include <SDL.h>

#include <cstdio>
#include <cstdlib>

class frame_logger {
 public:
  frame_logger();
  ~frame_logger();

  bool is_active() const { return file_ != nullptr; }

  void log_event(const char* event_name, const char* detail = nullptr);

  void set_renderer_backend(const char* name) {
    renderer_backend_ = name ? name : "unknown";
  }
  void set_resolution(int w, int h) {
    res_w_ = w;
    res_h_ = h;
  }
  void set_fullscreen(bool fs) { fullscreen_ = fs; }
  void set_tick_count(int n) { tick_count_ = n; }
  void set_frame_reason(const char* reason) {
    frame_reason_ = reason ? reason : "";
  }

 private:
  FILE* file_{nullptr};
  Uint32 start_tick_{0};
  const char* renderer_backend_{"unknown"};
  int res_w_{0};
  int res_h_{0};
  bool fullscreen_{false};
  int tick_count_{0};
  const char* frame_reason_{""};

  void write_header();
  void write_row(const char* event_name, const char* detail);
};

extern frame_logger g_frame_logger;

#endif
