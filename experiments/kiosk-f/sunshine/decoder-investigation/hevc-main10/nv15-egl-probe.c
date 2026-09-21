#include <stdio.h>
#include <stdlib.h>
#include <dlfcn.h>
#include <fcntl.h>
#include <unistd.h>
int main(int argc,char **argv){
 if(argc!=2)return 2;
 void *g=dlopen("libgbm.so.1",RTLD_NOW|RTLD_GLOBAL),*e=dlopen("libEGL.so.1",RTLD_NOW|RTLD_GLOBAL);
 if(!g||!e){fprintf(stderr,"%s\n",dlerror());return 3;}
 void *(*create)(int)=dlsym(g,"gbm_create_device");
 void (*destroy)(void*)=dlsym(g,"gbm_device_destroy");
 void *(*proc)(const char*)=dlsym(e,"eglGetProcAddress");
 unsigned (*init)(void*,int*,int*)=dlsym(e,"eglInitialize");
 unsigned (*term)(void*)=dlsym(e,"eglTerminate");
 const char *(*str)(void*,int)=dlsym(e,"eglQueryString");
 if(!proc)return 4;
 void *(*display)(unsigned,void*,const int*)=proc("eglGetPlatformDisplayEXT");
 unsigned (*query)(void*,int,int*,int*)=proc("eglQueryDmaBufFormatsEXT");
 if(!create||!destroy||!proc||!init||!term||!str||!display||!query)return 4;
 int fd=open(argv[1],O_RDWR|O_CLOEXEC);if(fd<0){perror("open");return 5;}
 void *gbm=create(fd);if(!gbm)return 6;void *d=display(0x31D7,gbm,NULL);int major=0,minor=0,count=0;
 if(!init(d,&major,&minor)){fprintf(stderr,"eglInitialize failed\n");return 7;}
 printf("EGL %d.%d vendor=%s version=%s\n",major,minor,str(d,0x3053),str(d,0x3054));
 if(!query(d,0,NULL,&count)||count<0||count>4096)return 8;
 int *formats=calloc((size_t)count,sizeof(int));int n=0;if(!formats||!query(d,count,formats,&n))return 9;
 unsigned nv15='N'|('V'<<8)|('1'<<16)|('5'<<24);int found=0;
 for(int i=0;i<n;i++)if((unsigned)formats[i]==nv15)found=1;
 printf("format_count=%d NV15=%s\n",n,found?"supported":"absent");
 free(formats);term(d);destroy(gbm);close(fd);return 0;
}
