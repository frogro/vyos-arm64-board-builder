#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
/* Diagnostic only: loaded into this one GNOME Network Displays test process. */
void gst_pipeline_set_latency(void *pipeline, uint64_t latency) {
    static void (*real_set)(void *, uint64_t);
    if (!real_set) real_set = dlsym(RTLD_NEXT, "gst_pipeline_set_latency");
    if (!real_set) abort();
    uint64_t target = latency == UINT64_C(500000000) ? UINT64_C(50000000) : latency;
    fprintf(stderr, "G latency probe: requested=%llu ns applied=%llu ns\n", (unsigned long long)latency, (unsigned long long)target);
    real_set(pipeline, target);
}
