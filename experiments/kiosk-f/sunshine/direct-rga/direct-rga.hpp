// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <cstdint>
#include <memory>
#include <string>
namespace vyarm {
struct direct_surface {
  int fd, width, height;
  uint32_t format, pitch, offset;
  uint64_t modifier;
};
struct direct_cursor {
  const uint8_t *bgra = nullptr;
  unsigned width = 0, height = 0;
  int x = 0, y = 0;
};
// Capture-thread owned. Borrowed input fd remains live until capture returns.
// Returns owned CPU NV12 bytes, not an encoder DMA-BUF/zero-copy claim.
class direct_rga {
  struct impl;
  std::unique_ptr<impl> state;
public:
  direct_rga();
  ~direct_rga();
  direct_rga(const direct_rga &) = delete;
  bool capture(const direct_surface &, int x, int y, unsigned w, unsigned h,
               bool bt709, bool full, const direct_cursor &, uint8_t *nv12,
               std::string &error, unsigned clockwise = 0);
};
}
