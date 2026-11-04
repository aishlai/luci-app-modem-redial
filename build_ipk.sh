#!/bin/bash
# 自动打包生成 OpenWrt / iStoreOS 官方规范 .ipk 安装包脚本 (GNU tar.gz 规范，版本号自动递增)

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

python3 - << 'PYEOF'
import os, tarfile, shutil, io, time, re

DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else '/Users/arvin/Documents/Test/luci-app-modem-redial'
VER_FILE = os.path.join(DIR, 'VERSION')
OUT_DIR = os.path.join(DIR, 'bin')
TMP_DIR = os.path.join(DIR, 'build_tmp')

# 读取并自动自增版本号
current_ver = "1.0.0-1"
if os.path.exists(VER_FILE):
    try:
        with open(VER_FILE, 'r', encoding='utf-8') as f:
            c = f.read().strip()
            if c: current_ver = c
    except Exception:
        pass

# 自增版本号: 1.0.0-1 -> 1.0.1-1
match = re.match(r'^(\d+)\.(\d+)\.(\d+)(?:-(\d+))?$', current_ver)
if match:
    major, minor, patch, build = match.groups()
    new_patch = int(patch) + 1
    new_ver = f"{major}.{minor}.{new_patch}-1"
else:
    new_ver = "1.0.1-1"

# 写回 VERSION 文件
with open(VER_FILE, 'w', encoding='utf-8') as f:
    f.write(new_ver + '\n')

print(f"==> [版本递增] {current_ver} -> {new_ver}")

OUT_IPK = os.path.join(OUT_DIR, f'luci-app-modem-redial_{new_ver}_all.ipk')
LATEST_IPK = os.path.join(OUT_DIR, 'luci-app-modem-redial_latest_all.ipk')

os.makedirs(OUT_DIR, exist_ok=True)
shutil.rmtree(TMP_DIR, ignore_errors=True)
os.makedirs(TMP_DIR, exist_ok=True)
now = int(time.time())

# 1. 生成 control.tar.gz
control_tar_path = os.path.join(TMP_DIR, 'control.tar.gz')
with tarfile.open(control_tar_path, 'w:gz', format=tarfile.GNU_FORMAT) as tar:
    ti = tarfile.TarInfo(name='./')
    ti.type = tarfile.DIRTYPE
    ti.mode = 0o755; ti.mtime = now; ti.uid = 0; ti.gid = 0; ti.uname = 'root'; ti.gname = 'root'
    tar.addfile(ti)

    def add_mem_file(name, data, mode):
        ti = tarfile.TarInfo(name=name)
        ti.size = len(data)
        ti.mtime = now
        ti.mode = mode
        ti.uname = 'root'; ti.gname = 'root'; ti.uid = 0; ti.gid = 0
        tar.addfile(ti, io.BytesIO(data))

    control_content = f'''Package: luci-app-modem-redial
Version: {new_ver}
Depends: python3
Section: luci
Architecture: all
Maintainer: aishlai
Description: LuCI Support for Huawei ONT Auto-Redial Assistant (光猫重拨助手)
'''.encode('utf-8')

    postinst_content = b'''#!/bin/sh
[ -n "${IPKG_INSTROOT}" ] || {
    rm -f /usr/lib/lua/luci/controller/modem_redial.lua \
          /usr/lib/lua/luci/model/cbi/modem_redial.lua \
          /usr/lib/lua/luci/view/modem_redial/status.htm 2>/dev/null || true
    rm -f /tmp/luci-indexcache*
    rm -rf /tmp/luci-modulecache/
    /etc/init.d/modem_redial enable
    /etc/init.d/rpcd restart 2>/dev/null || true
    /etc/init.d/uhttpd restart 2>/dev/null || true
}
exit 0
'''
    prerm_content = b'''#!/bin/sh
[ -n "${IPKG_INSTROOT}" ] || {
    /etc/init.d/modem_redial stop
    /etc/init.d/modem_redial disable
    rm -f /usr/lib/lua/luci/controller/modem_redial.lua \
          /usr/lib/lua/luci/model/cbi/modem_redial.lua \
          /usr/lib/lua/luci/view/modem_redial/status.htm 2>/dev/null || true
}
exit 0
'''
    add_mem_file('./control', control_content, 0o644)
    add_mem_file('./postinst', postinst_content, 0o755)
    add_mem_file('./prerm', prerm_content, 0o755)

# 2. 生成 data.tar.gz (纯原生 OpenWrt 24.10 纯 JavaScript 视图规范，不含 legacy luasrc)
data_tar_path = os.path.join(TMP_DIR, 'data.tar.gz')
with tarfile.open(data_tar_path, 'w:gz', format=tarfile.GNU_FORMAT) as tar:
    ti = tarfile.TarInfo(name='./')
    ti.type = tarfile.DIRTYPE
    ti.mode = 0o755; ti.mtime = now; ti.uid = 0; ti.gid = 0; ti.uname = 'root'; ti.gname = 'root'
    tar.addfile(ti)

    # 拷贝 root 目录结构
    root_dir = os.path.join(DIR, 'root')
    for dirpath, dirnames, filenames in os.walk(root_dir):
        rel_dir = os.path.relpath(dirpath, root_dir)
        arc_dir = './' + rel_dir if rel_dir != '.' else './'
        if arc_dir != './':
            ti = tarfile.TarInfo(name=arc_dir + '/')
            ti.type = tarfile.DIRTYPE
            ti.mode = 0o755; ti.mtime = now; ti.uid = 0; ti.gid = 0; ti.uname = 'root'; ti.gname = 'root'
            tar.addfile(ti)
        for f in filenames:
            if f.startswith('.') or f == '.DS_Store': continue
            full_path = os.path.join(dirpath, f)
            arcname = './' + os.path.join(rel_dir, f) if rel_dir != '.' else './' + f
            with open(full_path, 'rb') as fp:
                data = fp.read()
            mode = 0o755 if ('/bin/' in arcname or '/init.d/' in arcname or '/uci-defaults/' in arcname) else 0o644
            add_mem_file(arcname, data, mode)

# 3. 合成外层 IPK 容器 (标准 OpenWrt 24.10 兼容格式)
with tarfile.open(OUT_IPK, 'w:gz', format=tarfile.GNU_FORMAT) as tar:
    deb_bin = b'2.0\n'
    ti = tarfile.TarInfo(name='./debian-binary')
    ti.size = len(deb_bin); ti.mode = 0o644; ti.mtime = now; ti.uid = 0; ti.gid = 0
    tar.addfile(ti, io.BytesIO(deb_bin))

    with open(data_tar_path, 'rb') as fp: data_bytes = fp.read()
    ti = tarfile.TarInfo(name='./data.tar.gz')
    ti.size = len(data_bytes); ti.mode = 0o644; ti.mtime = now; ti.uid = 0; ti.gid = 0
    tar.addfile(ti, io.BytesIO(data_bytes))

    with open(control_tar_path, 'rb') as fp: ctrl_bytes = fp.read()
    ti = tarfile.TarInfo(name='./control.tar.gz')
    ti.size = len(ctrl_bytes); ti.mode = 0o644; ti.mtime = now; ti.uid = 0; ti.gid = 0
    tar.addfile(ti, io.BytesIO(ctrl_bytes))

shutil.copyfile(OUT_IPK, LATEST_IPK)
shutil.rmtree(TMP_DIR, ignore_errors=True)
print(f"==> [成功] IPK 安装包已生成至: {OUT_IPK}")
print(f"==> [最新] 最新副本已更新至:   {LATEST_IPK}")
PYEOF
