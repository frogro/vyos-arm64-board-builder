#include <linux/videodev2.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <errno.h>
#include <stdio.h>
#include <unistd.h>
static int trial(int fd,const char *name,unsigned id,void *p,unsigned size,int reject){
 struct v4l2_ext_control c={.id=id,.size=size,.ptr=p};
 struct v4l2_ext_controls cs={.which=V4L2_CTRL_WHICH_CUR_VAL,.count=1,.controls=&c};
 errno=0;int r=ioctl(fd,VIDIOC_TRY_EXT_CTRLS,&cs),e=errno;
 printf("%s result=%d errno=%d expected=%s\n",name,r,e,reject?"EINVAL":"accept");
 return reject ? !(r==-1&&e==EINVAL) : r!=0;
}
int main(int argc,char **argv){
 if(argc!=2)return 2; int fd=open(argv[1],O_RDWR);if(fd<0){perror("open");return 2;}
 struct v4l2_format fmt={.type=V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE};
 fmt.fmt.pix_mp.width=1920;fmt.fmt.pix_mp.height=1080;fmt.fmt.pix_mp.pixelformat=V4L2_PIX_FMT_HEVC_SLICE;
 if(ioctl(fd,VIDIOC_S_FMT,&fmt)){perror("format");return 2;}
 int bad=0;struct v4l2_ctrl_hevc_sps s={0};
 s.chroma_format_idc=1;s.pic_width_in_luma_samples=1920;s.pic_height_in_luma_samples=1080;s.num_short_term_ref_pic_sets=64;
 bad+=trial(fd,"ST64",V4L2_CID_STATELESS_HEVC_SPS,&s,sizeof(s),0);
 s.num_short_term_ref_pic_sets=65;bad+=trial(fd,"ST65",V4L2_CID_STATELESS_HEVC_SPS,&s,sizeof(s),1);
 s.num_short_term_ref_pic_sets=0;s.flags=V4L2_HEVC_SPS_FLAG_LONG_TERM_REF_PICS_PRESENT;s.num_long_term_ref_pics_sps=32;
 bad+=trial(fd,"LT32",V4L2_CID_STATELESS_HEVC_SPS,&s,sizeof(s),0);
 s.num_long_term_ref_pics_sps=33;bad+=trial(fd,"LT33",V4L2_CID_STATELESS_HEVC_SPS,&s,sizeof(s),1);
 struct v4l2_ctrl_hevc_ext_sps_st_rps r={0};r.num_negative_pics=16;
 bad+=trial(fd,"negative16",V4L2_CID_STATELESS_HEVC_EXT_SPS_ST_RPS,&r,sizeof(r),0);
 r.num_negative_pics=17;bad+=trial(fd,"negative17",V4L2_CID_STATELESS_HEVC_EXT_SPS_ST_RPS,&r,sizeof(r),1);
 r.num_negative_pics=0;r.num_positive_pics=17;bad+=trial(fd,"positive17",V4L2_CID_STATELESS_HEVC_EXT_SPS_ST_RPS,&r,sizeof(r),1);
 r.num_negative_pics=8;r.num_positive_pics=8;bad+=trial(fd,"sum16",V4L2_CID_STATELESS_HEVC_EXT_SPS_ST_RPS,&r,sizeof(r),0);
 r.num_positive_pics=9;bad+=trial(fd,"sum17",V4L2_CID_STATELESS_HEVC_EXT_SPS_ST_RPS,&r,sizeof(r),1);
 close(fd);return bad?1:0;
}
