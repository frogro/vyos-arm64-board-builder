// SPDX-License-Identifier: GPL-3.0-or-later
// Read-only KMS source. Never changes a CRTC/plane or takes DRM master.
#include <xf86drm.h>
#include <xf86drmMode.h>
#include <memory>
#include <set>
struct kms_source {
  Fd card;
  GLuint program=0;
  explicit kms_source(const char *node) {
    card.fd=open(node,O_RDWR|O_CLOEXEC);need(card.fd>=0,"open DRM card");
    need(drmSetClientCap(card.fd,DRM_CLIENT_CAP_UNIVERSAL_PLANES,1)==0,"universal planes");
  }
  ~kms_source(){if(program)glDeleteProgram(program);}
  GLuint shader(GLenum type,const char *source) {
    GLuint s=glCreateShader(type);glShaderSource(s,1,&source,nullptr);glCompileShader(s);
    GLint good=0;glGetShaderiv(s,GL_COMPILE_STATUS,&good);
    if(!good){char log[1024];glGetShaderInfoLog(s,sizeof(log),nullptr,log);glDeleteShader(s);throw std::runtime_error(log);}
    return s;
  }
  void init_shader() {
    if(program)return;
    GLuint v=shader(GL_VERTEX_SHADER,"attribute vec2 p; varying vec2 uv; void main(){gl_Position=vec4(p,0.,1.);uv=(p+1.)*.5;}");
    GLuint f=shader(GL_FRAGMENT_SHADER,"precision mediump float; varying vec2 uv; uniform sampler2D src; void main(){gl_FragColor=texture2D(src,uv);}");
    program=glCreateProgram();glAttachShader(program,v);glAttachShader(program,f);
    glBindAttribLocation(program,0,"p");glLinkProgram(program);glDeleteShader(v);glDeleteShader(f);
    GLint good=0;glGetProgramiv(program,GL_LINK_STATUS,&good);need(good,"link KMS copy shader");
  }
  void copy(gpu_fill &gpu,unsigned w,unsigned h) {
    init_shader();
    std::unique_ptr<drmModePlaneRes,decltype(&drmModeFreePlaneResources)> planes(drmModeGetPlaneResources(card.fd),drmModeFreePlaneResources);
    need(bool(planes),"get planes");
    uint32_t fb_id=0;
    for(uint32_t i=0;i<planes->count_planes;++i){
      std::unique_ptr<drmModePlane,decltype(&drmModeFreePlane)> p(drmModeGetPlane(card.fd,planes->planes[i]),drmModeFreePlane);
      if(!p || !p->fb_id || !p->crtc_id)continue;
      std::unique_ptr<drmModeObjectProperties,decltype(&drmModeFreeObjectProperties)> props(drmModeObjectGetProperties(card.fd,p->plane_id,DRM_MODE_OBJECT_PLANE),drmModeFreeObjectProperties);
      bool primary=false;
      if(props)for(uint32_t j=0;j<props->count_props;++j){
        std::unique_ptr<drmModePropertyRes,decltype(&drmModeFreeProperty)> prop(drmModeGetProperty(card.fd,props->props[j]),drmModeFreeProperty);
        if(prop && std::string(prop->name)=="type" && props->prop_values[j]==DRM_PLANE_TYPE_PRIMARY)primary=true;
      }
      if(primary){need(fb_id==0,"multiple active primary planes unsupported");fb_id=p->fb_id;}
    }
    need(fb_id!=0,"active primary framebuffer");
    struct Frame {
      int fd;drmModeFB2 *fb;
      ~Frame(){if(fb){std::set<uint32_t> seen;for(auto handle:fb->handles)if(handle && seen.insert(handle).second){drm_gem_close close{};close.handle=handle;ioctl(fd,DRM_IOCTL_GEM_CLOSE,&close);}drmModeFreeFB2(fb);}}
    } frame{card.fd,drmModeGetFB2(card.fd,fb_id)};
    need(frame.fb!=nullptr,"GETFB2");auto &fb=*frame.fb;
    need(fb.width==w && fb.height==h && fb.pixel_format==0x34325258 && fb.handles[0] && !fb.handles[1],"unsupported KMS geometry/format");
    Fd dma;need(drmPrimeHandleToFD(card.fd,fb.handles[0],DRM_CLOEXEC,&dma.fd)==0,"export KMS buffer");
    auto create=reinterpret_cast<PFNEGLCREATEIMAGEKHRPROC>(eglGetProcAddress("eglCreateImageKHR"));
    auto target=reinterpret_cast<PFNGLEGLIMAGETARGETTEXTURE2DOESPROC>(eglGetProcAddress("glEGLImageTargetTexture2DOES"));
    const EGLint attrs[]={EGL_WIDTH,EGLint(w),EGL_HEIGHT,EGLint(h),EGL_LINUX_DRM_FOURCC_EXT,EGLint(fb.pixel_format),
      EGL_DMA_BUF_PLANE0_FD_EXT,dma.fd,EGL_DMA_BUF_PLANE0_OFFSET_EXT,EGLint(fb.offsets[0]),
      EGL_DMA_BUF_PLANE0_PITCH_EXT,EGLint(fb.pitches[0]),EGL_DMA_BUF_PLANE0_MODIFIER_LO_EXT,EGLint(fb.modifier&0xffffffff),
      EGL_DMA_BUF_PLANE0_MODIFIER_HI_EXT,EGLint(fb.modifier>>32),EGL_NONE};
    struct Texture {
      gpu_fill &gpu;EGLImageKHR image=EGL_NO_IMAGE_KHR;GLuint tex=0;
      ~Texture(){if(tex)glDeleteTextures(1,&tex);if(image!=EGL_NO_IMAGE_KHR)gpu.destroy_image(gpu.display,image);}
    } source{gpu};
    source.image=create(gpu.display,EGL_NO_CONTEXT,EGL_LINUX_DMA_BUF_EXT,nullptr,attrs);
    need(source.image!=EGL_NO_IMAGE_KHR,"import KMS modifier");
    glGenTextures(1,&source.tex);glActiveTexture(GL_TEXTURE0);glBindTexture(GL_TEXTURE_2D,source.tex);target(GL_TEXTURE_2D,source.image);
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_NEAREST);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,GL_CLAMP_TO_EDGE);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,GL_CLAMP_TO_EDGE);
    glBindFramebuffer(GL_FRAMEBUFFER,gpu.fbo);glDisable(GL_SCISSOR_TEST);glViewport(0,0,w,h);
    glUseProgram(program);glUniform1i(glGetUniformLocation(program,"src"),0);
    const GLfloat vertices[]={-1,-1,1,-1,-1,1,1,1};
    glVertexAttribPointer(0,2,GL_FLOAT,GL_FALSE,0,vertices);glEnableVertexAttribArray(0);
    glDrawArrays(GL_TRIANGLE_STRIP,0,4);glDisableVertexAttribArray(0);glFinish();
    need(glGetError()==GL_NO_ERROR,"KMS GPU copy");
    static bool reported=false;if(!reported){std::cout<<"kms_fb="<<fb_id<<" modifier=0x"<<std::hex<<fb.modifier<<std::dec<<" pitch="<<fb.pitches[0]<<std::endl;reported=true;}
    // FD/import stay alive through glFinish. Implicit synchronization is used;
    // this does not lock out compositor buffer reuse or prove tear-free capture.
  }
};
