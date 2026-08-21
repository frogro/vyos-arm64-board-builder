#!/usr/bin/env python3
from pathlib import Path
import hashlib
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class KvmProfileTests(unittest.TestCase):
    def test_kernel_profile_is_opt_in_and_policy_free(self):
        text = (ROOT / "profiles/kvm-over-ip.config").read_text()
        self.assertIn("CONFIG_USB_VIDEO_CLASS=m", text)
        self.assertIn("CONFIG_MEDIA_CAMERA_SUPPORT=y", text)
        self.assertIn("CONFIG_MEDIA_PCI_SUPPORT=y", text)
        self.assertIn("CONFIG_MEDIA_PLATFORM_SUPPORT=y", text)
        self.assertIn("CONFIG_SND_USB_AUDIO=m", text)
        self.assertIn("CONFIG_USB_GADGET=y", text)
        self.assertIn("CONFIG_USB_CONFIGFS_F_HID=y", text)
        lowered = text.lower()
        for forbidden in (
            "password",
            "token",
            "192.168.",
            "listen_address",
            "tcp_port",
        ):
            self.assertNotIn(forbidden, lowered)
        self.assertNotIn("SYNOPSYS_HDMIRX", text)
        self.assertNotIn("USB_DWC3_DUAL_ROLE", text)

    def test_readiness_profile_matches_kernel_profile(self):
        requested = (ROOT / "profiles/kvm-over-ip.config").read_text()
        requirements = (ROOT / "profiles/kvm-over-ip-ready.config").read_text()
        for line in requirements.splitlines():
            if line.startswith("CONFIG_"):
                symbol = line.split("=", 1)[0]
                self.assertIn(symbol + "=", requested)

    def test_ustreamer_build_is_pinned_and_bookworm_scoped(self):
        text = (ROOT / "tools/build-ustreamer.sh").read_text()
        self.assertIn("USTREAMER_TAG=\"${USTREAMER_TAG:-v6.56}\"", text)
        self.assertIn("23dd2f9e66f945eaf8d9273e4cc4f5b7c47da711", text)
        self.assertIn("bookworm", text)
        self.assertIn("MAX_GLIBC", text)
        self.assertIn("libjpeg.a", text)
        self.assertIn("NEEDED.*libjpeg", text)
        self.assertIn("USTREAMER_LIBJPEG_LINKAGE=static", text)
        self.assertNotIn("trixie", text.lower())

    def test_installer_places_profile_scoped_payload(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            artifacts = root / "artifacts"
            rootfs = root / "rootfs"
            artifacts.mkdir()
            rootfs.mkdir()

            for name in ("ustreamer", "ustreamer-dump"):
                path = artifacts / name
                path.write_text("#!/bin/sh\nexit 0\n")
                path.chmod(0o755)
            (artifacts / "LICENSE").write_text("GPL-3.0\n")
            (artifacts / "LICENSE.libjpeg-turbo").write_text("IJG/BSD\n")
            (artifacts / "build.env").write_text("USTREAMER_TAG=v6.56\n")
            checksums = []
            for name in (
                "ustreamer",
                "ustreamer-dump",
                "LICENSE",
                "LICENSE.libjpeg-turbo",
            ):
                digest = hashlib.sha256((artifacts / name).read_bytes()).hexdigest()
                checksums.append(f"{digest}  {name}")
            (artifacts / "SHA256SUMS").write_text("\n".join(checksums) + "\n")

            subprocess.run(
                [str(ROOT / "tools/install-ustreamer.sh"), str(rootfs), str(artifacts)],
                check=True,
            )
            self.assertTrue((rootfs / "usr/local/bin/ustreamer").is_file())
            self.assertTrue(
                (rootfs / "usr/share/doc/ustreamer/LICENSE.libjpeg-turbo").is_file()
            )
            self.assertTrue(
                (rootfs / "usr/share/vyos-arm64-board-builder/ustreamer-build.env").is_file()
            )

    def test_kvm_userspace_package_set_is_profile_scoped(self):
        packages = (ROOT / "profiles/kvm-over-ip-packages.txt").read_text()
        for package in (
            "v4l-utils",
            "gstreamer1.0-tools",
            "gstreamer1.0-plugins-good",
        ):
            self.assertIn(package, packages)
        installer = (ROOT / "tools/install-kvm-userspace.sh").read_text()
        self.assertIn("apt-get install -y --no-install-recommends", installer)
        self.assertNotIn("apt-get upgrade", installer)

    def test_rock5b_provider_contains_only_opt_in_hardware_delta(self):
        text = (
            ROOT / "profiles/kvm-hardware/rk3588-synopsys-hdmirx.config"
        ).read_text()
        for line in (
            "CONFIG_VIDEO_SYNOPSYS_HDMIRX=m",
            "CONFIG_VIDEO_SYNOPSYS_HDMIRX_LOAD_DEFAULT_EDID=y",
            "# CONFIG_USB_DWC3_HOST is not set",
            "CONFIG_USB_DWC3_DUAL_ROLE=y",
        ):
            self.assertIn(line, text)


if __name__ == "__main__":
    unittest.main()
