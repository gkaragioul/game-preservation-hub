#include "frame_logger.h"

frame_logger g_frame_logger;

frame_logger::frame_logger() {
  const char* path = std::getenv("CORSIXTH_FRAME_LOG");
  if (!path || !path[0]) return;

  file_ = std::fopen(path, "w");
  if (file_) {
    start_tick_ = SDL_GetTicks();
    write_header();
  }
}

frame_logger::~frame_logger() {
  if (file_) {
    std::fclose(file_);
    file_ = nullptr;
  }
}

void frame_logger::write_header() {
  if (!file_) return;
  std::fprintf(file_,
      "rel_ms,event,detail,renderer,res_w,res_h,fullscreen,tick_count,"
      "frame_reason\n");
}

void frame_logger::write_row(const char* event_name, const char* detail) {
  if (!file_) return;
  Uint32 now = SDL_GetTicks();
  Uint32 rel = now - start_tick_;
  const char* d = detail ? detail : "";
  std::fprintf(file_, "%u,%s,%s,%s,%d,%d,%d,%d,%s\n", rel, event_name, d,
               renderer_backend_, res_w_, res_h_, static_cast<int>(fullscreen_),
               tick_count_, frame_reason_);
}

void frame_logger::log_event(const char* event_name, const char* detail) {
  write_row(event_name, detail);
}
