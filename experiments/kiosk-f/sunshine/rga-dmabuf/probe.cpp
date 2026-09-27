// SPDX-License-Identifier: GPL-3.0-or-later
// Standalone feasibility probe, not a Sunshine integration or zero-copy encoder.
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
struct Queue {
  int fd; v4l2_buf_type type; bool active=false;
  ~Queue(){if(active)ctl(fd,VIDIOC_STREAMOFF,&type);}
};
static constexpr auto input=V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE;
static constexpr auto output=V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE;
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
static void queue(int fd,v4l2_buf_type type,size_t length,int dmafd) {
  v4l2_plane plane{}; plane.length=length;
  if(type==input){plane.m.fd=dmafd;plane.bytesused=length;}
  v4l2_buffer b{};b.type=type;b.memory=type==input?V4L2_MEMORY_DMABUF:V4L2_MEMORY_MMAP;
  b.length=1;b.m.planes=&plane;
  need(ctl(fd,VIDIOC_QBUF,&b)==0,"QBUF");
}
static bool dequeue(int fd,v4l2_buf_type type,size_t minimum) {
  v4l2_plane plane{};v4l2_buffer b{};b.type=type;
  b.memory=type==input?V4L2_MEMORY_DMABUF:V4L2_MEMORY_MMAP;b.length=1;b.m.planes=&plane;
  if(ctl(fd,VIDIOC_DQBUF,&b)<0){need(errno==EAGAIN,"DQBUF");return false;}
  need(b.index==0 && !(b.flags&V4L2_BUF_FLAG_ERROR),"bad completed buffer");
  if(type==output)need(plane.data_offset==0 && plane.bytesused>=minimum,"short capture");
  return true;
}
int main(int argc, char **argv) try {
  const bool rga_export=argc==2 && std::string(argv[1])=="rga-export";
  need(argc==1 || rga_export,"usage: probe [rga-export]");
  std::string node=discover();
  bool colors_ok=true;
  for(auto dims:{std::pair<unsigned,unsigned>{1920,1080},{1080,1920}})
  for(bool bt709:{false,true})for(bool full:{false,true}) {
    unsigned w=dims.first,h=dims.second;size_t srcsize=size_t(w)*h*4;
    Fd rga;rga.fd=open(node.c_str(),O_RDWR|O_NONBLOCK|O_CLOEXEC);need(rga.fd>=0,"open RGA");
    v4l2_capability cap{};need(ctl(rga.fd,VIDIOC_QUERYCAP,&cap)==0,"QUERYCAP");
    unsigned caps=(cap.capabilities&V4L2_CAP_DEVICE_CAPS)?cap.device_caps:cap.capabilities;
    need((caps&(V4L2_CAP_VIDEO_M2M_MPLANE|V4L2_CAP_STREAMING))==
         (V4L2_CAP_VIDEO_M2M_MPLANE|V4L2_CAP_STREAMING),"capabilities");
    format(rga.fd,input,w,h,bt709,true,w*4);
    auto outfmt=format(rga.fd,output,w,h,bt709,full,w);
    req(rga.fd,input,V4L2_MEMORY_DMABUF);req(rga.fd,output,V4L2_MEMORY_MMAP);
    Fd allocator,dma;
    if(rga_export) {
      allocator.fd=open(node.c_str(),O_RDWR|O_NONBLOCK|O_CLOEXEC);
      need(allocator.fd>=0,"open source allocator");
      format(allocator.fd,input,w,h,bt709,true,w*4);
      req(allocator.fd,input,V4L2_MEMORY_MMAP);
      v4l2_exportbuffer exp{};exp.type=input;exp.flags=O_RDWR|O_CLOEXEC;
      need(ctl(allocator.fd,VIDIOC_EXPBUF,&exp)==0,"export RGA buffer");
      dma.fd=exp.fd;
    } else {
      allocator.fd=open("/dev/dma_heap/system",O_RDWR|O_CLOEXEC);
      need(allocator.fd>=0,"open heap");
      dma_heap_allocation_data alloc{};alloc.len=srcsize;alloc.fd_flags=O_RDWR|O_CLOEXEC;
      need(ctl(allocator.fd,DMA_HEAP_IOCTL_ALLOC,&alloc)==0,"heap alloc");
      dma.fd=alloc.fd;
    }
    Map src;src.len=srcsize;src.ptr=mmap(nullptr,src.len,PROT_READ|PROT_WRITE,MAP_SHARED,dma.fd,0);
    need(src.ptr!=MAP_FAILED,"source map");
    dma_buf_sync sync{};sync.flags=DMA_BUF_SYNC_START|DMA_BUF_SYNC_WRITE;
    need(ctl(dma.fd,DMA_BUF_IOCTL_SYNC,&sync)==0,"source CPU begin");
    for(unsigned row=0;row<h;++row)for(unsigned x=0;x<w;++x) {
      auto &c=colors[x*8/w];auto p=static_cast<unsigned char*>(src.ptr)+(size_t(row)*w+x)*4;
      p[0]=c[2];p[1]=c[1];p[2]=c[0];p[3]=255;
    }
    sync.flags=DMA_BUF_SYNC_END|DMA_BUF_SYNC_WRITE;
    need(ctl(dma.fd,DMA_BUF_IOCTL_SYNC,&sync)==0,"source CPU end");
    v4l2_plane plane{};v4l2_buffer b{};b.type=output;b.memory=V4L2_MEMORY_MMAP;b.length=1;b.m.planes=&plane;
    need(ctl(rga.fd,VIDIOC_QUERYBUF,&b)==0,"QUERYBUF");
    Map dst;dst.len=plane.length;
    need(dst.len>=outfmt.fmt.pix_mp.plane_fmt[0].sizeimage && dst.len>=size_t(w)*h*3/2,"destination length");
    dst.ptr=mmap(nullptr,dst.len,PROT_READ|PROT_WRITE,MAP_SHARED,rga.fd,plane.m.mem_offset);
    need(dst.ptr!=MAP_FAILED,"destination map");
    // Queues destruct before mappings and source fd, including error paths.
    Queue qi{rga.fd,input},qo{rga.fd,output};
    std::vector<unsigned char> copy(size_t(w)*h*3/2);
    double elapsed=0;int error=0;
    for(int n=0;n<120;++n) {
      auto start=std::chrono::steady_clock::now();
      queue(rga.fd,output,dst.len,-1);queue(rga.fd,input,srcsize,dma.fd);
      for(auto q:{&qo,&qi})if(!q->active){need(ctl(rga.fd,VIDIOC_STREAMON,&q->type)==0,"STREAMON");q->active=true;}
      bool a=false,b=false;auto deadline=start+std::chrono::milliseconds(200);
      while(!(a&&b)) {
        if(!a)a=dequeue(rga.fd,output,copy.size());
        if(!b)b=dequeue(rga.fd,input,0);
        need(std::chrono::steady_clock::now()<deadline,"conversion deadline");
        if(!(a&&b)){pollfd p{rga.fd,POLLIN|POLLOUT,0};need(poll(&p,1,2)>=0 || errno==EINTR,"poll");}
      }
      memcpy(copy.data(),dst.ptr,copy.size());
      elapsed+=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
      for(unsigned i=0;i<8;++i) {
        unsigned x=(i*w/8+w/16)&~1u;auto &c=colors[i];double kr=bt709?.2126:.299,kb=bt709?.0722:.114;
        double y=kr*c[0]+(1-kr-kb)*c[1]+kb*c[2];
        int expected[3]={int(lround(full?y:16+y*219/255)),int(lround(128+(c[2]-y)*(full?.5:112.0/255)/(1-kb))),int(lround(128+(c[0]-y)*(full?.5:112.0/255)/(1-kr)))};
        int actual[3]={copy[size_t(h/2)*w+x],copy[size_t(w)*h+size_t(h/4)*w+x],copy[size_t(w)*h+size_t(h/4)*w+x+1]};
        for(int j=0;j<3;++j)error=std::max(error,std::abs(actual[j]-std::clamp(expected[j],0,255)));
      }
    }
    std::cout<<"allocator="<<(rga_export?"rga-export":"system-heap")<<" "<<w<<"x"<<h<<" bt709="<<bt709<<" full="<<full<<" frames=120 max_error="<<error<<" mean_import_convert_copy_ms="<<elapsed/120<<std::endl;
    colors_ok=colors_ok && error<=3;
  }
  return colors_ok?0:2;
} catch(const std::exception &e){std::cerr<<e.what()<<std::endl;return 1;}
