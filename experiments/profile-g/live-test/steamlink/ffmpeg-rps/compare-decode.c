#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <libavformat/avformat.h>
#include <libavcodec/avcodec.h>
#include <libavutil/hwcontext.h>
#include <libavutil/md5.h>
#include <libavutil/imgutils.h>
#include <libswscale/swscale.h>
static enum AVPixelFormat fmt(AVCodecContext *c,const enum AVPixelFormat *p){(void)c;for(;*p!=AV_PIX_FMT_NONE;p++)if(*p==AV_PIX_FMT_DRM_PRIME)return *p;return AV_PIX_FMT_NONE;}
static int count;
static void output(AVFrame *frame){
 AVFrame *cpu=av_frame_alloc();AVFrame *f=frame;
 if(frame->format==AV_PIX_FMT_DRM_PRIME){int r=av_hwframe_transfer_data(cpu,frame,0);if(r<0){fprintf(stderr,"transfer %d\n",r);exit(4);}f=cpu;}
 uint8_t *buf=av_malloc(f->width*f->height*3/2+128),*dst[4];int strides[4];
 av_image_fill_arrays(dst,strides,buf,AV_PIX_FMT_YUV420P,f->width,f->height,1);
 struct SwsContext *s=sws_getContext(f->width,f->height,f->format,f->width,f->height,AV_PIX_FMT_YUV420P,SWS_POINT,NULL,NULL,NULL);
 if(!s){fprintf(stderr,"sws error fmt=%d\n",f->format);exit(5);}
 sws_scale(s,(const uint8_t*const*)f->data,f->linesize,0,f->height,dst,strides);uint8_t hash[16];av_md5_sum(hash,buf,f->width*f->height*3/2);
 printf("%d ",count++);for(int i=0;i<16;i++)printf("%02x",hash[i]);printf("\n");
 sws_freeContext(s);av_free(buf);av_frame_free(&cpu);
}
int main(int argc,char**argv){
 if(argc!=4)return 2;
 int hw=atoi(argv[2]),max=atoi(argv[3]);AVFormatContext *in=NULL;
 if(avformat_open_input(&in,argv[1],NULL,NULL)<0||avformat_find_stream_info(in,NULL)<0)return 3;
 int idx=av_find_best_stream(in,AVMEDIA_TYPE_VIDEO,-1,-1,NULL,0);if(idx<0)return 3;
 const AVCodec*c=avcodec_find_decoder(in->streams[idx]->codecpar->codec_id);AVCodecContext *ctx=avcodec_alloc_context3(c);avcodec_parameters_to_context(ctx,in->streams[idx]->codecpar);
 if(hw){AVBufferRef *device=NULL;int r=av_hwdevice_ctx_create(&device,AV_HWDEVICE_TYPE_V4L2REQUEST,NULL,NULL,0);if(r<0)return 4;ctx->hw_device_ctx=device;ctx->get_format=fmt;}
 if(avcodec_open2(ctx,c,NULL)<0)return 4;
 AVPacket *p=av_packet_alloc();AVFrame*f=av_frame_alloc();
 while(count<max && av_read_frame(in,p)>=0){if(p->stream_index==idx){int r=avcodec_send_packet(ctx,p);if(r<0){fprintf(stderr,"send %d\n",r);return 6;}while(avcodec_receive_frame(ctx,f)==0){output(f);av_frame_unref(f);if(count>=max)break;}}av_packet_unref(p);}
 if(count<max){avcodec_send_packet(ctx,NULL);while(avcodec_receive_frame(ctx,f)==0){output(f);av_frame_unref(f);}}
 fprintf(stderr,"decoded=%d hardware=%d\n",count,hw);av_frame_free(&f);av_packet_free(&p);avcodec_free_context(&ctx);avformat_close_input(&in);return count?0:7;
}
