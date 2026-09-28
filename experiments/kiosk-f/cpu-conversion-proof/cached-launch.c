/* Optional CPU staging for linear system-memory video. No global allocator changes. */
#include <gst/gst.h>
#include <glib-unix.h>
#include <gst/video/video.h>
#include <string.h>
#include <signal.h>
static GMainLoop *loop;
static GstElement *pipeline;
static int failed;
static GstPadProbeReturn stage(GstPad *pad, GstPadProbeInfo *info, gpointer unused) {
    (void)pad; (void)unused;
    GstBuffer *in = GST_PAD_PROBE_INFO_BUFFER(info);
    GstBuffer *out = gst_buffer_new_allocate(NULL, gst_buffer_get_size(in), NULL);
    GstMapInfo r = GST_MAP_INFO_INIT, w = GST_MAP_INFO_INIT;
    gboolean rm = FALSE, wm = FALSE;
    if (out) rm = gst_buffer_map(in, &r, GST_MAP_READ);
    if (rm) wm = gst_buffer_map(out, &w, GST_MAP_WRITE);
    if (!wm || w.size != r.size) goto error;
    memcpy(w.data, r.data, r.size);
    gst_buffer_unmap(out, &w); wm = FALSE;
    gst_buffer_unmap(in, &r); rm = FALSE;
    /* Preserve timestamps/flags. Video layout metadata is copied below; avoid
       foreign-memory lifetime/synchronization metadata on the owned allocation. */
    if (!gst_buffer_copy_into(out, in, GST_BUFFER_COPY_FLAGS | GST_BUFFER_COPY_TIMESTAMPS, 0, -1)) goto error;
    GstVideoMeta *vm = gst_buffer_get_video_meta(in);
    if (vm && !gst_buffer_add_video_meta_full(out, vm->flags, vm->format,
                vm->width, vm->height, vm->n_planes, vm->offset, vm->stride)) goto error;
    GST_PAD_PROBE_INFO_DATA(info) = out;
    gst_buffer_unref(in);
    return GST_PAD_PROBE_OK;
error:
    if (wm) gst_buffer_unmap(out, &w);
    if (rm) gst_buffer_unmap(in, &r);
    if (out) gst_buffer_unref(out);
    failed = 1;
    g_printerr("cached-copy: allocation, layout or mapping failed; stopping\n");
    g_main_loop_quit(loop);
    return GST_PAD_PROBE_DROP;
}
static gboolean message(GstBus *bus, GstMessage *msg, gpointer data) {
    (void)bus; (void)data;
    if (GST_MESSAGE_TYPE(msg) == GST_MESSAGE_ERROR) {
        GError *err = NULL; gchar *debug = NULL;
        gst_message_parse_error(msg, &err, &debug);
        g_printerr("cached-copy: %s (%s)\n", err->message, debug ? debug : "");
        g_clear_error(&err); g_free(debug); failed = 1;
        g_main_loop_quit(loop);
    } else if (GST_MESSAGE_TYPE(msg) == GST_MESSAGE_EOS) g_main_loop_quit(loop);
    return G_SOURCE_CONTINUE;
}
static gboolean stop(gpointer data) { (void)data; g_main_loop_quit(loop); return G_SOURCE_REMOVE; }
int main(int argc, char **argv) {
    GError *error = NULL;
    gst_init(&argc, &argv);
    if (argc > 1 && !strcmp(argv[1], "-e")) { argv++; argc--; }
    if (argc < 2) return 2;
    pipeline = gst_parse_launchv((const gchar **)(argv + 1), &error);
    if (error || !pipeline) { g_printerr("cached-copy: %s\n", error ? error->message : "no pipeline"); return 2; }
    GstElement *identity = gst_bin_get_by_name(GST_BIN(pipeline), "vyarm_cached_copy");
    if (!identity) return 2;
    GstPad *pad = gst_element_get_static_pad(identity, "src");
    loop = g_main_loop_new(NULL, FALSE);
    gst_pad_add_probe(pad, GST_PAD_PROBE_TYPE_BUFFER, stage, NULL, NULL);
    GstBus *bus = gst_element_get_bus(pipeline);
    gst_bus_add_watch(bus, message, NULL);
    g_unix_signal_add(SIGTERM, stop, NULL); g_unix_signal_add(SIGINT, stop, NULL);
    g_print("cached-copy: enabled, owned CPU memory before conversion\n");
    if (gst_element_set_state(pipeline, GST_STATE_PLAYING) == GST_STATE_CHANGE_FAILURE) failed = 1;
    else g_main_loop_run(loop);
    gst_element_set_state(pipeline, GST_STATE_NULL);
    gst_object_unref(bus); gst_object_unref(pad); gst_object_unref(identity); gst_object_unref(pipeline);
    g_main_loop_unref(loop);
    return failed;
}
