rmdir /s /q build dist __pycache__
pyinstaller octomap.spec
verpatch dist\octomap\octomap.exe /va 0.0.0.4 /s product "OctoMap" /s company "Zumi" /s copyright "2022 Zumi" /s desc "A program to edit maps" /fn /langid 1033
rmdir /s /q dist\octomap\include
del dist\octomap\octomap.exe.manifest dist\octomap\PIL._webp.pyd dist\octomap\pyexpat.pyd dist\octomap\select.pyd dist\octomap\unicodedata.pyd dist\octomap\_bz2.pyd dist\octomap\_ctypes.pyd dist\octomap\_decimal.pyd dist\octomap\_hashlib.pyd dist\octomap\_lzma.pyd dist\octomap\_socket.pyd dist\octomap\_ssl.pyd
pause