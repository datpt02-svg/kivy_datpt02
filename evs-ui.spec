# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [
    ('app/ui.kv', 'app'),
    ('app/screen/KivyModule', 'app/screen/KivyModule'),
    ('app/libs/widgets/components.kv', 'app/libs/widgets'),
    ('app/libs/assets', 'app/libs/assets'),
    ('app/libs/language', 'app/libs/language'),
    ('default_data', 'default_data'),
    ('alembic.ini','.'),
    ('db/alembic','db/alembic'),
    ('setup.bat','.'),
]
binaries = []

hiddenimports = [
    'win32timezone',
    'logging',
    'logging.config',
    # pywin32 core modules
    'pywin32',
    'win32api',
    'win32event',
    'win32con',
    'win32pipe',
    'win32file',
    'win32process',
    'pywintypes',
    'pythoncom',
    'win32gui',
    'win32security',
    'win32service',
    'win32serviceutil',
    'win32clipboard',
    'win32net',
    'win32netcon',
    'win32wnet',
    'win32pdh',
    'win32profile',
    'win32ras',
    'win32reg',
    'win32ts',
    'win32uiole',
    'win32ver',
    'win32wnet',
    'dotenv',
    'cv2'
]
hiddenimports += []
# ==== Gom các deps quan trọng ====
for mod in (
    'plyer',
    'cv2',
    'dotenv',
    'pywin32'
):
    tmp_ret = collect_all(mod)
    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hiddenimports += tmp_ret[2]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['kivy.garden', 'kivy.tests', 'pytest'],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='evs-ui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='app/libs/assets/icons/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='evs-ui',
)
