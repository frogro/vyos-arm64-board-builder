// SPDX-License-Identifier: GPL-2.0
/* Isolated diagnostic: no decoder may be bound; caller serializes domain changes. */
#include <linux/module.h>
#include <linux/platform_device.h>
#include <linux/iommu.h>
static int __init test_init(void)
{
 struct device *dev;
 struct iommu_domain *domain;
 int ret = 0;
 dev = bus_find_device_by_name(&platform_bus_type, NULL, "fdc70000.video-codec");
 if (!dev) return -ENODEV;
 device_lock(dev);
 domain = iommu_get_domain_for_dev(dev);
 if (dev->driver || !domain || domain->type != IOMMU_DOMAIN_DMA ||
     !domain->ops->flush_iotlb_all) { ret = -EBUSY; goto out; }
 pr_info("VYARM_FLUSH_HELPER begin\n");
 iommu_flush_iotlb_all(domain);
 pr_info("VYARM_FLUSH_HELPER done\n");
out:
 device_unlock(dev);
 put_device(dev);
 return ret;
}
static void __exit test_exit(void) {}
module_init(test_init);
module_exit(test_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("TEST ONLY: serialized AV1 IOMMU flush callback");
