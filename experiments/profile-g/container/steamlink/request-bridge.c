/* Private Steam Link 1.3.32.316 adapter; never install via ld.so.preload.
 * The wrapper verifies the executable and private FFmpeg before enabling it.
 * HEVC capability override is limited to the observed, pinned call site. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <libavutil/hwcontext.h>
_Static_assert(AV_HWDEVICE_TYPE_DRM == 8, "unexpected FFmpeg DRM ABI");
_Static_assert(AV_HWDEVICE_TYPE_V4L2REQUEST == 13, "unexpected request ABI");
int av_hwdevice_ctx_create(AVBufferRef **ctx, enum AVHWDeviceType type,
                          const char *dev, AVDictionary *opts, int flags) {
    int (*fn)(AVBufferRef **, enum AVHWDeviceType, const char *, AVDictionary *, int)
        = dlsym(RTLD_NEXT, "av_hwdevice_ctx_create");
    if (!fn) return -38;
    if (type == AV_HWDEVICE_TYPE_DRM) { type = AV_HWDEVICE_TYPE_V4L2REQUEST; dev = NULL; }
    return fn(ctx, type, dev, opts, flags);
}
FILE *fopen(const char *path, const char *mode) {
    FILE *(*fn)(const char *, const char *) = dlsym(RTLD_NEXT, "fopen");
    void *caller = __builtin_return_address(0); Dl_info d;
    if (getenv("G_STEAMLINK_HEVC") && !strcmp(path, "/proc/cpuinfo") && !strcmp(mode, "r")
        && dladdr(caller, &d) && strstr(d.dli_fname, "/steamlink/bin/shell")
        && (uintptr_t)caller - (uintptr_t)d.dli_fbase == 0x1405cc) {
        static const char revision[] = "Revision : 3000\n";
        /* A private copy also makes simultaneous callers independent. */
        FILE *f = tmpfile();
        if (!f) return NULL;
        fwrite(revision, 1, sizeof(revision)-1, f); rewind(f); return f;
    }
    return fn ? fn(path, mode) : NULL;
}
