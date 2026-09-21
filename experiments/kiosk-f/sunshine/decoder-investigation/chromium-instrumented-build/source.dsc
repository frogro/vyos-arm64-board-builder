-----BEGIN PGP SIGNED MESSAGE-----
Hash: SHA256

Format: 3.0 (quilt)
Source: chromium
Binary: chromium, chromium-l10n, chromium-shell, chromium-headless-shell, chromium-driver, chromium-common, chromium-sandbox
Architecture: i386 amd64 arm64 armhf loong64 ppc64el all
Version: 153.0.8010.47-2~deb13u1
Maintainer: Debian Chromium Team <chromium@packages.debian.org>
Uploaders:  Andres Salomon <dilinger@debian.org>, Timothy Pearson <tpearson@raptorengineering.com>, Daniel Richard G. <skunk@iSKUNK.ORG>,
Homepage: http://www.chromium.org/Home
Standards-Version: 4.5.0
Vcs-Browser: https://salsa.debian.org/chromium-team/chromium
Vcs-Git: https://salsa.debian.org/chromium-team/chromium.git
Build-Depends: debhelper (>= 11), devscripts, llvm-22:native, lld-22:native, clang-22:native, clang-format-22:native, libclang-rt-22-dev, libc++-22-dev, rustc-web:any (>= 1.96.0), libstd-rust-web-dev (>= 1.96.0), bindgen:native, rustfmt:any, python3:any, pkgconf, ninja-build, python3-jinja2:native, ca-certificates, wget, flex, xvfb, wdiff, golang, gperf, bison, nodejs:any, node-rollup-plugin-terser:native, node-typescript, rollup, esbuild:native, xz-utils, xcb-proto, xfonts-base, libdav1d-dev, libx11-xcb-dev, libxshmfence-dev, libgl-dev, libglu1-mesa-dev, libegl1-mesa-dev, libgles2-mesa-dev, libopenh264-dev, generate-ninja, mesa-common-dev, rapidjson-dev, libva-dev, libxt-dev, libgbm-dev, libpng-dev, libxss-dev, libelf-dev, libpci-dev, libcap-dev, libffi-dev, libkrb5-dev, libexif-dev, libflac-dev, libudev-dev, libpipewire-0.3-dev, libpthreadpool-dev, libopus-dev, libxtst-dev, libjpeg-dev, libgtk-3-dev, liblcms2-dev, libpulse-dev, libpam0g-dev, libdouble-conversion-dev, libxnvctrl-dev, libglib2.0-dev, libasound2-dev, libsecret-1-dev, libspeechd-dev, libminizip-dev, libhunspell-dev, libharfbuzz-dev, libxcb-dri3-dev, libusb-1.0-0-dev, libopenjp2-7-dev, libnss3-dev, libnspr4-dev, libcups2-dev, libevdev-dev, libgcrypt20-dev, libcurl4-openssl-dev, libzstd-dev, fonts-ipafont-gothic, fonts-ipafont-mincho, cross-exe-wrapper <cross>, linux-libc-dev (>= 6.5)
Build-Conflicts: bindgen-0.56, bindgen-0.65, rustc-1.74
Package-List:
 chromium deb web optional arch=i386,amd64,arm64,armhf,loong64,ppc64el
 chromium-common deb web optional arch=i386,amd64,arm64,armhf,loong64,ppc64el
 chromium-driver deb web optional arch=i386,amd64,arm64,armhf,loong64,ppc64el
 chromium-headless-shell deb web optional arch=i386,amd64,arm64,armhf,loong64,ppc64el
 chromium-l10n deb localization optional arch=all
 chromium-sandbox deb web optional arch=i386,amd64,arm64,armhf,loong64,ppc64el
 chromium-shell deb web optional arch=i386,amd64,arm64,armhf,loong64,ppc64el
Checksums-Sha1:
 e06ba99fb3876d8ef2c14125d6e73f7d730c3863 16118380 chromium_153.0.8010.47.orig-pre-gen.tar.xz
 e027b8d48916dddb1fde047f48d819d01fe61d9b 963926108 chromium_153.0.8010.47.orig.tar.xz
 d8c1a379e9cdafdd43718d983bf0f16335aa1b32 564176 chromium_153.0.8010.47-2~deb13u1.debian.tar.xz
Checksums-Sha256:
 bdfb320af01e4d991880102cf6e8b4f7d001f6c52cb9c7529743268d67b0fb3c 16118380 chromium_153.0.8010.47.orig-pre-gen.tar.xz
 d7b52d13651391a7951f7f6c51941518152d261bd4e33382960830c59c2332fd 963926108 chromium_153.0.8010.47.orig.tar.xz
 aab91397261c2361958daf32539393ebe6acf57f0e1cfaecc4d73d21ff62e410 564176 chromium_153.0.8010.47-2~deb13u1.debian.tar.xz
Files:
 19c3e15ee3125ae121f9179ae175ee61 16118380 chromium_153.0.8010.47.orig-pre-gen.tar.xz
 10046baf4a534426bc49cbc168481ef3 963926108 chromium_153.0.8010.47.orig.tar.xz
 cd278d089b97ca6b50d39f5f23f71db8 564176 chromium_153.0.8010.47-2~deb13u1.debian.tar.xz

-----BEGIN PGP SIGNATURE-----

iQJIBAEBCAAyFiEEUAUk+X1YiTIjs19qZF0CR8NudjcFAmqrMmsUHGRpbGluZ2Vy
QGRlYmlhbi5vcmcACgkQZF0CR8Nudjei3Q/9Ew9zubhgG5GeEdfkTEYflLJ0Qp/p
xg3f2Mi1qG51AXZHDBnQ10YHQDcYK1QSj0ePg3rVIs9tjwB8lNT8we2n6yUr46ps
5/ga9KARCeqzKfXg1R+swa5sNG+zo7FdAQrY62+ibvMIINVK7H3+tTi3YCGJgYb4
lpe6hcqfxRNKnOocF8re/ne/dpA1eRU7Pfw4TAXtrCKGjs2vwMAeIs9qkCPMc9nS
ETpw6BJHUIfB78hKnPSQaC5sAbJ2nafWNRmyXp8lZUl58QRuajwRU7UV2DaRpD03
/ABSoeXmowdnAiZT+DRDlWvrkQ1WPTHtclch/cQgW5LxYdEAKG3vHgk6g5yHBrTf
WwomeK8WubDzySjpvP54fOgLjaFrQi7CuxDAIGXgJTJ1Pd/pKov1WyyfXmGdf38o
g73u0kidUIz1jxpKbWZwj3e+/TRQnmeA1C1ESlUpXw5qTeAlGd9xzcR9z8hsEsrZ
BGqwEDrqY+8oz2sgFeK67JgaaySNGnL0XEDVwJk7QMYH8VE0yMnD/FYT5YUTYVFE
OfEA8y5tzIWEQvsZxyAU1TtQPlRSRgHSzirzijxQXR+q/w2G+qjn8N9juuTRRwMi
M8CKiB9mh4oMU4RECsDZ2I1qfZuYhSbpe9IKxAQseUWJtYN32XzE6LFS2fx3DomY
jf/5xzZ3TD0BIYk=
=owit
-----END PGP SIGNATURE-----
