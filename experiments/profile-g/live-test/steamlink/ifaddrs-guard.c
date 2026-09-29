/* Steam Link-only LD_PRELOAD workaround: omit addressless getifaddrs records.
 * Keep the original allocation intact for libc freeifaddrs. Never change the
 * host interface or load this library globally. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <ifaddrs.h>
#include <pthread.h>
#include <stdlib.h>

static int (*real_get)(struct ifaddrs **);
static void (*real_free)(struct ifaddrs *);
static pthread_once_t once = PTHREAD_ONCE_INIT;
static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
struct allocation {
    struct allocation *next;
    struct ifaddrs *original;
    struct ifaddrs nodes[];
};
static struct allocation *allocations;
static void resolve(void) {
    real_get = dlsym(RTLD_NEXT, "getifaddrs");
    real_free = dlsym(RTLD_NEXT, "freeifaddrs");
}
int getifaddrs(struct ifaddrs **out) {
    pthread_once(&once, resolve);
    if (!real_get || !real_free) { errno = ENOSYS; return -1; }
    struct ifaddrs *original = NULL;
    int result = real_get(&original);
    if (result) return result;
    size_t count = 0;
    for (struct ifaddrs *p = original; p; p = p->ifa_next)
        if (p->ifa_addr) count++;
    if (!count) { real_free(original); *out = NULL; return 0; }
    struct allocation *a = calloc(1, sizeof(*a) + count * sizeof(a->nodes[0]));
    if (!a) { real_free(original); errno = ENOMEM; return -1; }
    a->original = original;
    size_t i = 0;
    for (struct ifaddrs *p = original; p; p = p->ifa_next) {
        if (!p->ifa_addr) continue;
        a->nodes[i] = *p;
        a->nodes[i].ifa_next = i + 1 < count ? &a->nodes[i+1] : NULL;
        i++;
    }
    pthread_mutex_lock(&lock);
    a->next = allocations;
    allocations = a;
    pthread_mutex_unlock(&lock);
    *out = a->nodes;
    return 0;
}
void freeifaddrs(struct ifaddrs *head) {
    if (!head) return;
    pthread_once(&once, resolve);
    pthread_mutex_lock(&lock);
    struct allocation **p = &allocations;
    while (*p && (*p)->nodes != head) p = &(*p)->next;
    struct allocation *a = *p;
    if (a) *p = a->next;
    pthread_mutex_unlock(&lock);
    if (a) { real_free(a->original); free(a); }
    else if (real_free) real_free(head);
}
