# -*- mode: python -*-

block_cipher = None

ONE_FILE = False
ICON_FILE = "./octomap.ico"

a = Analysis(['octomap.py'],
			 pathex=['C:/Python34/Lib/', 'C:\\Documents and Settings\\Zumi\\Desktop\\Applications\\octomap'],
			 binaries=None,
			 datas=None,
			 hiddenimports=['tkinter'],
			 hookspath=None,
			 runtime_hooks=None,
			 excludes=None,
			 win_no_prefer_redirects=None,
			 win_private_assemblies=None,
			 cipher=block_cipher)

# include rsrc
a.datas += Tree('./resources', prefix='resources')

pyz = PYZ(a.pure, a.zipped_data,
			 cipher=block_cipher)

if ONE_FILE:
	exe = EXE(pyz,
			  a.scripts,
			  a.binaries,
			  a.zipfiles,
			  a.datas,
			  name='octomap',
			  debug=False,
			  strip=False,
			  upx=False,
			  runtime_tmpdir=None,
			  console=True,)
else:
	exe = EXE(pyz,
			  a.scripts,
			  exclude_binaries=True,
			  name='octomap',
			  debug=False,
			  strip=True,
			  upx=False,
			  console=False,
			  icon=ICON_FILE,)
	coll = COLLECT(exe,
				   a.binaries,
				   a.zipfiles,
				   a.datas,
				   strip=True,
				   upx=True,
				   name='octomap')