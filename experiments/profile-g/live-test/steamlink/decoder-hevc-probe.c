#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
typedef struct {const char *name;} Codec;
typedef struct {int pix_fmt,methods,device_type;} Hw;
const Codec *avcodec_find_decoder(int id){
 const Codec *(*fn)(int)=dlsym(RTLD_NEXT,"avcodec_find_decoder");
 const Codec *c=fn(id);fprintf(stderr,"DECODER_TRACE find id=%d name=%s\n",id,c?c->name:"null");return c;
}
const Hw *avcodec_get_hw_config(const Codec *c,int i){
 const Hw *(*fn)(const Codec*,int)=dlsym(RTLD_NEXT,"avcodec_get_hw_config");
 const Hw *h=fn(c,i);fprintf(stderr,"DECODER_TRACE hw codec=%s index=%d device=%d methods=%d fmt=%d\n",c?c->name:"null",i,h?h->device_type:-1,h?h->methods:0,h?h->pix_fmt:-1);return h;
}
int avcodec_open2(void *ctx,const Codec *c,void *opts){
 int (*fn)(void*,const Codec*,void*)=dlsym(RTLD_NEXT,"avcodec_open2");
 int ret=fn(ctx,c,opts);fprintf(stderr,"DECODER_TRACE open codec=%s result=%d\n",c?c->name:"null",ret);return ret;
}
int av_hwdevice_ctx_create(void *ctx,int type,const char *dev,void *opts,int flags){
 int (*fn)(void*,int,const char*,void*,int)=dlsym(RTLD_NEXT,"av_hwdevice_ctx_create");
 if(type==8){fprintf(stderr,"DECODER_TRACE experimental DRM -> V4L2REQUEST\n");type=13;dev=NULL;}
 int ret=fn(ctx,type,dev,opts,flags);fprintf(stderr,"DECODER_TRACE device type=%d result=%d\n",type,ret);return ret;
}

/* Diagnostic only: exact capability-probe call site in Valve ARM64 1.3.32.316. */
FILE *fopen(const char *path,const char *mode){
 FILE *(*fn)(const char*,const char*)=dlsym(RTLD_NEXT,"fopen");
 void *caller=__builtin_return_address(0);Dl_info d;
 if(!strcmp(path,"/proc/cpuinfo") && !strcmp(mode,"r") && dladdr(caller,&d)
    && strstr(d.dli_fname,"/steamlink/bin/shell")
    && (uintptr_t)caller-(uintptr_t)d.dli_fbase==0x1405cc){
  static char revision[]="Revision : 3000\n";
  fprintf(stderr,"HEVC_PROBE scoped Pi revision capability override\n");
  return fmemopen(revision,sizeof(revision)-1,"r");
 }
 return fn(path,mode);
}
