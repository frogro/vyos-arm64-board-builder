# Formatting functions from VyOS image_info.py, GPL-3.0-or-later.
# Copyright VyOS maintainers and contributors.
# Upstream source: vyos/vyos-1x 27383e4f15180184a45dfcafe36b7a4ca326370f.
from __future__ import annotations

def _format_show_images_summary(images_summary: image.BootDetails) -> str:
    headers: list[str] = ['Name', 'Default boot', 'Running']
    table_data: list[list[str]] = list()
    for image_item in images_summary.get('images_available', []):
        name: str = image_item
        if images_summary.get('image_default') == name:
            default: str = 'Yes'
        else:
            default: str = ''

        if images_summary.get('image_running') == name:
            running: str = 'Yes'
        else:
            running: str = ''

        table_data.append([name, default, running])
    tabulated: str = tabulate(table_data, headers)

    return tabulated

def _format_show_images_details(
        images_details: list[image.ImageDetails]) -> str:
    headers: list[str] = [
        'Name', 'Version', 'Storage Read-Only', 'Storage Read-Write',
        'Storage Total'
    ]
    table_data: list[list[Union[str, int]]] = list()
    for image_item in images_details:
        name: str = image_item.get('name')
        version: str = image_item.get('version')
        disk_ro: str = bytes_to_human(image_item.get('disk_ro'),
                                      precision=1, int_below_exponent=30)
        disk_rw: str = bytes_to_human(image_item.get('disk_rw'),
                                      precision=1, int_below_exponent=30)
        disk_total: str = bytes_to_human(image_item.get('disk_total'),
                                         precision=1, int_below_exponent=30)
        table_data.append([name, version, disk_ro, disk_rw, disk_total])
    tabulated: str = tabulate(table_data, headers,
                              colalign=('left', 'left', 'right', 'right', 'right'))

    return tabulated
