#!/usr/bin/python3
"""Restore CUPS backend retry holds after a container restart, through IPP.

CUPS may persist a retry-held job with job-hold-until=no-hold while its retry
wake-up time is only in memory. Do not release explicit user or auth holds.
"""
import time
from pathlib import Path
from urllib.parse import unquote, urlparse
import cups


def recoverable(attributes, printers):
    if attributes.get('job-state') != 4:  # IPP_JOB_HELD
        return False
    reasons = attributes.get('job-state-reasons', [])
    if isinstance(reasons, str):
        reasons = [reasons]
    printer_reasons = attributes.get('job-printer-state-reasons', [])
    if isinstance(printer_reasons, str):
        printer_reasons = [printer_reasons]
    # CUPS 2.4 may normalize job-state-reasons to 'none' after reloading
    # a backend retry hold, retaining the printer's offline-report instead.
    offline_retry = reasons == ['none'] and 'offline-report' in printer_reasons
    if 'resources-are-not-ready' not in reasons and not offline_retry:
        return False
    if attributes.get('job-hold-until') != 'no-hold':
        return False
    name = unquote(urlparse(attributes.get('job-printer-uri', '')).path.rsplit('/', 1)[-1])
    printer = printers.get(name, {})
    if printer.get('printer-state') == 5:  # deliberately stopped printer
        return False
    uri = printer.get('device-uri', '')
    return uri.startswith('usb:') or '+usb:' in uri


def main():
    # A container with no assigned device must leave unavailable jobs waiting.
    if not any(Path('/dev/bus/usb').glob('*/*')):
        return
    connection = None
    for _ in range(60):
        try:
            connection = cups.Connection(host='/run/cups/cups.sock')
            printers = connection.getPrinters()
            break
        except (RuntimeError, cups.IPPError):
            time.sleep(0.5)
    else:
        raise RuntimeError('CUPS did not become available for USB retry recovery')
    for job, attributes in connection.getJobs(which_jobs='not-completed', my_jobs=False).items():
        # Query immediately before modifying to respect intervening admin actions.
        attributes = connection.getJobAttributes(job)
        if recoverable(attributes, printers):
            connection.setJobHoldUntil(job, 'no-hold')
            print(f'Resumed CUPS automatic USB retry for job {job}', flush=True)


if __name__ == '__main__':
    main()
