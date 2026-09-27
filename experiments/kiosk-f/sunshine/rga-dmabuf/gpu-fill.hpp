// SPDX-License-Identifier: GPL-3.0-or-later
// Probe GPU rendering into the RGA-exported linear DMA-BUF. No CPU pixel upload.
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES2/gl2.h>
#include <GLES2/gl2ext.h>
#include <cstdlib>

struct gpu_fill {
  EGLDisplay display=EGL_NO_DISPLAY;
  EGLContext context=EGL_NO_CONTEXT;
  EGLImageKHR image=EGL_NO_IMAGE_KHR;
  GLuint texture=0,fbo=0;
  PFNEGLDESTROYIMAGEKHRPROC destroy_image=nullptr;
  ~gpu_fill() {
    if(context!=EGL_NO_CONTEXT){
      if(fbo)glDeleteFramebuffers(1,&fbo);
      if(texture)glDeleteTextures(1,&texture);
    }
    if(image!=EGL_NO_IMAGE_KHR && destroy_image)destroy_image(display,image);
    if(display!=EGL_NO_DISPLAY){
      eglMakeCurrent(display,EGL_NO_SURFACE,EGL_NO_SURFACE,EGL_NO_CONTEXT);
      if(context!=EGL_NO_CONTEXT)eglDestroyContext(display,context);
      eglTerminate(display);
    }
  }
  void draw(int fd,unsigned w,unsigned h,unsigned storage_w) {
    auto platform=reinterpret_cast<PFNEGLGETPLATFORMDISPLAYEXTPROC>(eglGetProcAddress("eglGetPlatformDisplayEXT"));
    auto create_image=reinterpret_cast<PFNEGLCREATEIMAGEKHRPROC>(eglGetProcAddress("eglCreateImageKHR"));
    destroy_image=reinterpret_cast<PFNEGLDESTROYIMAGEKHRPROC>(eglGetProcAddress("eglDestroyImageKHR"));
    auto target=reinterpret_cast<PFNGLEGLIMAGETARGETTEXTURE2DOESPROC>(eglGetProcAddress("glEGLImageTargetTexture2DOES"));
    need(platform && create_image && destroy_image && target,"EGL entrypoints");
    display=platform(EGL_PLATFORM_SURFACELESS_MESA,EGL_DEFAULT_DISPLAY,nullptr);
    need(display!=EGL_NO_DISPLAY && eglInitialize(display,nullptr,nullptr),"EGL init");
    need(eglBindAPI(EGL_OPENGL_ES_API),"EGL bind");
    const EGLint ca[]={EGL_RENDERABLE_TYPE,EGL_OPENGL_ES2_BIT,EGL_SURFACE_TYPE,EGL_PBUFFER_BIT,EGL_NONE};
    EGLConfig config;EGLint count=0;
    need(eglChooseConfig(display,ca,&config,1,&count) && count==1,"EGL choose");
    const EGLint ctxa[]={EGL_CONTEXT_CLIENT_VERSION,2,EGL_NONE};
    context=eglCreateContext(display,config,EGL_NO_CONTEXT,ctxa);
    need(context!=EGL_NO_CONTEXT && eglMakeCurrent(display,EGL_NO_SURFACE,EGL_NO_SURFACE,context),"EGL context");
    const char *renderer=reinterpret_cast<const char*>(glGetString(GL_RENDERER));
    need(renderer && strstr(renderer,"Mali-G610") && !strstr(renderer,"llvmpipe"),"real GPU required");
    std::cout<<"gpu_renderer="<<renderer<<std::endl;
    // DRM_FORMAT_XRGB8888, linear. fd is allocated/exported by RGA, not KMS AFBC.
    const EGLint attrs[]={EGL_WIDTH,EGLint(storage_w),EGL_HEIGHT,EGLint(h),
      EGL_LINUX_DRM_FOURCC_EXT,0x34325258,EGL_DMA_BUF_PLANE0_FD_EXT,fd,
      EGL_DMA_BUF_PLANE0_OFFSET_EXT,0,EGL_DMA_BUF_PLANE0_PITCH_EXT,EGLint(storage_w*4),
      EGL_DMA_BUF_PLANE0_MODIFIER_LO_EXT,0,EGL_DMA_BUF_PLANE0_MODIFIER_HI_EXT,0,EGL_NONE};
    image=create_image(display,EGL_NO_CONTEXT,EGL_LINUX_DMA_BUF_EXT,nullptr,attrs);
    need(image!=EGL_NO_IMAGE_KHR,"EGL DMA-BUF import");
    glGenTextures(1,&texture);glBindTexture(GL_TEXTURE_2D,texture);
    target(GL_TEXTURE_2D,image);
    glGenFramebuffers(1,&fbo);glBindFramebuffer(GL_FRAMEBUFFER,fbo);
    glFramebufferTexture2D(GL_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_TEXTURE_2D,texture,0);
    need(glCheckFramebufferStatus(GL_FRAMEBUFFER)==GL_FRAMEBUFFER_COMPLETE,"linear DMA-BUF render target");
    paint(w,h,0);
  }
  void paint(unsigned w,unsigned h,unsigned phase) {
    glBindFramebuffer(GL_FRAMEBUFFER,fbo);
    glViewport(0,0,w,h);glEnable(GL_SCISSOR_TEST);
    for(unsigned i=0;i<8;++i){
      unsigned left=i*w/8,right=(i+1)*w/8;
      glScissor(left,0,right-left,h);
      const auto &color=colors[phase?7-i:i];
      glClearColor(color[0]/255.f,color[1]/255.f,color[2]/255.f,1.f);
      glClear(GL_COLOR_BUFFER_BIT);
    }
    // Complete GPU writes before RGA queues input; avoids claiming asynchronous zero-copy.
    glFinish();need(glGetError()==GL_NO_ERROR,"GPU fill");
  }
};
