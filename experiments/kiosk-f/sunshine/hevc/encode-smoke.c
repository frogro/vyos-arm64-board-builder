/* SPDX-License-Identifier: MIT
 * Standalone encoder bitstream probe, not a Sunshine latency benchmark.
 * Usage: encode-smoke ENCODER OUTPUT
 */
#include <stdio.h>
#include <stdlib.h>
#include <libavcodec/avcodec.h>
#include <libavutil/opt.h>

static void check(int ret, const char *what) {
    if (ret < 0) {
        char error[AV_ERROR_MAX_STRING_SIZE];
        av_strerror(ret, error, sizeof(error));
        fprintf(stderr, "%s: %s\n", what, error);
        exit(1);
    }
}

static int drain(AVCodecContext *ctx, AVPacket *packet, FILE *out) {
    int count = 0, ret;
    while ((ret = avcodec_receive_packet(ctx, packet)) >= 0) {
        if (fwrite(packet->data, 1, packet->size, out) != (size_t)packet->size)
            exit(1);
        count++;
        av_packet_unref(packet);
    }
    if (ret != AVERROR(EAGAIN) && ret != AVERROR_EOF) check(ret, "receive");
    return count;
}

int main(int argc, char **argv) {
    if (argc != 3) return 2;
    const AVCodec *codec = avcodec_find_encoder_by_name(argv[1]);
    if (!codec) { fprintf(stderr, "Encoder unavailable\n"); return 1; }
    AVCodecContext *ctx = avcodec_alloc_context3(codec);
    AVFrame *frame = av_frame_alloc();
    AVPacket *packet = av_packet_alloc();
    if (!ctx || !frame || !packet) return 1;
    ctx->width = 1920; ctx->height = 1080;
    ctx->pix_fmt = AV_PIX_FMT_NV12;
    ctx->time_base = (AVRational){1, 60};
    ctx->framerate = (AVRational){60, 1};
    ctx->bit_rate = 8000000;
    ctx->gop_size = 60; ctx->max_b_frames = 0;
    ctx->color_range = AVCOL_RANGE_MPEG;
    ctx->colorspace = AVCOL_SPC_BT709;
    ctx->color_primaries = AVCOL_PRI_BT709;
    ctx->color_trc = AVCOL_TRC_BT709;
    check(av_opt_set_int(ctx->priv_data, "rc_mode", 1, 0), "CBR");
    check(avcodec_open2(ctx, codec, NULL), "open");
    frame->format = ctx->pix_fmt;
    frame->width = ctx->width; frame->height = ctx->height;
    check(av_frame_get_buffer(frame, 32), "frame buffer");
    FILE *out = fopen(argv[2], "wb");
    if (!out) return 1;
    int packets = 0;
    for (int n = 0; n < 120; n++) {
        check(av_frame_make_writable(frame), "writable");
        /* Limited-range gray bars move every frame; neutral chroma. */
        for (int y = 0; y < ctx->height; y++)
            for (int x = 0; x < ctx->width; x++)
                frame->data[0][y * frame->linesize[0] + x] =
                    16 + (((x + n * 8) / 120) % 8) * 30;
        for (int y = 0; y < ctx->height / 2; y++)
            for (int x = 0; x < ctx->width; x++)
                frame->data[1][y * frame->linesize[1] + x] = 128;
        frame->pts = n;
        check(avcodec_send_frame(ctx, frame), "send");
        packets += drain(ctx, packet, out);
    }
    check(avcodec_send_frame(ctx, NULL), "flush");
    packets += drain(ctx, packet, out);
    if (fclose(out)) return 1;
    fprintf(stderr, "%s: 120 input frames, %d packets\n", argv[1], packets);
    av_packet_free(&packet); av_frame_free(&frame); avcodec_free_context(&ctx);
    return packets == 120 ? 0 : 1;
}
