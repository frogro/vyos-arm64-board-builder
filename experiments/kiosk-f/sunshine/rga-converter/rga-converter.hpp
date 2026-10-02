// Experimental opt-in V4L2 RGA converter. No device/board-number assumptions.
// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <linux/videodev2.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <fcntl.h>
#include <unistd.h>
#include <poll.h>
#include <cerrno>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <string>
#include <chrono>

namespace vyarm {
class rga_converter {
  struct buffer {
    void *data = MAP_FAILED;
    size_t length = 0;
    unsigned stride = 0;
    bool streaming = false;
  } in, out;
  int fd = -1;
  unsigned width = 0, height = 0, space = 0, range = 0;
  bool failed = false;
  static int ctl(int f, unsigned long op, void *arg) {
    int r; do { r = ioctl(f, op, arg); } while (r < 0 && errno == EINTR);
    return r;
  }
  bool setup(buffer &b, v4l2_buf_type type, unsigned fmt, unsigned quant) {
    v4l2_format f{}; f.type = type;
    auto &p = f.fmt.pix_mp;
    p.width = width; p.height = height; p.pixelformat = fmt;
    p.field = V4L2_FIELD_NONE; p.colorspace = space; p.quantization = quant;
    p.ycbcr_enc = space == V4L2_COLORSPACE_REC709 ? V4L2_YCBCR_ENC_709 : V4L2_YCBCR_ENC_601;
    p.num_planes = 1;
    if (ctl(fd, VIDIOC_S_FMT, &f) < 0 || p.width != width || p.height != height ||
        p.pixelformat != fmt || p.num_planes != 1 || p.quantization != quant ||
        p.colorspace != space) return false;
    b.stride = p.plane_fmt[0].bytesperline;
    const size_t required = fmt == V4L2_PIX_FMT_XBGR32 ? size_t(b.stride)*height : size_t(b.stride)*height*3/2;
    if (b.stride < width*(fmt == V4L2_PIX_FMT_XBGR32 ? 4u : 1u) || p.plane_fmt[0].sizeimage < required) return false;
    v4l2_requestbuffers req{}; req.type=type; req.memory=V4L2_MEMORY_MMAP; req.count=1;
    if (ctl(fd, VIDIOC_REQBUFS, &req)<0 || !req.count) return false;
    v4l2_buffer v{}; v4l2_plane planes[VIDEO_MAX_PLANES]{};
    v.type=type; v.memory=V4L2_MEMORY_MMAP; v.length=1; v.m.planes=planes;
    if (ctl(fd, VIDIOC_QUERYBUF, &v)<0 || planes[0].length < required) return false;
    b.length=planes[0].length;
    b.data=mmap(nullptr,b.length,PROT_READ|PROT_WRITE,MAP_SHARED,fd,planes[0].m.mem_offset);
    if(b.data==MAP_FAILED) return false;
    memset(b.data,0,b.length);
    return true;
  }
  bool queue(buffer &b,v4l2_buf_type type) {
    v4l2_buffer v{}; v4l2_plane planes[VIDEO_MAX_PLANES]{};
    v.type=type; v.memory=V4L2_MEMORY_MMAP; v.length=1; v.m.planes=planes;
    planes[0].length=b.length;
    if(type==V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE) planes[0].bytesused=b.stride*height;
    return ctl(fd,VIDIOC_QBUF,&v)==0;
  }
  bool dequeue(v4l2_buf_type type, bool &done) {
    if(done) return true;
    v4l2_buffer v{}; v4l2_plane planes[VIDEO_MAX_PLANES]{};
    v.type=type; v.memory=V4L2_MEMORY_MMAP; v.length=1; v.m.planes=planes;
    if(ctl(fd,VIDIOC_DQBUF,&v)<0) return errno==EAGAIN;
    if(v.index!=0 || v.flags & V4L2_BUF_FLAG_ERROR) return false;
    if(type==V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE &&
       (planes[0].data_offset!=0 || planes[0].bytesused<size_t(out.stride)*height*3/2)) return false;
    done=true; return true;
  }
  bool initialize() {
    namespace fs=std::filesystem;
    std::error_code ec;
    for(const auto &entry: fs::directory_iterator("/sys/class/video4linux",ec)) {
      std::ifstream name(entry.path()/"name"); std::string driver; std::getline(name,driver);
      if(driver!="rockchip-rga") continue;
      auto node=fs::path("/dev")/entry.path().filename();
      fd=open(node.c_str(),O_RDWR|O_NONBLOCK|O_CLOEXEC);
      if(fd>=0) break;
    }
    if(fd<0) return false;
    v4l2_capability cap{};
    if(ctl(fd,VIDIOC_QUERYCAP,&cap)<0) return false;
    unsigned caps=cap.capabilities & V4L2_CAP_DEVICE_CAPS ? cap.device_caps : cap.capabilities;
    if((caps & (V4L2_CAP_VIDEO_M2M_MPLANE|V4L2_CAP_STREAMING)) !=
       (V4L2_CAP_VIDEO_M2M_MPLANE|V4L2_CAP_STREAMING)) return false;
    return setup(in,V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE,V4L2_PIX_FMT_XBGR32,V4L2_QUANTIZATION_FULL_RANGE) &&
           setup(out,V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE,V4L2_PIX_FMT_NV12,range);
  }
  void close_device() {
    for(auto item : {std::pair<buffer*,v4l2_buf_type>{&in,V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE},
                    {&out,V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE}}) {
      if(item.first->streaming) ctl(fd,VIDIOC_STREAMOFF,&item.second);
      if(item.first->data!=MAP_FAILED) munmap(item.first->data,item.first->length);
      *item.first=buffer{};
    }
    if(fd>=0) close(fd);
    fd=-1;
  }
public:
  rga_converter()=default;
  rga_converter(const rga_converter&)=delete;
  rga_converter& operator=(const rga_converter&)=delete;
  ~rga_converter(){close_device();}
  // Same-size BGR0 -> NV12 only. Unsupported geometry must use swscale.
  bool convert(const uint8_t *src,int src_stride,uint8_t *y,int y_stride,uint8_t *uv,int uv_stride,
               unsigned w,unsigned h,bool bt709,bool full) {
    if(!src || !y || !uv || !w || !h || w>4096 || h>4096 || (w|h)&1 ||
       src_stride<int(w*4) || y_stride<int(w) || uv_stride<int(w)) return false;
    unsigned s=bt709?V4L2_COLORSPACE_REC709:V4L2_COLORSPACE_SMPTE170M;
    unsigned q=full?V4L2_QUANTIZATION_FULL_RANGE:V4L2_QUANTIZATION_LIM_RANGE;
    if(w!=width || h!=height || s!=space || q!=range) {
      close_device(); width=w;height=h;space=s;range=q;failed=false;
    }
    if(failed) return false;
    if(fd<0 && !initialize()) {close_device();failed=true;return false;}
    for(unsigned row=0;row<h;++row) memcpy(static_cast<uint8_t*>(in.data)+size_t(row)*in.stride,src+size_t(row)*src_stride,w*4);
    bool ok=queue(out,V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE) && queue(in,V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE);
    for(auto item:{std::pair<buffer*,v4l2_buf_type>{&out,V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE},
                  {&in,V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE}}) {
      if(ok && !item.first->streaming) {
        ok=ctl(fd,VIDIOC_STREAMON,&item.second)==0;item.first->streaming=ok;
      }
    }
    bool a=false,b=false;
    auto end=std::chrono::steady_clock::now()+std::chrono::milliseconds(100);
    while(ok && !(a&&b) && std::chrono::steady_clock::now()<end) {
      ok=dequeue(V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE,a) && dequeue(V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE,b);
      if(ok && !(a&&b)) {pollfd p{fd,POLLIN|POLLOUT,0}; int r=poll(&p,1,5); if(r<0 && errno!=EINTR) ok=false;}
    }
    if(!ok || !a || !b) {close_device();failed=true;return false;}
    for(unsigned row=0;row<h;++row) memcpy(y+size_t(row)*y_stride,static_cast<uint8_t*>(out.data)+size_t(row)*out.stride,w);
    auto chroma=static_cast<uint8_t*>(out.data)+size_t(out.stride)*h;
    for(unsigned row=0;row<h/2;++row) memcpy(uv+size_t(row)*uv_stride,chroma+size_t(row)*out.stride,w);
    return true;
  }
};
}
