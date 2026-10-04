"""Compatibility entry point: F and G share one display audio implementation."""
import importlib.util
from pathlib import Path

path = Path(__file__).with_name('kiosk-audio.py')
if not path.exists():  # Source-tree tests; installed G keeps both files together.
    path = Path(__file__).resolve().parents[2]/'kiosk-f/container/kiosk-audio.py'
spec = importlib.util.spec_from_file_location('display_audio', path)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
select_device = base.select_device
AudioSession = base.AudioSession
