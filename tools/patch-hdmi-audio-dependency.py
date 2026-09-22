#!/usr/bin/env python3
"""Restore the codec dependency of kernels using the DRM HDMI audio helper."""
import argparse
import re
from pathlib import Path


def patch(kernel):
    kernel = Path(kernel)
    source = kernel / 'drivers/gpu/drm/display/drm_hdmi_audio_helper.c'
    config = kernel / 'drivers/gpu/drm/display/Kconfig'
    if not source.exists():
        return 'not applicable: no DRM HDMI audio helper'
    text = source.read_text()
    if not re.search(r'platform_device_register_data\s*\([^;]*HDMI_CODEC_DRV_NAME', text, re.S):
        return 'not applicable: helper does not register HDMI codec devices'
    content = config.read_text()
    pattern = r'(?m)^config DRM_DISPLAY_HDMI_AUDIO_HELPER\n(?:(?!config |menuconfig ).*\n)*'
    match = re.search(pattern, content)
    if not match:
        raise ValueError('HDMI codec registration found without expected helper Kconfig symbol')
    block = match.group()
    if re.search(r'^\s+select SND_SOC_HDMI_CODEC(?:\s|$)', block, re.M):
        return 'already provided by kernel'
    codec_config = kernel / 'sound/soc/codecs/Kconfig'
    if not re.search(r'^config SND_SOC_HDMI_CODEC$', codec_config.read_text(), re.M):
        raise ValueError('Expected HDMI codec Kconfig symbol is missing')
    # The hidden tristate cannot be enabled reliably by a config fragment.
    # Conditional select preserves audio-disabled builds and the SND_SOC=m cap.
    updated = block.replace('\n', '\n\tselect SND_SOC_HDMI_CODEC if SND_SOC\n', 1)
    config.write_text(content[:match.start()] + updated + content[match.end():])
    return 'added conditional HDMI codec dependency'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kernel', type=Path)
    print(patch(parser.parse_args().kernel))
