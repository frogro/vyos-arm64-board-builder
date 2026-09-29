#!/usr/bin/env python3
"""Compile extracted real parser function and mapping; not a Chromium build."""
from pathlib import Path
import re,subprocess,tempfile,sys
if len(sys.argv) != 2:
 raise SystemExit('usage: test-parser-conversion.py PATCHED_CHROMIUM_SOURCE')
root=Path(sys.argv[1])
h=(root/'media/parsers/h265_parser.h').read_text()
struct=re.search(r'struct MEDIA_EXPORT H265StRefPicSet \{.*?\n\};',h,re.S).group().replace('MEDIA_EXPORT ','')
s=(root/'media/parsers/h265_parser.cc').read_text();f=s[s.index('H265Parser::Result H265Parser::ParseStRefPicSet('):s.index('H265Parser::Result H265Parser::ParseVuiParameters')]
pre='''#include <array>
#include <vector>
#include <cassert>
#include <iostream>
#include <stdexcept>
#include <cstdint>
#include "media/gpu/v4l2/v4l2_hevc_sps_rps.h"
constexpr int kMaxShortTermRefPicSets=64;
'''+struct+'''
struct H265SPS {
 int num_short_term_ref_pic_sets=2;
 int sps_max_sub_layers_minus1=0;
 std::array<int,7> sps_max_dec_pic_buffering_minus1={15};
 std::array<H265StRefPicSet,64> st_ref_pic_set={};
};
class H265Parser {
 public:
 enum Result{kOk,kInvalidStream};
 std::vector<bool> bits; size_t offset=0;
 bool read(bool* p){if(offset==bits.size())return false;*p=bits[offset++];return true;}
 bool read(int* p){bool b;if(!read(&b))return false;*p=b;return true;}
 bool ue(int* p){int n=0,b;while(true){if(!read(&b))return false;if(b)break;if(++n>30)return false;}int v=1;while(n--){if(!read(&b))return false;v=(v<<1)|b;}*p=v-1;return true;}
 void bit(int v){bits.push_back(v);}
 void enc(int v){unsigned x=v+1,n=0;for(unsigned t=x;t>1;t>>=1)++n;for(unsigned j=0;j<n;++j)bit(0);for(int j=n;j>=0;--j)bit((x>>j)&1);}
 Result ParseStRefPicSet(int,const H265SPS&,H265StRefPicSet*,bool);
};
#define READ_BOOL_OR_RETURN(p) do{if(!read(p))return kInvalidStream;}while(0)
#define READ_UE_OR_RETURN(p) do{if(!ue(p))return kInvalidStream;}while(0)
#define IN_RANGE_OR_RETURN(x,a,b) do{if((x)<(a)||(x)>(b))return kInvalidStream;}while(0)
'''
delegate=(root/'media/gpu/v4l2/v4l2_video_decoder_delegate_h265.cc').read_text()
control=delegate[delegate.index('  auto add_rps_control ='):delegate.index('  if (sps->num_short_term_ref_pic_sets < 0')]
pre += """
#include <linux/videodev2.h>
#include <cerrno>
struct FakeDevice {
 int error=0; unsigned capacity=64; unsigned elem=80;
 int Ioctl(unsigned long, v4l2_query_ext_ctrl* q) {
  if(error){errno=error;return -1;}
  q->elem_size=elem;q->nr_of_dims=1;q->dims[0]=capacity;return 0;
 }
};
void TestControls(){
 FakeDevice device;auto* device_=&device;
 std::vector<v4l2_ext_control> ctrls;
 std::array<v4l2_ctrl_hevc_ext_sps_st_rps,64> payload={};
""" + control + """
 assert(add_rps_control(1,payload,2));assert(ctrls.size()==1);
 assert(ctrls[0].size==160&&ctrls[0].ptr==payload.data());
 ctrls.clear();assert(add_rps_control(1,payload,0)&&ctrls.empty());
 device.error=EINVAL;assert(add_rps_control(1,payload,2)&&ctrls.empty());
 device.error=EIO;assert(!add_rps_control(1,payload,2));
 device.error=0;device.elem=79;assert(!add_rps_control(1,payload,2));
 device.elem=80;device.capacity=1;assert(!add_rps_control(1,payload,2));
 device.capacity=64;assert(!add_rps_control(1,payload,65));
 assert(!add_rps_control(1,payload,-1));
}
"""
main='''
int main(){
 TestControls();
 H265SPS sps; H265Parser p;
 // Explicit RPS: negative deltas -1,-4, positive +2; used bits 1,0,1.
 p.enc(2);p.enc(1);p.enc(0);p.bit(1);p.enc(2);p.bit(0);p.enc(1);p.bit(1);
 auto& a=sps.st_ref_pic_set[0];
 assert(p.ParseStRefPicSet(0,sps,&a,false)==H265Parser::kOk);
 assert(a.delta_poc_s0[0]==-1&&a.delta_poc_s0[1]==-4&&a.delta_poc_s1[0]==2);
 assert(a.delta_poc_s0_minus1[1]==2&&a.delta_poc_s1_minus1[0]==1);
 v4l2_ctrl_hevc_ext_sps_st_rps out;
 assert(media::FillHevcShortTermRps(a,out));
 assert(out.used_by_curr_pic==5&&out.delta_poc_s0_minus1[1]==2);
 // Predicted RPS: delta +1; implied use_delta=1 for used references.
 H265Parser q;q.bit(1);q.bit(0);q.enc(0);
 q.bit(1);q.bit(0);q.bit(1);q.bit(1);q.bit(0);q.bit(0);
 auto& b=sps.st_ref_pic_set[1];
 assert(q.ParseStRefPicSet(1,sps,&b,false)==H265Parser::kOk);
 assert(b.num_negative_pics==1&&b.delta_poc_s0[0]==-3);
 assert(b.num_positive_pics==1&&b.delta_poc_s1[0]==3);
 assert(media::FillHevcShortTermRps(b,out));
 assert(out.flags==1&&out.used_by_curr_pic==5&&out.use_delta_flag==7);
 // Reusing destination must clear raw flags left by predicted RPS.
 H265Parser empty;empty.enc(0);empty.enc(0);
 assert(empty.ParseStRefPicSet(0,sps,&b,false)==H265Parser::kOk);
 assert(media::FillHevcShortTermRps(b,out)&&out.flags==0&&out.used_by_curr_pic==0);
 // Truncated input, excessive DPB and out-of-range UAPI values fail closed.
 H265Parser bad;assert(bad.ParseStRefPicSet(0,sps,&b,false)==H265Parser::kInvalidStream);
 H265Parser excessive;excessive.enc(16);excessive.enc(0);
 assert(excessive.ParseStRefPicSet(0,sps,&b,false)==H265Parser::kInvalidStream);
 a.delta_poc_s0_minus1[0]=32768;assert(!media::FillHevcShortTermRps(a,out));
 a.delta_poc_s0_minus1[0]=0;a.num_negative_pics=17;assert(!media::FillHevcShortTermRps(a,out));
 a.num_negative_pics=2;a.inter_ref_pic_set_prediction_flag=true;a.used_by_curr_pic_flag[32]=true;
 assert(!media::FillHevcShortTermRps(a,out));
 static_assert(sizeof(v4l2_ctrl_hevc_ext_sps_st_rps)==80);
 static_assert(sizeof(v4l2_ctrl_hevc_ext_sps_lt_rps)==4);
 std::cout<<"PASS: actual parser function + RPS conversion, explicit/predicted/reused/truncated/bounds/ABI + mocked control capabilities\\n";
}
'''
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'test.cc').write_text(pre+f+main)
 subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I'+str(root),str(p/'test.cc'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
