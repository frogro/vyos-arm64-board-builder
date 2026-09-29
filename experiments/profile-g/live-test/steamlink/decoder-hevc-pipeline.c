#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <time.h>
#include <pthread.h>
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


static pthread_mutex_t rate_lock=PTHREAD_MUTEX_INITIALIZER;
static unsigned long sent,decoded;
static double send_time,receive_time,started,last_report;
static double seconds(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec/1e9;}
int avcodec_send_packet(void *ctx,const void *pkt){
 int (*fn)(void*,const void*)=dlsym(RTLD_NEXT,"avcodec_send_packet");
 double t=seconds();int r=fn(ctx,pkt);double dt=seconds()-t;
 pthread_mutex_lock(&rate_lock);if(!started)started=last_report=seconds();send_time+=dt;if(r==0 && pkt)sent++;pthread_mutex_unlock(&rate_lock);return r;
}
int avcodec_receive_frame(void *ctx,void *frame){
 int (*fn)(void*,void*)=dlsym(RTLD_NEXT,"avcodec_receive_frame");
 double t=seconds();int r=fn(ctx,frame);double now=seconds();
 pthread_mutex_lock(&rate_lock);receive_time+=now-t;if(r==0)decoded++;
 if(started && now-last_report>=5){double interval=now-last_report;fprintf(stderr,"PIPELINE_RATE elapsed=%.3f seconds=%.3f packets=%lu frames=%lu send_ms=%.3f receive_ms=%.3f\n",now-started,interval,sent,decoded,send_time*1000,receive_time*1000);last_report=now;sent=decoded=0;send_time=receive_time=0;}
 pthread_mutex_unlock(&rate_lock);return r;
}
