/* Diagnostic only: temporary left/right key events for the consented
 * Steam UI idle/motion comparison. Never preload in normal sessions. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
typedef struct {uint32_t type,reserved;uint64_t timestamp;uint32_t window,which;int32_t scancode;uint32_t key;uint16_t mod,raw;bool down,repeat;} Key;
typedef union {Key key;unsigned char padding[128];} Event;
static double clock_s(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec/1e9;}
int SDL_PeepEvents(Event *e,int n,int action,uint32_t min,uint32_t max){
 int (*real)(Event*,int,int,uint32_t,uint32_t)=dlsym(RTLD_NEXT,"SDL_PeepEvents");
 int r=real(e,n,action,min,max);static int calls;if(calls++<10)fprintf(stderr,"INPUT_CALL n=%d action=%d min=%x max=%x result=%d\n",n,action,min,max,r);if(r||!e||n<1||action!=2)return r;
 void *(*focus)(void)=dlsym(RTLD_NEXT,"SDL_GetKeyboardFocus");
 uint32_t (*wid)(void*)=dlsym(RTLD_NEXT,"SDL_GetWindowID");
 uint64_t (*ticks)(void)=dlsym(RTLD_NEXT,"SDL_GetTicksNS");
 void *w=focus?focus():NULL;
 if(!w){void **(*windows)(int*)=dlsym(RTLD_NEXT,"SDL_GetWindows");void (*free_sdl)(void*)=dlsym(RTLD_NEXT,"SDL_free");int num=0;void **list=windows?windows(&num):NULL;if(num>0)w=list[num-1];if(list)free_sdl(list);if(!w)return false;}
 static double start,last;static int count;double now=clock_s();if(!start)start=now;
 if(now-start<50||count>=60||now-last<.5)return false;
 memset(e,0,sizeof(*e));e->key.type=(count%2)?0x301:0x300;e->key.timestamp=ticks();e->key.window=wid(w);
 e->key.scancode=((count/2)%2)?80:79;e->key.key=0x40000000u|e->key.scancode;e->key.down=!(count%2);
 fprintf(stderr,"INPUT_PROBE seconds=%.2f key=%d down=%d\n",now-start,e->key.scancode,e->key.down);
 count++;last=now;return true;
}
