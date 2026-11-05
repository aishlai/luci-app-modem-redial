#!/bin/bash
# 自动打包生成 OpenWrt / iStoreOS 官方规范 .ipk 安装包脚本 (GNU tar.gz 规范，统一使用 Git Tag 版本号)

set -e
export SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

python3 - "$@" << 'PYEOF'
import os, tarfile, shutil, io, time, re, sys, subprocess

DIR = os.environ.get("SCRIPT_DIR") or os.getcwd()
VER_FILE = os.path.join(DIR, 'VERSION')
OUT_DIR = os.path.join(DIR, 'bin')
TMP_DIR = os.path.join(DIR, 'build_tmp')
MAKEFILE = os.path.join(DIR, 'Makefile')

# 统一获取并解析版本号 (优先级: 命令行参数 > 环境变量 > Git Tag > VERSION文件 > 默认值)
tag_source = ""
raw_ver = ""

# 1. 命令行参数 (如: bash build_ipk.sh v1.0.5)
if len(sys.argv) > 1 and sys.argv[1].strip():
    candidate = sys.argv[1].strip()
    if candidate not in ("main", "master") and not candidate.startswith("refs/"):
        raw_ver = candidate
        tag_source = f"命令行参数 ({raw_ver})"

# 2. 环境变量 (GitHub Actions 等 CI 环境)
if not raw_ver:
    env_ref = os.environ.get("GITHUB_REF_NAME") or os.environ.get("GIT_TAG")
    if env_ref and not env_ref.startswith("refs/") and env_ref not in ("main", "master"):
        raw_ver = env_ref.strip()
        tag_source = f"环境变量 GITHUB_REF_NAME ({raw_ver})"

# 3. 自动从 Git Tag 获取
if not raw_ver:
    try:
        # 当前 Commit 上的最新 Tag
        res = subprocess.run(["git", "tag", "-l", "--points-at", "HEAD", "--sort=-v:refname"], cwd=DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0 and res.stdout.strip():
            raw_ver = res.stdout.strip().splitlines()[0]
            tag_source = f"当前 Commit Git Tag ({raw_ver})"
        else:
            # 仓库中全局最新 Tag
            res2 = subprocess.run(["git", "tag", "-l", "--sort=-v:refname"], cwd=DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res2.returncode == 0 and res2.stdout.strip():
                raw_ver = res2.stdout.strip().splitlines()[0]
                tag_source = f"仓库全局最新 Git Tag ({raw_ver})"
    except Exception:
        pass

# 4. 从 VERSION 文件读取回退值
if not raw_ver and os.path.exists(VER_FILE):
    try:
        with open(VER_FILE, 'r', encoding='utf-8') as f:
            c = f.read().strip()
            if c:
                raw_ver = c
                tag_source = f"VERSION 文件 ({raw_ver})"
    except Exception:
        pass

# 5. 默认保底版本
if not raw_ver:
    raw_ver = "1.0.0"
    tag_source = "默认保底值"

# 规范化版本号：
# 1) 去除前导 'v' 或 'V' (如 v1.0.5 -> 1.0.5)
clean_ver = re.sub(r'^[vV]', '', raw_ver).strip()

# 2) 遵循 OpenWrt 官方规范: <version>-<pkg_release>
# 若 Tag 自身不包含 '-' (如 1.0.5)，则自动补充包发布修订号 -1 (即 1.0.5-1)
if '-' in clean_ver:
    final_ver = clean_ver
else:
    final_ver = f"{clean_ver}-1"

# 解析基础版本与发布修订号 (供 Makefile 使用)
pkg_ver, pkg_rel = final_ver.split('-', 1) if '-' in final_ver else (final_ver, '1')

# 同步写入 VERSION 文件
with open(VER_FILE, 'w', encoding='utf-8') as f:
    f.write(final_ver + '\n')

# 同步更新 Makefile 中的 PKG_VERSION 与 PKG_RELEASE
if os.path.exists(MAKEFILE):
    try:
        with open(MAKEFILE, 'r', encoding='utf-8') as f:
            m_content = f.read()
        m_content = re.sub(r'PKG_VERSION:=.*', f'PKG_VERSION:={pkg_ver}', m_content)
        m_content = re.sub(r'PKG_RELEASE:=.*', f'PKG_RELEASE:={pkg_rel}', m_content)
        with open(MAKEFILE, 'w', encoding='utf-8') as f:
            f.write(m_content)
    except Exception:
        pass

# 同步更新前端 LuCI JS 视图中的插件版本号 (显示为 v1.0.5)
display_tag = f"v{pkg_ver}"
js_view_file = os.path.join(DIR, 'root/www/luci-static/resources/view/modem_redial.js')
if os.path.exists(js_view_file):
    try:
        with open(js_view_file, 'r', encoding='utf-8') as f:
            j_content = f.read()
        j_content = re.sub(r"var PLUGIN_VERSION = ['\"].*?['\"];", f"var PLUGIN_VERSION = '{display_tag}';", j_content)
        with open(js_view_file, 'w', encoding='utf-8') as f:
            f.write(j_content)
    except Exception:
        pass

# 同步更新 Python 脚本中的 __version__
py_script_file = os.path.join(DIR, 'root/usr/bin/modem_redial.py')
if os.path.exists(py_script_file):
    try:
        with open(py_script_file, 'r', encoding='utf-8') as f:
            p_content = f.read()
        p_content = re.sub(r'__version__ = [\'"].*?[\'"]', f'__version__ = "{final_ver}"', p_content)
        with open(py_script_file, 'w', encoding='utf-8') as f:
            f.write(p_content)
    except Exception:
        pass

print(f"==> [版本识别] 来源: {tag_source} => 最终打包版本: {final_ver}")

OUT_IPK = os.path.join(OUT_DIR, f'luci-app-modem-redial_{final_ver}_all.ipk')

# 确保输出目录干净，清理所有历史旧包与残留，只保留当前版本
os.makedirs(OUT_DIR, exist_ok=True)
for item in os.listdir(OUT_DIR):
    if item.endswith('.ipk') or item.endswith('.txt'):
        try:
            os.remove(os.path.join(OUT_DIR, item))
        except Exception:
            pass

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
Version: {final_ver}
Depends: python3
Section: luci
Architecture: all
Maintainer: aishlai
Description: LuCI Support for Beijing Unicom Huawei V271-20 ONT Auto-Redial Assistant (光猫重拨助手)
'''.encode('utf-8')

    conffiles_content = b'/etc/config/modem_redial\n'

    preinst_content = '''#!/bin/sh
[ -n "${IPKG_INSTROOT}" ] || {
    # 升级前备份已有配置，绝不丢失用户填写的光猫地址、密码与启用状态
    if [ -f /etc/config/modem_redial ]; then
        cp -f /etc/config/modem_redial /tmp/_modem_redial_cfg.bak 2>/dev/null || true
    fi
}
exit 0
'''.encode('utf-8')

    postinst_content = '''#!/bin/sh
[ -n "${IPKG_INSTROOT}" ] || {
    # 升级后恢复原有的用户配置
    if [ -f /tmp/_modem_redial_cfg.bak ]; then
        mv -f /tmp/_modem_redial_cfg.bak /etc/config/modem_redial 2>/dev/null || true
    fi
    rm -f /usr/lib/lua/luci/controller/modem_redial.lua \
          /usr/lib/lua/luci/model/cbi/modem_redial.lua \
          /usr/lib/lua/luci/view/modem_redial/status.htm 2>/dev/null || true
    rm -f /tmp/luci-indexcache*
    rm -rf /tmp/luci-modulecache/
    uci -q get ucitrack.@modem_redial[0] >/dev/null 2>&1 || {
        uci add ucitrack modem_redial
        uci set ucitrack.@modem_redial[-1].init="modem_redial"
        uci commit ucitrack
    }
    /etc/init.d/modem_redial enable
    /etc/init.d/modem_redial restart 2>/dev/null || true
}
exit 0
'''.encode('utf-8')
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
    add_mem_file('./conffiles', conffiles_content, 0o644)
    add_mem_file('./preinst', preinst_content, 0o755)
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

shutil.rmtree(TMP_DIR, ignore_errors=True)
print(f"==> [成功] IPK 安装包已生成至: {OUT_IPK}")
PYEOF
