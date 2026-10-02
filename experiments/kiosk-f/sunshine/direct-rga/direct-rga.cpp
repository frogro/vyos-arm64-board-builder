// SPDX-License-Identifier: GPL-3.0-or-later
#include "direct-rga.hpp"
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES2/gl2.h>
#include <GLES2/gl2ext.h>
#include <linux/videodev2.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <fcntl.h>
#include <unistd.h>
#include <poll.h>
#include <chrono>
#include <cstring>
#include <cerrno>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <vector>
namespace vyarm {
namespace {
constexpr auto input=V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE;
constexpr auto output=V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE;
void require(bool ok,const char *what) {if(!ok)throw std::runtime_error(std::string(what)+": "+strerror(errno));}
int ctl(int fd,unsigned long op,void *p){int r;do{r=ioctl(fd,op,p);}while(r<0 && errno==EINTR);return r;}
struct fd_t {int v=-1; ~fd_t(){if(v>=0)close(v);} };
// Sunshine's existing desktop GL context must be restored even after a failure.
struct context_restore {
 EGLDisplay display=eglGetCurrentDisplay(); EGLContext context=eglGetCurrentContext();
 EGLSurface read=eglGetCurrentSurface(EGL_READ),draw=eglGetCurrentSurface(EGL_DRAW);
 EGLenum api=eglQueryAPI();
 ~context_restore(){auto now=eglGetCurrentDisplay();if(now!=EGL_NO_DISPLAY)eglMakeCurrent(now,EGL_NO_SURFACE,EGL_NO_SURFACE,EGL_NO_CONTEXT);eglBindAPI(api);if(display!=EGL_NO_DISPLAY)eglMakeCurrent(display,draw,read,context);}
};
GLuint shader(GLenum type,const char *src){GLuint s=glCreateShader(type);glShaderSource(s,1,&src,nullptr);glCompileShader(s);GLint ok=0;glGetShaderiv(s,GL_COMPILE_STATUS,&ok);if(!ok){glDeleteShader(s);throw std::runtime_error("GPU shader compilation failed");}return s;}
}
struct direct_rga::impl {
 fd_t device,allocator,dma;
 unsigned width=0,height=0,storage=0; bool bt709=false,full=false,qi=false,qo=false;
 void *mapped=MAP_FAILED;size_t length=0;
 EGLDisplay display=EGL_NO_DISPLAY;EGLContext context=EGL_NO_CONTEXT;
 EGLImageKHR target_image=EGL_NO_IMAGE_KHR;GLuint target_texture=0,fbo=0,program=0;
 PFNEGLCREATEIMAGEKHRPROC create=nullptr;PFNEGLDESTROYIMAGEKHRPROC destroy=nullptr;
 PFNGLEGLIMAGETARGETTEXTURE2DOESPROC bind_image=nullptr;
 ~impl(){
  // Stop DMA before dropping imports or mappings, also on timeout/error.
  if(qi){auto t=input;ctl(device.v,VIDIOC_STREAMOFF,&t);}if(qo){auto t=output;ctl(device.v,VIDIOC_STREAMOFF,&t);}
  if(mapped!=MAP_FAILED)munmap(mapped,length);
  if(context!=EGL_NO_CONTEXT){context_restore restore;if(restore.context==context){restore.context=EGL_NO_CONTEXT;restore.read=restore.draw=EGL_NO_SURFACE;}eglBindAPI(EGL_OPENGL_ES_API);if(eglMakeCurrent(display,EGL_NO_SURFACE,EGL_NO_SURFACE,context)){
   if(program)glDeleteProgram(program);
   if(fbo)glDeleteFramebuffers(1,&fbo);
   if(target_texture)glDeleteTextures(1,&target_texture);
   if(target_image!=EGL_NO_IMAGE_KHR && destroy)destroy(display,target_image);
   eglMakeCurrent(display,EGL_NO_SURFACE,EGL_NO_SURFACE,EGL_NO_CONTEXT);
  }eglDestroyContext(display,context);}
  // EGL displays may be shared with other capture contexts. Do not terminate them.
 }
 void format(int fd,v4l2_buf_type t,unsigned w,unsigned pitch){
  v4l2_format f{};f.type=t;auto &p=f.fmt.pix_mp;p.width=w;p.height=height;p.pixelformat=t==input?V4L2_PIX_FMT_XBGR32:V4L2_PIX_FMT_NV12;
  p.field=V4L2_FIELD_NONE;p.num_planes=1;p.colorspace=bt709?V4L2_COLORSPACE_REC709:V4L2_COLORSPACE_SMPTE170M;
  p.ycbcr_enc=bt709?V4L2_YCBCR_ENC_709:V4L2_YCBCR_ENC_601;p.quantization=t==input||full?V4L2_QUANTIZATION_FULL_RANGE:V4L2_QUANTIZATION_LIM_RANGE;p.plane_fmt[0].bytesperline=pitch;
  auto wanted=p;require(ctl(fd,VIDIOC_S_FMT,&f)==0,"RGA format");
  require(p.width==w && p.height==height && p.pixelformat==wanted.pixelformat && p.num_planes==1 && p.colorspace==wanted.colorspace && p.ycbcr_enc==wanted.ycbcr_enc && p.quantization==wanted.quantization && p.plane_fmt[0].bytesperline==pitch,"RGA negotiated format changed");
 }
 void request(int fd,v4l2_buf_type t,v4l2_memory mem){v4l2_requestbuffers r{};r.type=t;r.memory=mem;r.count=1;require(ctl(fd,VIDIOC_REQBUFS,&r)==0&&r.count>=1,"RGA allocate");}
 void init(unsigned w,unsigned h,bool b,bool f){
  width=w;height=h;storage=(w+15)&~15u;bt709=b;full=f;
  // This tested driver gates corrected matrix/range handling by HW revision.
  std::ifstream csc("/sys/module/rockchip_rga/parameters/experimental_full_csc");char enabled=0;csc>>enabled;
  require(enabled=='Y'||enabled=='1',"RGA corrected CSC is not enabled");
  std::string node;for(auto &e:std::filesystem::directory_iterator("/sys/class/video4linux")){std::ifstream n(e.path()/"name");std::string v;getline(n,v);if(v=="rockchip-rga"){node="/dev/"+e.path().filename().string();break;}}
  require(!node.empty(),"RGA device missing");device.v=open(node.c_str(),O_RDWR|O_NONBLOCK|O_CLOEXEC);require(device.v>=0,"open RGA");
  v4l2_capability cap{};require(ctl(device.v,VIDIOC_QUERYCAP,&cap)==0,"RGA capabilities");unsigned caps=cap.capabilities&V4L2_CAP_DEVICE_CAPS?cap.device_caps:cap.capabilities;
  require((caps&(V4L2_CAP_VIDEO_M2M_MPLANE|V4L2_CAP_STREAMING))==(V4L2_CAP_VIDEO_M2M_MPLANE|V4L2_CAP_STREAMING),"RGA M2M streaming required");
  format(device.v,input,storage,storage*4);v4l2_selection crop{};crop.type=input;crop.target=V4L2_SEL_TGT_CROP;crop.r.width=width;crop.r.height=height;
  require(ctl(device.v,VIDIOC_S_SELECTION,&crop)==0 && crop.r.left==0 && crop.r.top==0 && crop.r.width==width && crop.r.height==height,"RGA crop");
  format(device.v,output,width,width);request(device.v,input,V4L2_MEMORY_DMABUF);request(device.v,output,V4L2_MEMORY_MMAP);
  allocator.v=open(node.c_str(),O_RDWR|O_NONBLOCK|O_CLOEXEC);require(allocator.v>=0,"RGA source allocator");format(allocator.v,input,storage,storage*4);request(allocator.v,input,V4L2_MEMORY_MMAP);
  v4l2_exportbuffer e{};e.type=input;e.flags=O_RDWR|O_CLOEXEC;require(ctl(allocator.v,VIDIOC_EXPBUF,&e)==0,"RGA source export");dma.v=e.fd;
  v4l2_plane plane{};v4l2_buffer buffer{};buffer.type=output;buffer.memory=V4L2_MEMORY_MMAP;buffer.length=1;buffer.m.planes=&plane;
  require(ctl(device.v,VIDIOC_QUERYBUF,&buffer)==0,"RGA query output");length=plane.length;require(length>=size_t(width)*height*3/2,"RGA output size");mapped=mmap(nullptr,length,PROT_READ|PROT_WRITE,MAP_SHARED,device.v,plane.m.mem_offset);require(mapped!=MAP_FAILED,"RGA output map");
  auto platform=reinterpret_cast<PFNEGLGETPLATFORMDISPLAYEXTPROC>(eglGetProcAddress("eglGetPlatformDisplayEXT"));
  create=reinterpret_cast<PFNEGLCREATEIMAGEKHRPROC>(eglGetProcAddress("eglCreateImageKHR"));destroy=reinterpret_cast<PFNEGLDESTROYIMAGEKHRPROC>(eglGetProcAddress("eglDestroyImageKHR"));bind_image=reinterpret_cast<PFNGLEGLIMAGETARGETTEXTURE2DOESPROC>(eglGetProcAddress("glEGLImageTargetTexture2DOES"));require(platform&&create&&destroy&&bind_image,"GPU DMA-BUF entrypoints");
  display=platform(EGL_PLATFORM_SURFACELESS_MESA,EGL_DEFAULT_DISPLAY,nullptr);require(display!=EGL_NO_DISPLAY&&eglInitialize(display,nullptr,nullptr),"GPU display");require(eglBindAPI(EGL_OPENGL_ES_API),"GLES API");
  EGLint attrs[]={EGL_RENDERABLE_TYPE,EGL_OPENGL_ES2_BIT,EGL_SURFACE_TYPE,EGL_PBUFFER_BIT,EGL_NONE};EGLConfig config;EGLint n=0;require(eglChooseConfig(display,attrs,&config,1,&n)&&n==1,"GPU config");EGLint ca[]={EGL_CONTEXT_CLIENT_VERSION,2,EGL_NONE};context=eglCreateContext(display,config,EGL_NO_CONTEXT,ca);require(context!=EGL_NO_CONTEXT&&eglMakeCurrent(display,EGL_NO_SURFACE,EGL_NO_SURFACE,context),"GPU context");
  const char *renderer=reinterpret_cast<const char*>(glGetString(GL_RENDERER));require(renderer && !strstr(renderer,"llvmpipe") && !strstr(renderer,"softpipe"),"hardware GPU required");
  EGLint ta[]={EGL_WIDTH,EGLint(storage),EGL_HEIGHT,EGLint(height),EGL_LINUX_DRM_FOURCC_EXT,0x34325258,EGL_DMA_BUF_PLANE0_FD_EXT,dma.v,EGL_DMA_BUF_PLANE0_OFFSET_EXT,0,EGL_DMA_BUF_PLANE0_PITCH_EXT,EGLint(storage*4),EGL_DMA_BUF_PLANE0_MODIFIER_LO_EXT,0,EGL_DMA_BUF_PLANE0_MODIFIER_HI_EXT,0,EGL_NONE};
  target_image=create(display,EGL_NO_CONTEXT,EGL_LINUX_DMA_BUF_EXT,nullptr,ta);require(target_image!=EGL_NO_IMAGE_KHR,"GPU linear target import");glGenTextures(1,&target_texture);glBindTexture(GL_TEXTURE_2D,target_texture);bind_image(GL_TEXTURE_2D,target_image);glGenFramebuffers(1,&fbo);glBindFramebuffer(GL_FRAMEBUFFER,fbo);glFramebufferTexture2D(GL_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_TEXTURE_2D,target_texture,0);require(glCheckFramebufferStatus(GL_FRAMEBUFFER)==GL_FRAMEBUFFER_COMPLETE,"GPU target framebuffer");
  GLuint v=shader(GL_VERTEX_SHADER,"attribute vec2 p; varying vec2 uv; uniform vec4 crop; uniform int rotation; void main(){gl_Position=vec4(p,0.,1.);vec2 q=(p+1.)*.5;if(rotation==90)q=vec2(q.y,1.-q.x);else if(rotation==180)q=vec2(1.-q.x,1.-q.y);else if(rotation==270)q=vec2(1.-q.y,q.x);uv=q*crop.zw+crop.xy;}");
  GLuint fs=shader(GL_FRAGMENT_SHADER,"precision mediump float; varying vec2 uv; uniform sampler2D src; void main(){gl_FragColor=texture2D(src,uv);}");program=glCreateProgram();glAttachShader(program,v);glAttachShader(program,fs);glBindAttribLocation(program,0,"p");glLinkProgram(program);glDeleteShader(v);glDeleteShader(fs);GLint linked=0;glGetProgramiv(program,GL_LINK_STATUS,&linked);require(linked,"GPU copy shader link");
 }
 void draw(GLuint tex,int x,int y,int w,int h,float u,float v,float du,float dv,unsigned rotation=0){
  glBindFramebuffer(GL_FRAMEBUFFER,fbo);glDisable(GL_SCISSOR_TEST);glViewport(x,y,w,h);glActiveTexture(GL_TEXTURE0);glBindTexture(GL_TEXTURE_2D,tex);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_NEAREST);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_NEAREST);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,GL_CLAMP_TO_EDGE);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,GL_CLAMP_TO_EDGE);glUseProgram(program);glUniform1i(glGetUniformLocation(program,"src"),0);glUniform4f(glGetUniformLocation(program,"crop"),u,v,du,dv);glUniform1i(glGetUniformLocation(program,"rotation"),rotation);
  const GLfloat vertices[]={-1,-1,1,-1,-1,1,1,1};glVertexAttribPointer(0,2,GL_FLOAT,GL_FALSE,0,vertices);glEnableVertexAttribArray(0);glDrawArrays(GL_TRIANGLE_STRIP,0,4);glDisableVertexAttribArray(0);
 }
 void gpu_copy(const direct_surface &s,int x,int y,const direct_cursor &cursor,unsigned rotation){
  require(eglBindAPI(EGL_OPENGL_ES_API)&&eglMakeCurrent(display,EGL_NO_SURFACE,EGL_NO_SURFACE,context),"GPU context restore");
  EGLint a[]={EGL_WIDTH,s.width,EGL_HEIGHT,s.height,EGL_LINUX_DRM_FOURCC_EXT,EGLint(s.format),EGL_DMA_BUF_PLANE0_FD_EXT,s.fd,EGL_DMA_BUF_PLANE0_OFFSET_EXT,EGLint(s.offset),EGL_DMA_BUF_PLANE0_PITCH_EXT,EGLint(s.pitch),EGL_DMA_BUF_PLANE0_MODIFIER_LO_EXT,EGLint(s.modifier&0xffffffff),EGL_DMA_BUF_PLANE0_MODIFIER_HI_EXT,EGLint(s.modifier>>32),EGL_NONE};
  struct imported{impl &owner;EGLImageKHR image=EGL_NO_IMAGE_KHR;GLuint texture=0,cursor=0;~imported(){if(cursor)glDeleteTextures(1,&cursor);if(texture)glDeleteTextures(1,&texture);if(image!=EGL_NO_IMAGE_KHR)owner.destroy(owner.display,image);}} source{*this};
  source.image=create(display,EGL_NO_CONTEXT,EGL_LINUX_DMA_BUF_EXT,nullptr,a);require(source.image!=EGL_NO_IMAGE_KHR,"GPU source modifier import");glGenTextures(1,&source.texture);glBindTexture(GL_TEXTURE_2D,source.texture);bind_image(GL_TEXTURE_2D,source.image);glDisable(GL_BLEND);draw(source.texture,0,0,width,height,float(x)/s.width,float(y)/s.height,float(rotation%180?height:width)/s.width,float(rotation%180?width:height)/s.height,rotation);
  if(cursor.bgra && cursor.width && cursor.height){
   require(cursor.width<=1024 && cursor.height<=1024,"cursor size");std::vector<uint8_t> rgba(size_t(cursor.width)*cursor.height*4);
   for(size_t i=0;i<rgba.size();i+=4){rgba[i]=cursor.bgra[i+2];rgba[i+1]=cursor.bgra[i+1];rgba[i+2]=cursor.bgra[i];rgba[i+3]=cursor.bgra[i+3];}
   glGenTextures(1,&source.cursor);glBindTexture(GL_TEXTURE_2D,source.cursor);glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA,cursor.width,cursor.height,0,GL_RGBA,GL_UNSIGNED_BYTE,rgba.data());glEnable(GL_BLEND);glBlendFunc(GL_ONE,GL_ONE_MINUS_SRC_ALPHA);int cx=cursor.x,cy=cursor.y;unsigned cw=cursor.width,ch=cursor.height;
   if(rotation==90){cx=int(width)-cursor.y-int(cursor.height);cy=cursor.x;cw=cursor.height;ch=cursor.width;}
   else if(rotation==180){cx=int(width)-cursor.x-int(cursor.width);cy=int(height)-cursor.y-int(cursor.height);}
   else if(rotation==270){cx=cursor.y;cy=int(height)-cursor.x-int(cursor.width);cw=cursor.height;ch=cursor.width;}
   draw(source.cursor,cx,cy,cw,ch,0,0,1,1,rotation);glDisable(GL_BLEND);
  }
  glFinish();require(glGetError()==GL_NO_ERROR,"GPU render/completion");
  // Borrowed KMS DMA-BUF and imported texture live through completion. As in
  // upstream KMS capture, producer synchronization uses implicit DMA-BUF fences.
 }
 void convert(uint8_t *dest){
  auto queue=[&](v4l2_buf_type t){v4l2_plane p{};p.length=t==input?size_t(storage)*height*4:length;if(t==input){p.m.fd=dma.v;p.bytesused=p.length;}v4l2_buffer b{};b.type=t;b.memory=t==input?V4L2_MEMORY_DMABUF:V4L2_MEMORY_MMAP;b.length=1;b.m.planes=&p;require(ctl(device.v,VIDIOC_QBUF,&b)==0,"RGA queue");};
  queue(output);queue(input);if(!qo){auto t=output;require(ctl(device.v,VIDIOC_STREAMON,&t)==0,"RGA output start");qo=true;}if(!qi){auto t=input;require(ctl(device.v,VIDIOC_STREAMON,&t)==0,"RGA input start");qi=true;}
  bool a=false,b=false;auto deadline=std::chrono::steady_clock::now()+std::chrono::milliseconds(200);
  auto dequeue=[&](v4l2_buf_type t,bool &done){if(done)return;v4l2_plane p{};v4l2_buffer v{};v.type=t;v.memory=t==input?V4L2_MEMORY_DMABUF:V4L2_MEMORY_MMAP;v.length=1;v.m.planes=&p;int r=ctl(device.v,VIDIOC_DQBUF,&v);if(r<0){require(errno==EAGAIN,"RGA dequeue");return;}require(v.index==0 && !(v.flags&V4L2_BUF_FLAG_ERROR),"RGA buffer error");if(t==output)require(p.data_offset==0&&p.bytesused>=size_t(width)*height*3/2,"RGA short output");done=true;};
  while(!(a&&b)){dequeue(output,a);dequeue(input,b);require(std::chrono::steady_clock::now()<deadline,"RGA conversion timeout");if(!(a&&b)){pollfd p{device.v,POLLIN|POLLOUT,0};int n=poll(&p,1,2);require(n>=0||errno==EINTR,"RGA wait");}}
  memcpy(dest,mapped,size_t(width)*height*3/2);
 }
};
direct_rga::direct_rga()=default;
direct_rga::~direct_rga()=default;
bool direct_rga::capture(const direct_surface &s,int x,int y,unsigned w,unsigned h,bool b,bool f,const direct_cursor &cursor,uint8_t *dest,std::string &error,unsigned rotation){
 context_restore restore;
 try {
  require(rotation==0||rotation==90||rotation==180||rotation==270,"unsupported rotation");
  unsigned source_w=rotation%180?h:w,source_h=rotation%180?w:h;
  require(dest&&s.fd>=0&&s.format==0x34325258&&w&&h&&w<=4096&&h<=4096&&!((w|h)&1)&&x>=0&&y>=0&&s.width>=int(source_w)&&s.height>=int(source_h)&&x<=s.width-int(source_w)&&y<=s.height-int(source_h),"unsupported direct capture geometry/format");
  if(!state||state->width!=w||state->height!=h||state->bt709!=b||state->full!=f){state.reset();state=std::make_unique<impl>();state->init(w,h,b,f);}
  std::ifstream csc("/sys/module/rockchip_rga/parameters/experimental_full_csc");char enabled=0;csc>>enabled;
  require(enabled=='Y'||enabled=='1',"RGA corrected CSC disabled during capture");
  state->gpu_copy(s,x,y,cursor,rotation);state->convert(dest);return true;
 }catch(const std::exception &e){error=e.what();state.reset();return false;}
}
}
