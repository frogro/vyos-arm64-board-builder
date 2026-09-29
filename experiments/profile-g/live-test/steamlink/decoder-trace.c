#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
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
 int ret=fn(ctx,type,dev,opts,flags);fprintf(stderr,"DECODER_TRACE device type=%d result=%d\n",type,ret);return ret;
}
