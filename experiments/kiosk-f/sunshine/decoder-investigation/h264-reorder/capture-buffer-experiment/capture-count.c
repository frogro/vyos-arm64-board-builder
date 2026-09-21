/* Test-only Linux ioctl interposer. No production installation. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <linux/videodev2.h>
#include <sys/ioctl.h>
#include <errno.h>
int ioctl(int fd, unsigned long request, ...) {
  va_list args;
  va_start(args, request);
  void *arg = va_arg(args, void *);
  va_end(args);
  int (*real_ioctl)(int, unsigned long, ...) = dlsym(RTLD_NEXT, "ioctl");
  if (!real_ioctl) { errno = ENOSYS; return -1; }
  if ((unsigned int)request == (unsigned int)VIDIOC_REQBUFS && arg) {
    struct v4l2_requestbuffers *b = arg;
    const char *setting = getenv("VYARM_CAPTURE_COUNT");
    unsigned count = setting ? (unsigned)strtoul(setting, NULL, 10) : 0;
    const char *extra_setting = getenv("VYARM_CAPTURE_EXTRA");
    unsigned extra = extra_setting ? (unsigned)strtoul(extra_setting, NULL, 10) : 0;
    char path[64], target[256];
    snprintf(path, sizeof(path), "/proc/self/fd/%d", fd);
    ssize_t n = readlink(path, target, sizeof(target)-1);
    if (n >= 0) target[n] = 0;
    const char *dev = getenv("VYARM_DECODER_DEVICE");
    if (n >= 0 && dev && !strcmp(dev,target) &&
        b->type == V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE &&
        b->memory == V4L2_MEMORY_MMAP && b->count > 0 && b->count <= 32) {
      unsigned requested = b->count;
      if (extra >= 1 && extra <= 8 && requested <= 32-extra) count = requested+extra;
      else if (!(requested == 6 && (count == 8 || count == 12))) count = requested;
      struct v4l2_requestbuffers copy = *b;
      copy.count = count;
      int ret = real_ioctl(fd, request, &copy);
      int saved_errno = errno;
      fprintf(stderr,"VYARM_CAPTURE requested=%u override=%u returned=%u result=%d\n",requested,count,copy.count,ret);
      if (ret == 0) *b = copy;
      errno = saved_errno;
      return ret;
    }
  }
  return real_ioctl(fd, request, arg);
}
