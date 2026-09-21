#include "rga-converter.hpp"
#include <vector>
#include <iostream>
#include <cmath>
#include <algorithm>
int main(){
  vyarm::rga_converter rga;
  for(auto dims : {std::pair<unsigned,unsigned>{1920,1080},{1080,1920}})
  for(bool bt709:{false,true}) for(bool full:{false,true}) {
    unsigned w=dims.first,h=dims.second; int stride=w*4+64,ys=w+32;
    std::vector<uint8_t> src(size_t(stride)*h), dst(size_t(ys)*h*3/2);
    unsigned colors[8][3]={{0,0,0},{255,255,255},{255,0,0},{0,255,0},{0,0,255},{255,255,0},{0,255,255},{255,0,255}};
    for(unsigned row=0;row<h;++row) for(unsigned x=0;x<w;++x){auto &c=colors[x*8/w];auto p=src.data()+size_t(row)*stride+x*4;p[0]=c[2];p[1]=c[1];p[2]=c[0];}
    if(rga.convert(nullptr,stride,dst.data(),ys,dst.data()+size_t(ys)*h,ys,w,h,bt709,full)) return 3;
    auto start=std::chrono::steady_clock::now(); int error=0;
    for(int n=0;n<120;++n){
      if(!rga.convert(src.data(),stride,dst.data(),ys,dst.data()+size_t(ys)*h,ys,w,h,bt709,full)){std::cerr<<"conversion failed "<<w<<" "<<bt709<<" "<<full<<" errno "<<errno<<"\n";return 2;}
      for(unsigned i=0;i<8;++i){unsigned x=(i*w/8+w/16)&~1u;auto &c=colors[i];double kr=bt709?.2126:.299,kb=bt709?.0722:.114;double y=kr*c[0]+(1-kr-kb)*c[1]+kb*c[2];
        int expected[3]={int(std::lround(full?y:16+y*219/255)),int(std::lround(128+(c[2]-y)*(full?0.5:112.0/255)/(1-kb))),int(std::lround(128+(c[0]-y)*(full?0.5:112.0/255)/(1-kr)))};
        int actual[3]={dst[size_t(h/2)*ys+x],dst[size_t(ys)*h+size_t(h/4)*ys+x],dst[size_t(ys)*h+size_t(h/4)*ys+x+1]};
        for(int j=0;j<3;++j)error=std::max(error,std::abs(actual[j]-std::clamp(expected[j],0,255)));
      }
    }
    double ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count()/120;
    std::cout<<w<<"x"<<h<<" bt709="<<bt709<<" full="<<full<<" max_error="<<error<<" mean_ms="<<ms<<std::endl;
    if(error>3)return 1;
  }
}
