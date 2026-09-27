// SPDX-License-Identifier: GPL-3.0-or-later
// Exercise the actual direct capture helper with exported, mutable DMA-BUFs.
// Streaming and KMS source selection require separate integration tests.
#include <linux/dma-heap.h>
#include <linux/dma-buf.h>
#include <linux/videodev2.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <fcntl.h>
#include <unistd.h>
#include <poll.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstring>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

static void need(bool good, const char *message) {
  if (!good) throw std::runtime_error(std::string(message)+": "+strerror(errno));
}
static int ctl(int fd, unsigned long op, void *arg) {
  int ret; do {ret=ioctl(fd,op,arg);} while(ret<0 && errno==EINTR); return ret;
}
struct Fd {int fd=-1; ~Fd(){if(fd>=0)close(fd);} };
struct Map {void *ptr=MAP_FAILED; size_t len=0; ~Map(){if(ptr!=MAP_FAILED)munmap(ptr,len);} };
static constexpr auto input=V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE;
static unsigned colors[8][3]={{0,0,0},{255,255,255},{255,0,0},{0,255,0},
  {0,0,255},{255,255,0},{0,255,255},{255,0,255}};
static std::string discover() {
  for(auto &e:std::filesystem::directory_iterator("/sys/class/video4linux")) {
    std::ifstream file(e.path()/"name"); std::string name; getline(file,name);
    if(name=="rockchip-rga") return "/dev/"+e.path().filename().string();
  }
  throw std::runtime_error("No rockchip-rga node");
}
static v4l2_format format(int fd,v4l2_buf_type type,unsigned w,unsigned h,
                           bool bt709,bool full,unsigned pitch) {
  v4l2_format f{}; f.type=type; auto &p=f.fmt.pix_mp;
  p.width=w; p.height=h; p.pixelformat=type==input?V4L2_PIX_FMT_XBGR32:V4L2_PIX_FMT_NV12;
  p.field=V4L2_FIELD_NONE; p.num_planes=1;
  p.colorspace=bt709?V4L2_COLORSPACE_REC709:V4L2_COLORSPACE_SMPTE170M;
  p.ycbcr_enc=bt709?V4L2_YCBCR_ENC_709:V4L2_YCBCR_ENC_601;
  p.quantization=(type==input || full)?V4L2_QUANTIZATION_FULL_RANGE:V4L2_QUANTIZATION_LIM_RANGE;
  p.plane_fmt[0].bytesperline=pitch;
  auto requested=p;
  need(ctl(fd,VIDIOC_S_FMT,&f)==0,"S_FMT");
  need(p.width==w && p.height==h && p.pixelformat==requested.pixelformat &&
       p.num_planes==1 && p.colorspace==requested.colorspace &&
       p.ycbcr_enc==requested.ycbcr_enc && p.quantization==requested.quantization &&
       p.plane_fmt[0].bytesperline==pitch,"format changed");
  return f;
}
static void req(int fd,v4l2_buf_type type,v4l2_memory memory) {
  v4l2_requestbuffers r{};r.type=type;r.memory=memory;r.count=1;
  need(ctl(fd,VIDIOC_REQBUFS,&r)==0 && r.count>=1,"REQBUFS");
}
#include "direct-rga.hpp"
int main() try {
 vyarm::direct_rga converter;
 unsigned cases=0;
 for(auto dims:{std::pair<unsigned,unsigned>{1920,1080},{1080,1920}})
 for(bool bt709:{false,true})for(bool full:{false,true}) {
  unsigned w=dims.first,h=dims.second,storage=(w+15)&~15u;auto node=discover();
  Fd allocator,dma;allocator.fd=open(node.c_str(),O_RDWR|O_NONBLOCK|O_CLOEXEC);need(allocator.fd>=0,"open allocator");
  format(allocator.fd,input,storage,h,true,true,storage*4);req(allocator.fd,input,V4L2_MEMORY_MMAP);
  v4l2_exportbuffer exp{};exp.type=input;exp.flags=O_RDWR|O_CLOEXEC;need(ctl(allocator.fd,VIDIOC_EXPBUF,&exp)==0,"export");dma.fd=exp.fd;
  Map src;src.len=size_t(storage)*h*4;src.ptr=mmap(nullptr,src.len,PROT_READ|PROT_WRITE,MAP_SHARED,dma.fd,0);need(src.ptr!=MAP_FAILED,"map");
  std::vector<uint8_t> nv12(size_t(w)*h*3/2),cursor(16*16*4,255);
  vyarm::direct_surface surface{dma.fd,int(storage),int(h),0x34325258,storage*4,0,0};
  std::string error;auto bad=surface;bad.format=0;
  need(!converter.capture(bad,0,0,w,h,bt709,full,{},nv12.data(),error),"reject unsupported format");
  need(!converter.capture(surface,0,0,w,h,bt709,full,{},nv12.data(),error,45),"reject non-quarter rotation");
  int max_error=0;
  for(unsigned phase=0;phase<3;++phase) {
   dma_buf_sync sync{};sync.flags=DMA_BUF_SYNC_START|DMA_BUF_SYNC_WRITE;need(ctl(dma.fd,DMA_BUF_IOCTL_SYNC,&sync)==0,"CPU begin");
   for(unsigned y=0;y<h;++y)for(unsigned x=0;x<w;++x){auto &c=colors[y<h/8 ? 7 : (x*8/w+phase)%8];auto p=static_cast<uint8_t*>(src.ptr)+(size_t(y)*storage+x)*4;p[0]=c[2];p[1]=c[1];p[2]=c[0];p[3]=255;}
   sync.flags=DMA_BUF_SYNC_END|DMA_BUF_SYNC_WRITE;need(ctl(dma.fd,DMA_BUF_IOCTL_SYNC,&sync)==0,"CPU end");
   need(converter.capture(surface,0,0,w,h,bt709,full,{cursor.data(),16,16,32,32},nv12.data(),error),error.c_str());
   need(std::abs(int(nv12[40*w+40])-(full?255:235))<=1,"cursor composition");
   double marker=(bt709?.2126+.0722:.299+.114)*255;
   need(std::abs(int(nv12[size_t(h/16)*w+w/2])-int(lround(full?marker:16+marker*219/255)))<=1,"top marker orientation");
   for(unsigned i=0;i<8;++i){unsigned x=(i*w/8+w/16)&~1u;auto &c=colors[(i+phase)%8];double kr=bt709?.2126:.299,kb=bt709?.0722:.114;double y=kr*c[0]+(1-kr-kb)*c[1]+kb*c[2];
    int expected[3]={int(lround(full?y:16+y*219/255)),int(lround(128+(c[2]-y)*(full?.5:112.0/255)/(1-kb))),int(lround(128+(c[0]-y)*(full?.5:112.0/255)/(1-kr)))};
    int actual[3]={nv12[size_t(h/2)*w+x],nv12[size_t(w)*h+size_t(h/4)*w+x],nv12[size_t(w)*h+size_t(h/4)*w+x+1]};
    for(int j=0;j<3;++j)max_error=std::max(max_error,std::abs(actual[j]-std::clamp(expected[j],0,255)));
   }
  }
  auto baseline=nv12;
  for(unsigned rotation:{90u,180u,270u}) {
   unsigned rw=rotation%180?h:w,rh=rotation%180?w:h;
   need(converter.capture(surface,0,0,rw,rh,bt709,full,{cursor.data(),16,16,32,32},nv12.data(),error,rotation),error.c_str());
   int rotation_error=0;
   // Pixel-centre reference includes asymmetric top marker and cursor.
   auto compare=[&](unsigned sx,unsigned sy){
    unsigned dx=sx,dy=sy;
    if(rotation==90){dx=h-1-sy;dy=sx;}
    if(rotation==180){dx=w-1-sx;dy=h-1-sy;}
    if(rotation==270){dx=sy;dy=w-1-sx;}
    rotation_error=std::max(rotation_error,std::abs(int(baseline[size_t(sy)*w+sx])-int(nv12[size_t(dy)*rw+dx])));
    for(unsigned channel=0;channel<2;++channel)
     rotation_error=std::max(rotation_error,std::abs(int(baseline[size_t(w)*h+(sy/2)*w+(sx&~1u)+channel])-int(nv12[size_t(rw)*rh+(dy/2)*rw+(dx&~1u)+channel])));
   };
   for(unsigned sy=16;sy<h;sy+=32)for(unsigned sx=16;sx<w;sx+=32)compare(sx,sy);
   compare(40,40);
   need(rotation_error<=3,"rotation reference mismatch");
   std::cout<<"rotation="<<rotation<<" output="<<rw<<"x"<<rh<<" max_error="<<rotation_error<<std::endl;
  }
  need(max_error<=3,"color mismatch");++cases;std::cout<<w<<"x"<<h<<" bt709="<<bt709<<" full="<<full<<" max_error="<<max_error<<" cursor=pass orientation=pass recovery=pass"<<std::endl;
 }
 std::cout<<"DIRECT_RGA_TEST_OK cases="<<cases<<std::endl;
} catch(const std::exception &e){std::cerr<<e.what()<<std::endl;return 1;}
