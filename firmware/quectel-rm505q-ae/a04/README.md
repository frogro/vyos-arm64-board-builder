# Optional RM505Q-AE A04 boot image

Source: `RM505QAEAAR11A04M4G_01.200.01.200/update/sbl1.mbn`, supplied by the repository owner from their Quectel firmware package.

The ARM board builder includes this file only when Additional/Extended Network is enabled
(`EXTENDED_NETWORK=yes`), on any supported board, at
`/usr/share/quectel-rm505q-ae/a04/sbl1.mbn`. It does not install it in the kernel
firmware search path or activate it automatically. Base builds do not receive
this bundled asset.

This image runs on the SDX55 modem, independently of the host CPU architecture.
Use only with the matching RM505Q-AE firmware; it is not a universal SDX55 image.

Optional manual installation on the target VyOS system:

```bash
cd /usr/share/quectel-rm505q-ae/a04
sha256sum --check SHA256SUMS &&
    sudo install -D -m 0644 sbl1.mbn /lib/firmware/qcom/sdx55m/sbl1.mbn
```

The file is then available to the native MHI driver's boot loader. Copying it
does not itself reinitialize an already stopped modem. No QFirehose flash is
performed by these commands. Manual installation is local to that VyOS image;
the bundled copy remains available in subsequently built images with Additional/Extended Network enabled.

## Validation and update scope

The checksum verifies the identity/integrity of this supplied file, not modem
compatibility or a successful boot. The upstream MHI PCI driver uses
`qcom/sdx55m/sbl1.mbn` for its Qualcomm SDX55 device profile; confirm the actual
PCI device match and firmware request before manual installation. Do not replace
an existing file at that shared path without checking which modem needs it.

Both the board image and its update ISO contain the optional bundle when built
with Extended Network. A manual copy into `/lib/firmware` is image-local: after
switching images, check and repeat the installation if needed. Automatic
activation or migration of this optional modem firmware is not implemented.

Driver reference:
https://github.com/torvalds/linux/blob/master/drivers/bus/mhi/host/pci_generic.c
