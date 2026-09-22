# DRM HDMI audio codec dependency

The ROCK 5B image 999.202609150829 creates hdmi-audio-codec platform devices
but omits SND_SOC_HDMI_CODEC. Both HDMI output sound cards remain deferred;
the I2S and display drivers bind, and analog ES8316 audio registers.
This diagnosis concerns output audio, not HDMI receiver video capture.

`tools/patch-hdmi-audio-dependency.py` adds the conditional Kconfig dependency
`select SND_SOC_HDMI_CODEC if SND_SOC` to DRM_DISPLAY_HDMI_AUDIO_HELPER.
It runs after kernel preparation and before baseline/board configuration.
The source guard requires the helper to register HDMI_CODEC_DRV_NAME through
platform_device_register_data. Kernels without that implementation are skipped;
existing selects are retained. Unexpected missing symbols fail explicitly.

There is no board whitelist or KVM-profile requirement. Boards using this
helper and ASoC receive the codec; other configurations do not enable it.
The fix preserves SND_SOC=m and audio-disabled configurations.

Validation: five regression tests, including Kconfig y/m/n evaluation when
kconfiglib is installed; applied and repeated against upstream Linux v6.18.
Full image build and physical HDMI audio playback remain untested.

Live insertion into the tested image is unavailable: CONFIG_MODVERSIONS=y,
CONFIG_MODULE_SIG_FORCE=y, no installed build headers, and the GitHub workflow
does not retain the private module-signing key. Do not disable signature
checking or substitute a module from another kernel build. Test the correction
with a newly built image and inspect /proc/asound/cards and devices_deferred.
