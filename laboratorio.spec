# recetas.spec
block_cipher = None

a = Analysis(
    ['laboratorio.py'],                    # <-- nombre de tu script
    pathex=[],
    binaries=[],
    datas=[
        ('icon_lab.ico', '.'),         # incluir icono en el exe
    ],
    hiddenimports=[
        'PIL',
        'PIL.Image',
        'reportlab',
        'reportlab.pdfgen',
        'reportlab.lib.units',
        'reportlab.pdfbase.pdfmetrics',
        'customtkinter',
        'sqlite3',
        # En recetas.spec y colposcopia.spec agrega:
        'win32print',
        'win32api',
        'win32con',
        'pywintypes',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Laboratorio',            # <-- nombre del exe
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                     # False = sin ventana de consola
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon_lab.ico',               # <-- icono personalizado
)