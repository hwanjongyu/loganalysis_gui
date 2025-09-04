# -*- mode: python ; coding: utf-8 -*-

import os
import glob

def find_libs(*lib_names):
    """A helper function to search for libraries in common system paths."""
    found_libs = []
    # Common library paths on Linux
    search_paths = ['/usr/lib', '/usr/lib64', '/lib', '/lib64']
    # Add multi-arch paths (e.g., /usr/lib/x86_64-linux-gnu)
    search_paths.extend(glob.glob('/usr/lib/*-linux-gnu'))
    search_paths.extend(glob.glob('/lib/*-linux-gnu'))
    
    # De-duplicate and sort for consistent search order
    search_paths = sorted(list(set(search_paths)))
    
    for lib_name in lib_names:
        found = False
        for path in search_paths:
            lib_path = os.path.join(path, lib_name)
            if os.path.exists(lib_path):
                found_libs.append((lib_path, '.'))
                found = True
                break
        if not found:
            print(f"WARNING: Could not find system library: {lib_name}")
    return found_libs

# A list of XCB libraries that are often not bundled correctly by PyInstaller.
# libxcb.so.1 is the most critical one, as it's explicitly excluded by PyInstaller's default rules.
needed_binaries = find_libs(
    'libxcb.so.1',
    'libxkbcommon-x11.so.0',
    'libxcb-icccm.so.4',
    'libxcb-image.so.0',
    'libxcb-keysyms.so.1',
    'libxcb-randr.so.0',
    'libxcb-render-util.so.0',
    'libxcb-xinerama.so.0',
    'libxcb-xkb.so.1',
    'libxcb-cursor.so.0',
)

a = Analysis(
    ['src/loganalysis_gui.py'],
    pathex=[],
    binaries=needed_binaries,
    datas=[],
    hiddenimports=['PyQt5.sip'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['src/runtime_hook.py'],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='loganalysis_gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
