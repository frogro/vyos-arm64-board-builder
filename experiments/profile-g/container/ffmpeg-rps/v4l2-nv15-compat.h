/* Linux UAPI linear packed 10-bit NV12; identical to Linux 6.18 videodev2.h.
 * Older build headers omit this stable FOURCC. Runtime negotiation still checks
 * whether the kernel supports the format; this does not force device support.
 */
#ifndef V4L2_NV15_COMPAT_H
#define V4L2_NV15_COMPAT_H
#include <linux/videodev2.h>
#ifndef V4L2_PIX_FMT_NV15
#define V4L2_PIX_FMT_NV15 v4l2_fourcc('N', 'V', '1', '5')
#endif
#endif
