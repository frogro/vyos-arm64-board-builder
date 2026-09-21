#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
/* Exact byte-layout conversion only, fixed synthetic 1920x1080 4:2:0 fixture. */
int main(void) {
 const size_t y=1920u*1080u,n=y*3/2,bytes=n*10/8;
 uint16_t *in=malloc(n*sizeof(*in));unsigned char *out=malloc(bytes);
 if(!in||!out)return 2;
 for(;;){
  size_t got=fread(in,sizeof(*in),n,stdin);if(!got)break;if(got!=n)return 3;
  for(size_t i=0,j=0;i<n;i+=4,j+=5){
   uint64_t v=0;
   for(unsigned k=0;k<4;k++){
    size_t idx=i+k,src=idx<y?idx:y+(idx-y)/2+((idx-y)%2)*(y/4);
    if(in[src]>1023)return 4;
    v|=(uint64_t)in[src]<<(10*k);
   }
   for(unsigned k=0;k<5;k++)out[j+k]=(unsigned char)(v>>(8*k));
  }
  if(fwrite(out,1,bytes,stdout)!=bytes)return 5;
 }
 free(in);free(out);return ferror(stdin)||fflush(stdout)?6:0;
}
