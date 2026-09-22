#include <gst/gst.h>
#include <gst/app/gstappsrc.h>
#include <stdio.h>
#include <string.h>
static guint32 le32(const guint8 *p) { return GST_READ_UINT32_LE(p); }
int main(int argc, char **argv) {
 gst_init(&argc,&argv);
 if(argc!=2) return 2;
 FILE *f=fopen(argv[1],"rb"); guint8 h[32],fh[12];
 if(!f || fread(h,1,32,f)!=32 || memcmp(h,"DKIF",4) || memcmp(h+8,"VP90",4) || GST_READ_UINT16_LE(h+6)!=32 || !le32(h+16) || !le32(h+20)) return 3;
 GError *err=NULL;
 GstElement *p=gst_parse_launch("appsrc name=src format=time block=true max-bytes=4194304 ! vp9parse ! v4l2slvp9dec ! video/x-raw,format=NV12_10LE40 ! fdsink fd=1 sync=false",&err);
 if(err) { g_printerr("pipeline: %s\n",err->message); return 4; }
 GstElement *src=gst_bin_get_by_name(GST_BIN(p),"src");
 GstCaps *caps=gst_caps_new_simple("video/x-vp9","width",G_TYPE_INT,(int)GST_READ_UINT16_LE(h+12),"height",G_TYPE_INT,(int)GST_READ_UINT16_LE(h+14),"framerate",GST_TYPE_FRACTION,(int)le32(h+16),(int)le32(h+20),NULL);
 gst_app_src_set_caps(GST_APP_SRC(src),caps);gst_caps_unref(caps);
 gst_element_set_state(p,GST_STATE_PLAYING);
 int rc=0; guint count=0; size_t n;
 while((n=fread(fh,1,12,f))) {
  if(n!=12 || le32(fh)==0 || le32(fh)>16777216) {rc=5;break;}
  guint len=le32(fh); GstBuffer *b=gst_buffer_new_allocate(NULL,len,NULL);GstMapInfo map;
  gst_buffer_map(b,&map,GST_MAP_WRITE);
  if(fread(map.data,1,len,f)!=len) {gst_buffer_unmap(b,&map);gst_buffer_unref(b);rc=6;break;}
  gst_buffer_unmap(b,&map);
  GST_BUFFER_PTS(b)=gst_util_uint64_scale(GST_READ_UINT64_LE(fh+4),GST_SECOND*(guint64)le32(h+20),le32(h+16));
  GST_BUFFER_DURATION(b)=gst_util_uint64_scale(GST_SECOND,le32(h+20),le32(h+16));
  if(gst_app_src_push_buffer(GST_APP_SRC(src),b)!=GST_FLOW_OK){rc=7;break;}count++;
 }
 fclose(f);gst_app_src_end_of_stream(GST_APP_SRC(src));
 GstBus *bus=gst_element_get_bus(p);GstMessage *m=gst_bus_timed_pop_filtered(bus,60*GST_SECOND,GST_MESSAGE_ERROR|GST_MESSAGE_EOS);
 if(!m) rc=8;
 else if(GST_MESSAGE_TYPE(m)==GST_MESSAGE_ERROR) {gchar *dbg=NULL;gst_message_parse_error(m,&err,&dbg);g_printerr("decode: %s; %s\n",err->message,dbg?dbg:"");g_clear_error(&err);g_free(dbg);rc=9;}
 if(m)gst_message_unref(m);
 g_printerr("input_frames=%u result=%d\n",count,rc);
 gst_element_set_state(p,GST_STATE_NULL);gst_object_unref(bus);gst_object_unref(src);gst_object_unref(p);return rc;
}
