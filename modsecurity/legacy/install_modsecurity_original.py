#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import shutil
import platform
import logging
import signal
from pathlib import Path
import tempfile
import argparse
import glob
import re

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('ModSecurity')

# 创建文件处理器
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modsecurity_install.log")
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

# 全局变量
BUILD_DIR = os.path.join(tempfile.gettempdir(), "modsecurity_build")

# 检测是否为宝塔环境
IS_BT_ENV = os.path.exists('/www/server/panel') or os.path.exists('/www/server/nginx')

# 根据环境设置Nginx路径
if IS_BT_ENV:
    NGINX_PATH = "/www/server/nginx"
    NGINX_BIN = "/www/server/nginx/sbin/nginx"
    NGINX_CONF = "/www/server/nginx/conf/nginx.conf"
    logger.info(f"检测到宝塔环境，设置Nginx路径为: {NGINX_PATH}")
    logger.info(f"Nginx可执行文件路径: {NGINX_BIN}")
    logger.info(f"Nginx配置文件路径: {NGINX_CONF}")
else:
    NGINX_PATH = "/etc/nginx"
    NGINX_BIN = "/usr/sbin/nginx"
    NGINX_CONF = "/etc/nginx/nginx.conf"
    logger.info(f"标准环境，设置Nginx路径为: {NGINX_PATH}")

# 信号处理函数，确保在脚本被中断时清理临时文件
def cleanup_handler(signum, frame):
    """在收到信号时清理临时文件"""
    logger.info(f"接收到信号 {signum}，正在清理临时文件...")
    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)
    logger.info("清理完成，退出")
    sys.exit(1)

# 注册信号处理函数
signal.signal(signal.SIGINT, cleanup_handler)  # Ctrl+C
signal.signal(signal.SIGTERM, cleanup_handler) # 终止信号

# 检测系统类型
def get_distro_family():
    """检测当前系统类型"""
    if os.path.exists('/etc/redhat-release') or os.path.exists('/etc/centos-release'):
        return 'rhel'
    elif os.path.exists('/etc/debian_version'):
        return 'debian'
    else:
        return 'unknown'

# 获取Nginx版本和编译信息的函数
def get_nginx_info(bt_env=False):
    """获取Nginx版本和编译信息
    
    Args:
        bt_env (bool): 是否为宝塔环境
        
    Returns:
        tuple: (nginx_version, configure_args, nginx_binary)
    """
    try:
        nginx_bin = "nginx"
        if bt_env:
            # 宝塔环境中Nginx可能在特定位置
            if os.path.exists("/www/server/nginx/sbin/nginx"):
                nginx_bin = "/www/server/nginx/sbin/nginx"
        
        # 获取Nginx版本
        nginx_version_output = subprocess.check_output(f"{nginx_bin} -v", shell=True, stderr=subprocess.STDOUT).decode()
        nginx_version_match = re.search(r'nginx/(\d+\.\d+\.\d+)', nginx_version_output)
        
        if not nginx_version_match:
            logger.error(f"无法解析Nginx版本信息: {nginx_version_output}")
            return None, None, nginx_bin
            
        nginx_version = nginx_version_match.group(1)
        logger.info(f"检测到Nginx版本: {nginx_version}")
        
        # 获取编译参数
        configure_args = subprocess.check_output(f"{nginx_bin} -V", shell=True, stderr=subprocess.STDOUT).decode()
        configure_match = re.search(r'configure arguments: (.*)', configure_args)
        
        if not configure_match:
            logger.error(f"无法获取Nginx配置参数: {configure_args}")
            return nginx_version, None, nginx_bin
            
        configure_args = configure_match.group(1)
        
        return nginx_version, configure_args, nginx_bin
        
    except Exception as e:
        logger.error(f"获取Nginx信息时出错: {e}")
        return None, None, "nginx"
        
# 检测系统类型并缓存
DISTRO_FAMILY = get_distro_family()
logger.info(f"检测到系统类型: {DISTRO_FAMILY}")

# 检查GCC版本是否支持C++17
def check_gcc_version():
    """检查GCC版本是否支持C++17，如果不支持则尝试安装更高版本"""
    try:
        # 检查当前GCC版本
        gcc_version_output = subprocess.check_output("gcc --version", shell=True, stderr=subprocess.STDOUT, universal_newlines=True)
        # 提取版本号
        version_match = re.search(r'\s(\d+\.\d+\.\d+)', gcc_version_output)
        if version_match:
            gcc_version = version_match.group(1)
            logger.info(f"检测到GCC版本: {gcc_version}")
            
            # 转换为数字进行比较
            major_version = int(gcc_version.split('.')[0])
            
            # GCC 7及以上版本支持C++17
            if major_version >= 7:
                logger.info("当前GCC版本支持C++17")
                return True
            else:
                logger.warning(f"当前GCC版本 {gcc_version} 不完全支持C++17，ModSecurity需要GCC 7或更高版本")
                return False
        else:
            logger.warning("无法确定GCC版本")
            return False
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.warning("系统上可能未安装GCC")
        return False

# 安装支持C++17的GCC版本
def install_newer_gcc(distro_family):
    """尝试安装支持C++17的更高版本GCC"""
    logger.info("尝试安装支持C++17的GCC版本...")
    
    try:
        if distro_family == 'debian':
            # 对于Ubuntu/Debian，添加toolchain PPA
            logger.info("为Ubuntu/Debian添加toolchain PPA...")
            subprocess.run("apt update", shell=True, check=True)
            subprocess.run("apt install -y software-properties-common", shell=True, check=True)
            subprocess.run("add-apt-repository -y ppa:ubuntu-toolchain-r/test", shell=True, check=True)
            subprocess.run("apt update", shell=True, check=True)
            subprocess.run("apt install -y gcc-7 g++-7", shell=True, check=True)
            # 设置GCC-7为默认版本
            subprocess.run("update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-7 60 --slave /usr/bin/g++ g++ /usr/bin/g++-7", shell=True, check=True)
            logger.info("已安装并设置GCC-7为默认版本")
            return True
        elif distro_family == 'rhel':
            # 对于CentOS/RHEL，使用SCL或Devtoolset
            logger.info("为CentOS/RHEL安装开发者工具集...")
            if os.path.exists("/etc/centos-release"):
                # CentOS
                subprocess.run("yum install -y centos-release-scl", shell=True, check=True)
                subprocess.run("yum install -y devtoolset-7-gcc devtoolset-7-gcc-c++", shell=True, check=True)
                # 添加到环境变量
                logger.info("添加devtoolset-7到环境...")
                os.environ["PATH"] = "/opt/rh/devtoolset-7/root/usr/bin:" + os.environ["PATH"]
                # 创建一个提示用户如何永久启用的消息
                logger.info("\n要在当前会话中启用GCC 7，请运行: source scl_source enable devtoolset-7")
                logger.info("要永久启用，请将以上命令添加到您的~/.bashrc文件中\n")
                return True
            else:
                # 其他RHEL类系统
                logger.warning("未能为您的RHEL系统找到适合的GCC 7安装方法")
                return False
        else:
            logger.warning(f"不支持为 {distro_family} 系统自动安装更新的GCC")
            return False
    except subprocess.CalledProcessError as e:
        logger.error(f"安装更新版本GCC失败: {e}")
        return False

def install_epel_repo():
    """安装EPEL仓库以提供额外的依赖包
    
    Returns:
        bool: 是否成功安装EPEL仓库
    """
    if DISTRO_FAMILY != 'rhel':
        logger.info("非CentOS/RHEL系统，跳过EPEL仓库安装")
        return True
    
    logger.info("尝试安装EPEL仓库以提供额外的依赖包...")
    
    # 检查是否已安装EPEL
    epel_installed = False
    try:
        subprocess.run("yum repolist | grep -i epel", shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        epel_installed = True
        logger.info("EPEL仓库已安装")
        return True
    except subprocess.CalledProcessError:
        logger.info("EPEL仓库未安装，将安装")
    
    # 获取CentOS版本信息
    centos_version = ""
    try:
        with open('/etc/centos-release', 'r') as f:
            centos_release = f.read().strip()
            version_match = re.search(r'release (\d+)\.', centos_release)
            if version_match:
                centos_version = version_match.group(1)
    except FileNotFoundError:
        logger.warning("无法读取CentOS版本信息，将尝试自动检测")
    
    # 针对不同版本安装合适的EPEL
    if centos_version == "7":
        # CentOS 7使用阿里云镜像安装EPEL
        try:
            logger.info("尝试从阿里云镜像安装CentOS 7的EPEL...")
            subprocess.run("yum install -y https://mirrors.aliyun.com/epel/epel-release-latest-7.noarch.rpm", 
                         shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            # 替换为国内镜像源
            subprocess.run("sed -i 's|^#baseurl=http://download.fedoraproject.org/pub/epel|baseurl=https://mirrors.aliyun.com/epel|g' /etc/yum.repos.d/epel*.repo", 
                         shell=True, check=True)
            subprocess.run("sed -i 's|^metalink|#metalink|g' /etc/yum.repos.d/epel*.repo", 
                         shell=True, check=True)
            logger.info("CentOS 7 EPEL仓库安装成功(阿里云镜像)")
            return True
        except subprocess.CalledProcessError:
            try:
                logger.warning("从阿里云安装失败，尝试官方源...")
                subprocess.run("yum install -y epel-release", shell=True, check=True)
                logger.info("CentOS 7 EPEL仓库安装成功(官方源)")
                return True
            except subprocess.CalledProcessError as e:
                logger.error(f"CentOS 7 EPEL仓库安装失败: {e}")
                return False
    elif centos_version == "8":
        # CentOS 8使用阿里云镜像安装EPEL
        try:
            logger.info("尝试从阿里云镜像安装CentOS 8的EPEL...")
            subprocess.run("yum install -y https://mirrors.aliyun.com/epel/epel-release-latest-8.noarch.rpm", 
                         shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            # 替换为国内镜像源
            subprocess.run("sed -i 's|^#baseurl=http://download.fedoraproject.org/pub/epel|baseurl=https://mirrors.aliyun.com/epel|g' /etc/yum.repos.d/epel*.repo", 
                         shell=True, check=True)
            subprocess.run("sed -i 's|^metalink|#metalink|g' /etc/yum.repos.d/epel*.repo", 
                         shell=True, check=True)
            logger.info("CentOS 8 EPEL仓库安装成功(阿里云镜像)")
            return True
        except subprocess.CalledProcessError:
            try:
                logger.warning("从阿里云安装失败，尝试官方源...")
                subprocess.run("yum install -y epel-release", shell=True, check=True)
                logger.info("CentOS 8 EPEL仓库安装成功(官方源)")
                return True
            except subprocess.CalledProcessError as e:
                logger.error(f"CentOS 8 EPEL仓库安装失败: {e}")
                return False
    else:
        # 未知版本，尝试通用安装
        try:
            logger.info("未检测到版本信息，尝试安装EPEL...")
            subprocess.run("yum install -y epel-release", shell=True, check=True)
            logger.info("EPEL仓库安装成功")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"EPEL仓库安装失败: {e}")
            return False


def fix_centos_yum_mirrors():
    """修复CentOS的YUM镜像源问题
    
    禁用fastmirror插件，备份并替换为阿里云或清华源
    
    Returns:
        bool: 是否成功修复镜像源
    """
    if DISTRO_FAMILY != 'rhel':
        logger.info("非CentOS/RHEL系统，跳过YUM镜像源修复")
        return True
    
    logger.info("开始修复CentOS YUM镜像源...")
    
    # 检测CentOS版本
    centos_version = "7"  # 默认值
    try:
        if os.path.exists("/etc/centos-release"):
            with open("/etc/centos-release", "r") as f:
                version_line = f.read().strip()
                match = re.search(r'release\s+(\d+)', version_line)
                if match:
                    centos_version = match.group(1)
                    logger.info(f"检测到CentOS版本: {centos_version}")
    except Exception as e:
        logger.warning(f"检测系统版本失败，将使用默认版本 {centos_version}: {e}")
    
    # 检查并禁用fastmirror插件
    fastmirror_conf = "/etc/yum/pluginconf.d/fastestmirror.conf"
    if os.path.exists(fastmirror_conf):
        logger.info("检测到fastmirror插件，尝试禁用...")
        try:
            # 备份原配置
            backup_file = f"{fastmirror_conf}.bak"
            if not os.path.exists(backup_file):
                shutil.copy2(fastmirror_conf, backup_file)
            
            # 读取并修改配置
            with open(fastmirror_conf, 'r') as f:
                content = f.read()
            
            # 替换enabled=1为enabled=0
            content = re.sub(r'enabled\s*=\s*1', 'enabled=0', content)
            
            # 写回配置
            with open(fastmirror_conf, 'w') as f:
                f.write(content)
                
            logger.info("已成功禁用fastmirror插件")
        except Exception as e:
            logger.warning(f"禁用fastmirror插件失败: {e}")
    
    # 备份现有YUM源配置
    backup_dir = "/etc/yum.repos.d/original_backup"
    os.makedirs(backup_dir, exist_ok=True)
    
    # 备份所有.repo文件
    repo_files = glob.glob("/etc/yum.repos.d/*.repo")
    if repo_files:
        for repo_file in repo_files:
            backup_file = os.path.join(backup_dir, os.path.basename(repo_file))
            if not os.path.exists(backup_file):
                logger.info(f"备份仓库文件 {repo_file} 到 {backup_file}")
                shutil.copy2(repo_file, backup_file)
            
            # 暂时禁用原始文件
            disabled_file = f"{repo_file}.disabled"
            if not os.path.exists(disabled_file):
                os.rename(repo_file, disabled_file)
    
    # 创建阿里云镜像源配置
    is_centos_eol = centos_version in ["7", "8"]
    
    if is_centos_eol:
        logger.info(f"检测到CentOS {centos_version} EOL版本，使用vault归档镜像")
        
        # 针对CentOS 7
        if centos_version == "7":
            mirror_conf = f"""# CentOS {centos_version} - 阿里云镜像
[base]
name=CentOS-{centos_version} - Base
baseurl=https://mirrors.aliyun.com/centos-vault/7.9.2009/os/$basearch/
gpgcheck=0
enabled=1

[updates]
name=CentOS-{centos_version} - Updates
baseurl=https://mirrors.aliyun.com/centos-vault/7.9.2009/updates/$basearch/
gpgcheck=0
enabled=1

[extras]
name=CentOS-{centos_version} - Extras
baseurl=https://mirrors.aliyun.com/centos-vault/7.9.2009/extras/$basearch/
gpgcheck=0
enabled=1

# EPEL仓库
[epel]
name=Extra Packages for Enterprise Linux {centos_version}
baseurl=https://mirrors.aliyun.com/epel/{centos_version}/$basearch
enabled=1
gpgcheck=0
"""
        # 针对CentOS 8
        elif centos_version == "8":
            mirror_conf = f"""# CentOS {centos_version} - 阿里云镜像
[base]
name=CentOS-{centos_version} - Base
baseurl=https://mirrors.aliyun.com/centos-vault/8.5.2111/BaseOS/$basearch/os/
gpgcheck=0
enabled=1

[appstream]
name=CentOS-{centos_version} - AppStream
baseurl=https://mirrors.aliyun.com/centos-vault/8.5.2111/AppStream/$basearch/os/
gpgcheck=0
enabled=1

[extras]
name=CentOS-{centos_version} - Extras
baseurl=https://mirrors.aliyun.com/centos-vault/8.5.2111/extras/$basearch/os/
gpgcheck=0
enabled=1

# EPEL仓库
[epel]
name=Extra Packages for Enterprise Linux {centos_version}
baseurl=https://mirrors.aliyun.com/epel/{centos_version}/Everything/$basearch
enabled=1
gpgcheck=0
"""
        else:
            # 一般情况下不会到这里
            mirror_conf = ""
    else:
        # 非EOL版本使用标准镜像
        mirror_conf = f"""# CentOS {centos_version} - 阿里云镜像
[base]
name=CentOS-{centos_version} - Base
baseurl=https://mirrors.aliyun.com/centos/{centos_version}/BaseOS/$basearch/os/
gpgcheck=0
enabled=1

[appstream]
name=CentOS-{centos_version} - AppStream
baseurl=https://mirrors.aliyun.com/centos/{centos_version}/AppStream/$basearch/os/
gpgcheck=0
enabled=1

[extras]
name=CentOS-{centos_version} - Extras
baseurl=https://mirrors.aliyun.com/centos/{centos_version}/extras/$basearch/os/
gpgcheck=0
enabled=1

# EPEL仓库
[epel]
name=Extra Packages for Enterprise Linux {centos_version}
baseurl=https://mirrors.aliyun.com/epel/{centos_version}/Everything/$basearch
enabled=1
gpgcheck=0
"""
    
    # 写入阿里云镜像配置
    try:
        mirror_file = "/etc/yum.repos.d/aliyun-mirror.repo"
        with open(mirror_file, 'w') as f:
            f.write(mirror_conf)
        logger.info("成功创建阿里云镜像源配置")
    except Exception as e:
        logger.error(f"创建镜像源配置失败: {e}")
        return False
    
    # 清理缓存并测试
    try:
        logger.info("清理YUM缓存并刷新...")
        subprocess.run("yum clean all", shell=True, check=True)
        subprocess.run("yum makecache", shell=True, check=True)
        
        # 测试仓库是否可访问
        test_cmd = "yum repolist"
        subprocess.run(test_cmd, shell=True, check=True)
        
        logger.info("YUM镜像源配置成功，仓库可访问")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"镜像源测试失败，尝试使用清华源: {e}")
        
        # 尝试使用清华源
        try:
            # 删除阿里云配置
            if os.path.exists(mirror_file):
                os.remove(mirror_file)
            
            # 创建清华源配置
            if centos_version == "7":
                tsinghua_conf = f"""# CentOS {centos_version} - 清华镜像
[base]
name=CentOS-{centos_version} - Base
baseurl=https://mirrors.tuna.tsinghua.edu.cn/centos-vault/7.9.2009/os/$basearch/
gpgcheck=0
enabled=1

[updates]
name=CentOS-{centos_version} - Updates
baseurl=https://mirrors.tuna.tsinghua.edu.cn/centos-vault/7.9.2009/updates/$basearch/
gpgcheck=0
enabled=1

[extras]
name=CentOS-{centos_version} - Extras
baseurl=https://mirrors.tuna.tsinghua.edu.cn/centos-vault/7.9.2009/extras/$basearch/
gpgcheck=0
enabled=1

# EPEL仓库
[epel]
name=Extra Packages for Enterprise Linux {centos_version}
baseurl=https://mirrors.tuna.tsinghua.edu.cn/epel/{centos_version}/$basearch
enabled=1
gpgcheck=0
"""
            elif centos_version == "8":
                tsinghua_conf = f"""# CentOS {centos_version} - 清华镜像
[base]
name=CentOS-{centos_version} - Base
baseurl=https://mirrors.tuna.tsinghua.edu.cn/centos-vault/8.5.2111/BaseOS/$basearch/os/
gpgcheck=0
enabled=1

[appstream]
name=CentOS-{centos_version} - AppStream
baseurl=https://mirrors.tuna.tsinghua.edu.cn/centos-vault/8.5.2111/AppStream/$basearch/os/
gpgcheck=0
enabled=1

[extras]
name=CentOS-{centos_version} - Extras
baseurl=https://mirrors.tuna.tsinghua.edu.cn/centos-vault/8.5.2111/extras/$basearch/os/
gpgcheck=0
enabled=1

# EPEL仓库
[epel]
name=Extra Packages for Enterprise Linux {centos_version}
baseurl=https://mirrors.tuna.tsinghua.edu.cn/epel/{centos_version}/Everything/$basearch
enabled=1
gpgcheck=0
"""
            else:
                # 非EOL版本
                tsinghua_conf = f"""# CentOS {centos_version} - 清华镜像
[base]
name=CentOS-{centos_version} - Base
baseurl=https://mirrors.tuna.tsinghua.edu.cn/centos/{centos_version}/BaseOS/$basearch/os/
gpgcheck=0
enabled=1

[appstream]
name=CentOS-{centos_version} - AppStream
baseurl=https://mirrors.tuna.tsinghua.edu.cn/centos/{centos_version}/AppStream/$basearch/os/
gpgcheck=0
enabled=1

[extras]
name=CentOS-{centos_version} - Extras
baseurl=https://mirrors.tuna.tsinghua.edu.cn/centos/{centos_version}/extras/$basearch/os/
gpgcheck=0
enabled=1

# EPEL仓库
[epel]
name=Extra Packages for Enterprise Linux {centos_version}
baseurl=https://mirrors.tuna.tsinghua.edu.cn/epel/{centos_version}/Everything/$basearch
enabled=1
gpgcheck=0
"""
            
            # 写入清华源配置
            tsinghua_file = "/etc/yum.repos.d/tsinghua-mirror.repo"
            with open(tsinghua_file, 'w') as f:
                f.write(tsinghua_conf)
            
            # 再次测试
            logger.info("清理YUM缓存并使用清华源测试...")
            subprocess.run("yum clean all", shell=True, check=True)
            subprocess.run("yum makecache", shell=True, check=True)
            subprocess.run("yum repolist", shell=True, check=True)
            
            logger.info("清华源配置成功，仓库可访问")
            return True
        except Exception as e2:
            logger.error(f"清华源也配置失败: {e2}")
            
            # 恢复原始配置
            for disabled_file in glob.glob("/etc/yum.repos.d/*.disabled"):
                original_file = disabled_file.replace(".disabled", "")
                try:
                    os.rename(disabled_file, original_file)
                except Exception:
                    pass
            
            logger.error("无法配置可用的YUM源，请手动配置软件源后重试")
            return False

# 安装系统依赖
def install_dependencies():
    """安装ModSecurity所需的系统依赖"""
    logger.info("安装系统依赖...")
    
    distro_family = DISTRO_FAMILY  # 使用全局缓存的系统类型
    
    # 检测是否为宝塔环境
    if IS_BT_ENV:
        logger.info("检测到宝塔面板环境，跳过Nginx安装")
    
    # 检测是否已安装Nginx
    nginx_installed = False
    try:
        # 使用新函数获取Nginx信息
        nginx_version, _, _ = get_nginx_info(IS_BT_ENV)
        if nginx_version:
            nginx_installed = True
            logger.info(f"检测到系统中已安装Nginx v{nginx_version}，跳过Nginx安装")
    except Exception:
        logger.info("未检测到Nginx，将进行安装")
        nginx_installed = False
    
    if distro_family == 'rhel':
        # CentOS/RHEL系统
        dependencies = [
            "git", "gcc", "gcc-c++", "make", "automake", "autoconf", "libtool", 
            "pcre-devel", "libxml2-devel", "curl-devel", "openssl-devel", 
            "yajl-devel", "libmaxminddb-devel", "lua-devel",
            # 添加更多必要的开发包
            "zlib-devel", "gd-devel", "perl-devel", "perl-ExtUtils-Embed",
            "kernel-devel", "cmake", 
            # 添加GeoIP库的依赖，修复“the GeoIP module requires the GeoIP library”错误
            "GeoIP", "GeoIP-devel"
        ]
        # 如果未安装nginx且不是宝塔环境，添加nginx依赖
        if not nginx_installed and not IS_BT_ENV:
            dependencies.append("nginx")
            logger.info("将安装Nginx服务器")
        else:
            logger.info("跳过Nginx安装，使用现有Nginx")
        cmd = f"yum install -y {' '.join(dependencies)}"
    elif distro_family == 'debian':
        # Debian/Ubuntu系统
        dependencies = [
            "git", "build-essential", "automake", "autoconf", "libtool", 
            "libpcre3-dev", "libxml2-dev", "libcurl4-openssl-dev", "libssl-dev", 
            "libyajl-dev", "libmaxminddb-dev", "liblua5.3-dev",
            # 添加更多必要的开发包，特别是Ubuntu系统需要的
            "zlib1g-dev", "gcc", "g++", "make", "cmake", "pkg-config",
            # 添加GeoIP库的依赖，修复“the GeoIP module requires the GeoIP library”错误
            "libgeoip-dev", "libgeoip1"
        ]
        # 如果未安装nginx且不是宝塔环境，添加nginx依赖
        if not nginx_installed and not IS_BT_ENV:
            dependencies.append("nginx")
            logger.info("将安装Nginx服务器")
        else:
            logger.info("跳过Nginx安装，使用现有Nginx")
            
        # 定义关键依赖包，这些是编译必须的
        critical_deps = ["build-essential", "libpcre3-dev", "libxml2-dev", "libcurl4-openssl-dev"]
        
        cmd = f"apt update && apt install -y {' '.join(dependencies)}"
    else:
        logger.error("不支持的系统类型")
        sys.exit(1)
    
    # 使用分段安装策略和更好的错误处理
    if distro_family == 'rhel':
        # 首先尝试安装EPEL仓库来提供更多依赖包
        epel_installed = install_epel_repo()
        if epel_installed:
            logger.info("成功添加EPEL仓库，这将提供更多依赖包")
            subprocess.run("yum clean all && yum makecache", shell=True, check=False)
        else:
            logger.warning("无法安装EPEL仓库，某些依赖包可能不可用")
    
    # 分批安装依赖，以防单个包失败影响全局
    missing_packages = []
    
    try:
        # 捕获过程的输出以进行详细错误分析
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            logger.warning("部分依赖安装可能失败")
            logger.debug(f"stdout: {stdout}")
            logger.debug(f"stderr: {stderr}")
            
            # 分析错误并提供更有用的提示
            if "Could not resolve host" in stderr:
                logger.error("检测到DNS解析问题，无法连接到软件仓库")
                logger.error("请检查系统的网络连接或使用 --skip-deps 参数跳过依赖安装")
                raise subprocess.CalledProcessError(process.returncode, cmd, output=stdout, stderr=stderr)
            
            # 检测是否有缺失的包
            if "No package" in stderr or "nothing provides" in stderr.lower() or "E: Unable to locate package" in stderr:
                # 提取缺失的包名称
                missing_package_matches = re.findall(r'No package ([\w-]+) available', stderr)
                missing_package_matches.extend(re.findall(r'nothing provides ([\w-]+) needed', stderr.lower()))
                missing_package_matches.extend(re.findall(r'E: Unable to locate package ([\w-]+)', stderr))
                
                for pkg in missing_package_matches:
                    missing_packages.append(pkg)
                    logger.warning(f"软件包 {pkg} 在当前系统的仓库中不可用")
                
                # 尝试一个一个安装其余的依赖包
                logger.info("将尝试单独安装每个依赖包，已跳过不可用的包")
                for dep in dependencies:
                    if dep not in missing_packages:
                        try:
                            if distro_family == 'rhel':
                                install_cmd = f"yum install -y {dep}"
                            else:  # debian
                                install_cmd = f"apt install -y {dep}"
                            
                            subprocess.run(install_cmd, shell=True, check=True, 
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                            logger.info(f"成功安装依赖: {dep}")
                        except subprocess.CalledProcessError:
                            missing_packages.append(dep)
                            logger.warning(f"无法安装依赖: {dep}")
                
                # 对于Debian/Ubuntu系统，单独再次尝试安装关键依赖
                if distro_family == 'debian' and 'critical_deps' in locals():
                    logger.info("尝试单独安装关键编译依赖...")
                    for critical_dep in critical_deps:
                        if critical_dep not in missing_packages:
                            try:
                                install_cmd = f"apt install -y {critical_dep}"
                                subprocess.run(install_cmd, shell=True, check=True,
                                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                                logger.info(f"成功安装关键依赖: {critical_dep}")
                            except subprocess.CalledProcessError:
                                missing_packages.append(critical_dep)
                                logger.warning(f"无法安装关键依赖: {critical_dep}")
        else:
            logger.info("依赖安装完成")
    except subprocess.CalledProcessError as e:
        logger.error(f"依赖安装过程出错: {e}")
        # 在DNS错误等严重问题下才会执行到这里
        raise
    
    # 如果有缺失的包，给出具体的解决方案
    if missing_packages:
        logger.warning(f"共有 {len(missing_packages)} 个依赖包无法安装: {', '.join(missing_packages)}")
        
        # 检查是否缺失关键依赖
        critical_missing = False
        if distro_family == 'debian' and 'critical_deps' in locals():
            critical_missing = any(dep in missing_packages for dep in critical_deps)
            if critical_missing:
                logger.warning("安装无法成功编译ModSecurity所需的关键依赖")
        
        # RHEL系统特定的建议
        if distro_family == 'rhel':
            logger.info("对于CentOS/RHEL系统，可尝试以下方法来安装缺失的依赖:")
            logger.info("1. 激活 PowerTools 或 CRB 仓库(如适用):")
            logger.info("   sudo yum config-manager --set-enabled powertools")
            logger.info("   或者: sudo yum config-manager --set-enabled crb")
            logger.info("2. 尝试其他软件源，如 Remi's RPM 仓库或者 IUS:")
            logger.info("   https://rpms.remirepo.net/ 或 https://ius.io/")
            logger.info("3. 如果可能，升级系统至更新版本")
        # Debian系统特定的建议
        else:  
            logger.info("对于Debian/Ubuntu系统，可尝试以下方法来安装缺失的依赖:")
            logger.info("1. 激活额外的软件源: sudo apt-add-repository universe")
            logger.info("2. 更新软件源列表: sudo apt update")
            logger.info("3. 手动安装关键编译包: sudo apt install build-essential libpcre3-dev libxml2-dev libcurl4-openssl-dev")
            
        logger.info("脚本将继续执行，但可能会在编译过程中遇到问题")

# 下载ModSecurity库
def download_modsecurity(force_update=False):
    """下载ModSecurity核心库
    
    Args:
        force_update (bool, optional): 强制重新编译ModSecurity模块，即使已存在也会更新。默认为False。
    """
    logger.info("下载ModSecurity...")
    os.chdir(BUILD_DIR)
    
    # 设置ModSecurity版本
    MODSEC_VERSION = "3.0.14"
    
    # 优先尝试从supine-win的Gitee镜像下载源码
    try:
        logger.info("尝试从supine-win的Gitee镜像下载ModSecurity源码...")
        subprocess.run("git clone https://gitee.com/supine-win/ModSecurity.git modsecurity", 
                     shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.info("从supine-win的Gitee镜像下载ModSecurity源码成功")
        download_success = True
    except subprocess.CalledProcessError as e:
        logger.error(f"从supine-win的镜像下载ModSecurity源码失败: {e}")
        logger.warning("从supine-win的镜像下载失败，尝试官方Gitee镜像")
        download_success = False
    
    # 如果上一步失败，尝试官方Gitee镜像
    if not download_success:
        try:
            logger.info("尝试从Gitee官方镜像下载ModSecurity源码...")
            subprocess.run("git clone https://gitee.com/mirrors/ModSecurity.git modsecurity", 
                         shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.info("从Gitee官方镜像下载ModSecurity源码成功")
            download_success = True
        except subprocess.CalledProcessError:
            logger.warning("从Gitee镜像下载失败，尝试从GitHub下载")
            download_success = False
    
    # 如果上一步失败，作为最后尝试从GitHub下载源码
    if not download_success:
        try:
            logger.info("尝试从GitHub下载ModSecurity源码...")
            subprocess.run("git clone https://github.com/SpiderLabs/ModSecurity.git modsecurity", 
                         shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.info("从GitHub下载ModSecurity源码成功")
            download_success = True
        except subprocess.CalledProcessError:
            logger.error("无法下载ModSecurity源码，请检查网络连接")
            sys.exit(1)
    
    # 检查模块文件是否已存在
    modules_dir = os.path.join(NGINX_PATH, "modules")
    module_file = os.path.join(modules_dir, "ngx_http_modsecurity_module.so")
    module_exists = os.path.exists(module_file)

    # 编译并安装ModSecurity
    try:
        os.chdir(os.path.join(BUILD_DIR, "modsecurity"))
        
        # 初始化子模块
        logger.info("初始化子模块...")
        print("+++ 执行: git submodule init +++")
        subprocess.run("git submodule init", shell=True, check=True)
        print("+++ 执行: git submodule update +++")
        subprocess.run("git submodule update", shell=True, check=True)
        
        # 如果模块已存在且不是强制更新，跳过编译步骤
        if module_exists and not force_update:
            logger.info(f"检测到ModSecurity模块已存在: {module_file}")
            logger.info("跳过ModSecurity的编译和安装步骤")
            return
        
        # 如果强制更新模式且模块存在
        if module_exists and force_update:
            logger.info(f"强制更新模式: 将重新编译ModSecurity模块")
        
        # 检查GCC版本是否支持C++17
        gcc_supports_cpp17 = check_gcc_version()
        if not gcc_supports_cpp17:
            logger.warning("ModSecurity编译需要支持C++17的GCC 7或更高版本")
            gcc_upgraded = install_newer_gcc(DISTRO_FAMILY)
            if gcc_upgraded:
                logger.info("成功安装支持C++17的GCC版本")
            else:
                logger.error("无法安装支持C++17的GCC版本，编译可能会失败")
                logger.error("您可能需要手动安装GCC 7+或尝试使用预编译的ModSecurity模块")
                logger.info("尝试继续编译，但可能会失败...")
            
        # 构建和编译
        logger.info("开始编译ModSecurity...")
        print("+++ 执行: ./build.sh +++")
        subprocess.run("./build.sh", shell=True, check=True)
        print("+++ 执行: ./configure +++")
        subprocess.run("./configure", shell=True, check=True)
        print("+++ 执行: make +++")
        subprocess.run("make", shell=True, check=True)
        print("+++ 执行: make install +++")
        subprocess.run("make install", shell=True, check=True)
        
        logger.info("ModSecurity编译安装完成")
    except subprocess.CalledProcessError as e:
        logger.error(f"ModSecurity编译安装失败: {e}")
        sys.exit(1)
    


# 下载和安装ModSecurity-nginx连接器
def install_modsecurity_nginx(force_update=False):
    """下载和安装ModSecurity-nginx连接器
    
    Args:
        force_update (bool, optional): 强制重新编译ModSecurity模块，即使已存在也会更新。默认为False。
    """
    logger.info("下载ModSecurity-nginx连接器...")
    
    # 检查模块文件是否已存在
    modules_dir = os.path.join(NGINX_PATH, "modules")
    module_file = os.path.join(modules_dir, "ngx_http_modsecurity_module.so")
    if os.path.exists(module_file) and not force_update:
        logger.info(f"检测到ModSecurity模块已存在: {module_file}")
        logger.info("跳过ModSecurity-nginx模块编译和安装")
        return
        
    # 如果强制更新模式且模块存在
    if os.path.exists(module_file) and force_update:
        logger.info(f"强制更新模式: 将重新编译ModSecurity-nginx模块")
        # 移除现有模块文件以确保更新
        try:
            os.remove(module_file)
            logger.info(f"已移除现有模块文件: {module_file}")
        except Exception as e:
            logger.warning(f"无法移除现有模块文件: {e}")
        
    os.chdir(BUILD_DIR)

    # 优先尝试从supine-win的Gitee镜像下载源码
    download_success = False
    try:
        logger.info("尝试从supine-win的Gitee镜像下载ModSecurity-nginx源码...")
        subprocess.run("git clone https://gitee.com/supine-win/ModSecurity-nginx.git modsecurity-nginx", 
                     shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.info("从supine-win的Gitee镜像下载ModSecurity-nginx成功")
        download_success = True
    except subprocess.CalledProcessError:
        logger.warning("从supine-win的镜像下载失败，尝试官方Gitee镜像")
    
    # 如果上一步失败，尝试官方Gitee镜像
    if not download_success:
        try:
            logger.info("尝试从Gitee官方镜像下载ModSecurity-nginx源码...")
            subprocess.run("git clone https://gitee.com/mirrors/ModSecurity-nginx.git modsecurity-nginx", 
                         shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.info("从Gitee官方镜像下载ModSecurity-nginx源码成功")
            download_success = True
        except subprocess.CalledProcessError:
            logger.warning("从Gitee镜像下载失败，尝试从GitHub下载")
    
    # 如果上一步失败，作为最后尝试从GitHub下载源码
    if not download_success:
        try:
            logger.info("尝试从GitHub下载ModSecurity-nginx源码...")
            subprocess.run("git clone https://github.com/SpiderLabs/ModSecurity-nginx.git modsecurity-nginx", 
                         shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.info("从GitHub下载ModSecurity-nginx源码成功")
            download_success = True
        except subprocess.CalledProcessError:
            logger.error("无法下载ModSecurity-nginx源码，请检查网络连接")
            sys.exit(1)
    
    # 获取Nginx版本和源码
    try:
        # 获取Nginx版本和编译信息
        nginx_version, configure_args, nginx_bin = get_nginx_info(IS_BT_ENV)
        
        if not nginx_version:
            logger.error("无法获取Nginx版本，请确保Nginx已安装并可访问")
            sys.exit(1)
        
        # 下载Nginx源码
        logger.info(f"下载Nginx v{nginx_version} 源码...")
        os.chdir(BUILD_DIR)
        nginx_src_url = f"http://nginx.org/download/nginx-{nginx_version}.tar.gz"
        
        # 尝试不同的源下载Nginx
        try:
            # 尝试Gitee镜像
            gitee_nginx_url = f"https://gitee.com/mirrors/nginx/raw/master/nginx-{nginx_version}.tar.gz"
            subprocess.run(f"wget -q {gitee_nginx_url} -O nginx.tar.gz", shell=True, check=True)
            logger.info("从Gitee镜像下载Nginx源码成功")
        except subprocess.CalledProcessError:
            # 如果失败，使用原始链接
            logger.warning("从Gitee镜像下载Nginx失败，尝试官方源")
            subprocess.run(f"wget -q {nginx_src_url} -O nginx.tar.gz", shell=True, check=True)
            logger.info("从nginx.org下载Nginx源码成功")
        
        subprocess.run("tar -xzf nginx.tar.gz", shell=True, check=True)
        nginx_src_dir = f"nginx-{nginx_version}"
        
        # 编译Nginx模块
        logger.info("开始编译Nginx ModSecurity模块...")
        os.chdir(os.path.join(BUILD_DIR, nginx_src_dir))
        
        # configure_args已在前面获取
        if not configure_args:
            logger.error("无法获取Nginx编译参数，将使用默认参数，可能导致模块不兼容")
            # 设置默认的基本编译参数
            configure_args = "--prefix=/usr/share/nginx --sbin-path=/usr/sbin/nginx --modules-path=/usr/lib/nginx/modules"
        
        # 使用全局缓存的系统类型
        distro_family = DISTRO_FAMILY
        
        # 宝塔环境特殊处理
        if IS_BT_ENV:
            logger.info("检测到宝塔环境，将针对性优化编译参数...")
            
            # 检查宝塔Nginx的编译选项
            bt_specific_options = []
            
            # 获取宝塔Nginx的configure_args
            if "--with-openssl" in configure_args:
                # 提取原来的openssl路径
                openssl_path_match = re.search(r'--with-openssl=([^ ]+)', configure_args)
                if openssl_path_match:
                    openssl_path = openssl_path_match.group(1)
                    # 如果路径存在，使用它，否则使用系统默认的
                    if os.path.exists(openssl_path):
                        bt_specific_options.append(f"--with-openssl={openssl_path}")
                    else:
                        # 移除这个选项，使用系统的OpenSSL
                        configure_args = re.sub(r'--with-openssl=[^ ]+', '', configure_args)
            
            # 确保添加了正确的模块路径
            if IS_BT_ENV and "--modules-path" not in configure_args:
                configure_args += " --modules-path=/www/server/nginx/modules"
        
        # 如果系统中没有libperl-dev包，移除perl模块选项减少编译问题
        if "--with-http_perl_module" in configure_args or "--with-http_perl_module=dynamic" in configure_args:
            # 尝试检查libperl-dev是否安装
            perl_dev_installed = False
            try:
                if distro_family == 'debian':
                    result = subprocess.run("dpkg -l | grep libperl-dev", shell=True, 
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    perl_dev_installed = result.returncode == 0
                elif distro_family == 'rhel':
                    result = subprocess.run("rpm -qa | grep perl-devel", shell=True, 
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    perl_dev_installed = result.returncode == 0
            except:
                pass
                
            if not perl_dev_installed:
                # 如果未安装，由于PERL模块常常导致问题，这里选择移除Perl模块
                logger.warning("检测到Nginx配置中含有Perl模块，但系统中没有完整的Perl开发环境")
                logger.warning("为确保成功编译，将从配置中移除Perl模块")
                # 从配置中移除Perl模块
                configure_args = re.sub(r'--with-http_perl_module[=\w]*', '', configure_args)
                logger.info("已禁用Perl模块，以确保编译成功")
        
        # 确保GeoIP库已安装，而不是移除GeoIP模块
        logger.info("确保安装GeoIP库以支持GeoIP模块...")
        
        # 确保安装GeoIP库
        try:
            if distro_family == 'debian':
                # 安装GeoIP相关库
                geoip_packages = ["libgeoip-dev", "libgeoip1", "geoip-bin"]
                print(f"+++ 执行: apt-get install -y {' '.join(geoip_packages)} +++")
                subprocess.run(["apt-get", "install", "-y"] + geoip_packages, check=True)
                
                # 安装Perl开发库，解决 "cannot find -lperl" 错误
                perl_packages = ["libperl-dev", "perl"]
                print(f"+++ 执行: apt-get install -y {' '.join(perl_packages)} +++")
                subprocess.run(["apt-get", "install", "-y"] + perl_packages, check=True)
                logger.info("已安装Debian/Ubuntu系统的GeoIP库")
            elif distro_family == 'rhel':
                # 安装GeoIP相关库
                geoip_packages = ["GeoIP", "GeoIP-devel", "geoipupdate"]
                print(f"+++ 执行: yum install -y {' '.join(geoip_packages)} +++")
                subprocess.run(["yum", "install", "-y"] + geoip_packages, check=True)
                
                # 安装Perl开发库，解决 "cannot find -lperl" 错误
                perl_packages = ["perl", "perl-devel", "perl-ExtUtils-Embed"]
                print(f"+++ 执行: yum install -y {' '.join(perl_packages)} +++")
                subprocess.run(["yum", "install", "-y"] + perl_packages, check=True)
                logger.info("已安装CentOS/RHEL系统的GeoIP库")
            else:
                logger.warning("无法识别系统类型，请手动安装GeoIP库")
                logger.warning("对于Debian/Ubuntu系统，使用: apt-get install -y libgeoip-dev libgeoip1 geoip-bin")
                logger.warning("对于CentOS/RHEL系统，使用: yum install -y GeoIP GeoIP-devel geoipupdate")
        except subprocess.CalledProcessError as e:
            logger.error(f"安装GeoIP库失败: {str(e)}")
            logger.warning("将尝试继续编译，但可能会遇到GeoIP相关错误")
        
        # 添加ModSecurity模块
        modsec_nginx_path = os.path.join(BUILD_DIR, "modsecurity-nginx")
        
        # 检查是否已经有PCRE库文件夹
        pcre_pattern = re.compile(r'pcre-\d+\.\d+')
        pcre_dir_exists = False
        
        # 检查当前目录下是否存在PCRE库文件夹
        for item in os.listdir(os.getcwd()):
            if os.path.isdir(item) and pcre_pattern.match(item):
                logger.info(f"检测到已存在PCRE库: {item}，跳过下载")
                pcre_dir_exists = True
                break
        
        if not pcre_dir_exists:
            logger.info("检测到缺少PCRE库，正在下载...")
            try:
                # 尝试下载最新的PCRE库
                pcre_urls = [
                    "https://github.com/PCRE2Project/pcre2/releases/download/pcre2-10.42/pcre2-10.42.tar.gz",
                    "https://ftp.exim.org/pub/pcre/pcre-8.45.tar.gz",
                    "https://ftp.pcre.org/pub/pcre/pcre-8.45.tar.gz"
                ]
                
                downloaded = False
                for url in pcre_urls:
                    try:
                        pcre_file = os.path.join(os.getcwd(), os.path.basename(url))
                        logger.info(f"尝试从{url}下载PCRE库...")
                        subprocess.run(f"curl -L {url} -o {pcre_file}", shell=True, check=True)
                        
                        # 解压PCRE库
                        logger.info("解压PCRE库...")
                        subprocess.run(f"tar -xzf {pcre_file}", shell=True, check=True)
                        logger.info("PCRE库准备完成")
                        
                        downloaded = True
                        break
                    except subprocess.CalledProcessError:
                        logger.warning(f"从{url}下载PCRE库失败，尝试下一个源...")
                
                if not downloaded:
                    logger.error("所有PCRE库源下载失败")
                    logger.warning("将尝试继续编译，但可能会失败")
            except Exception as e:
                logger.error(f"下载PCRE库失败: {str(e)}")
                logger.warning("将尝试继续编译，但可能会失败")
        
        # 构建编译命令
        # 注意：当在Nginx源码目录中存在pcre-*目录时，Nginx会优先使用该目录的PCRE库
        compile_cmd = f"./configure {configure_args} --add-dynamic-module={modsec_nginx_path}"
        print(f"+++ 执行: {compile_cmd} +++")
        try:
            # 捕获并保存所有输出，便于调试
            process = subprocess.Popen(compile_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            stdout, stderr = process.communicate()
            
            # 显示所有输出
            if stdout:
                print("Configure 标准输出:")
                print(stdout)
                
            # 如果返回非零状态，显示错误并退出
            if process.returncode != 0:
                print("\n\nConfigure 错误输出:")
                print(stderr)
                # 检查常见的错误原因
                missing_deps = []
                if "not found" in stderr:
                    missing_deps.append("缺少依赖库")
                if "error: C" in stderr:
                    missing_deps.append("编译器错误")
                if "fatal error:" in stderr and ".h" in stderr:
                    # 寻找缺失的头文件
                    missing_headers = re.findall(r'fatal error: ([\w\/\.]+\.h)', stderr)
                    if missing_headers:
                        for header in missing_headers:
                            missing_deps.append(f"缺少头文件 {header}")
                    
                error_msg = "编译配置失败"
                if missing_deps:
                    error_msg += ": " + ", ".join(missing_deps)
                
                logger.error(f"{error_msg}\n请检查编译环境并确保所有依赖项已安装")
                
                # 根据系统类型提供不同的建议
                if distro_family == 'debian':
                    logger.error("请尝试手动安装以下开发包: build-essential libpcre3-dev libxml2-dev libcurl4-openssl-dev")
                    logger.error("您可能需要运行: sudo apt update && sudo apt upgrade -y")
                else:  # rhel
                    logger.error("请尝试手动安装以下开发包: gcc gcc-c++ make automake pcre-devel libxml2-devel curl-devel")
                
                sys.exit(1)
        
            print("+++ 执行: make modules +++")
            # 同样捕获make命令的输出
            process = subprocess.Popen("make modules", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            stdout, stderr = process.communicate()
            
            if stdout:
                print("Make 标准输出:")
                print(stdout)
                
            if process.returncode != 0:
                print("\n\nMake 错误输出:")
                print(stderr)
                logger.error("模块编译失败\n请检查上述错误信息")
                sys.exit(1)
                
            logger.info("编译Nginx ModSecurity模块成功")
        except Exception as e:
            logger.error(f"编译过程出现异常: {str(e)}")
            logger.error("请确保安装了所有必要的开发包：build-essential libpcre3-dev libxml2-dev libcurl4-openssl-dev")
            sys.exit(1)
        
        # 创建模块目录并复制模块
        modules_dir = os.path.join(NGINX_PATH, "modules")
        os.makedirs(modules_dir, exist_ok=True)
        
        # 复制模块
        module_path = os.path.join(BUILD_DIR, nginx_src_dir, "objs/ngx_http_modsecurity_module.so")
        dst_module_path = os.path.join(modules_dir, "ngx_http_modsecurity_module.so")
        shutil.copy(module_path, dst_module_path)
        
        # 测试模块兼容性
        logger.info("测试ModSecurity模块与当前Nginx的兼容性...")
        test_module_cmd = f"NGINX_CONF_FILE=/tmp/modsec_test.conf {NGINX_BIN} -t"
        
        # 创建临时配置文件用于测试
        with open("/tmp/modsec_test.conf", "w") as f:
            f.write(f"load_module {dst_module_path};\nevents {{ }}\nhttp {{ }}")
        
        try:
            subprocess.run(test_module_cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.info("模块兼容性测试成功，模块可以正常加载")
        except subprocess.CalledProcessError as e:
            err_output = e.stderr.decode() if e.stderr else ""
            is_binary_incompatible = "not binary compatible" in err_output
            
            logger.error(f"模块兼容性测试失败，该模块与当前Nginx版本不兼容")
            logger.error(f"错误详情: {err_output}")
            
            if IS_BT_ENV:
                nginx_version_exact = get_nginx_info(True)[0] or "unknown"
                logger.error(f"在宝塔环境(Nginx {nginx_version_exact})中出现了模块二进制兼容性问题")
                
                # 如果二进制不兼容，尝试特定的宝塔修复方式
                if is_binary_incompatible:
                    logger.info("正在尝试获取宝塔的精确版本信息...")  
                    
                    logger.error("有两种解决方案:")
                    logger.error(f"1. 使用宝塔官方插件安装ModSecurity (推荐)")
                    logger.error("   访问宝塔面板 > 插件 > 安全 > 搜索ModSecurity进行安装")
                    logger.error(f"2. 下列是手动配置请谨慎操作:")
                    logger.error(f"   a. 将模块文件 {dst_module_path}.incompatible 重命名为 {dst_module_path}")
                    logger.error(f"   b. 在Nginx配置文件中添加: load_module {dst_module_path};")
                    logger.error(f"   c. 在http块中添加: modsecurity on; modsecurity_rules_file /www/server/nginx/conf.d/modsecurity.conf;")
                    logger.error(f"   注意: 上述手动操作可能导致Nginx无法正常启动")
                
            else:
                logger.error("模块与Nginx版本不兼容的解决方案:")
                logger.error("1. 使用相同的Nginx版本重新编译模块")
                logger.error("2. 更新Nginx到与模块兼容的版本")
                logger.error("3. 使用官方包管理器安装ModSecurity")
                
            # 备份不兼容模块
            incompatible_backup = f"{dst_module_path}.incompatible"
            try:
                os.rename(dst_module_path, incompatible_backup)
                logger.info(f"已将不兼容的模块备份为 {incompatible_backup}")
            except Exception as rename_err:
                logger.warning(f"无法备份不兼容模块: {rename_err}")
                
            # 如果在宝塔环境中遇到二进制兼容性问题，给出更详细的指导
            if IS_BT_ENV and is_binary_incompatible:
                logger.info("\n** 宝塔兼容性问题特别说明 **")
                logger.info("该问题通常是因为宝塔面板使用了定制版的Nginx编译参数，导致模块与Nginx二进制不兼容")
                logger.info("强烈建议使用宝塔自带的插件管理功能安装ModSecurity\n")
        finally:
            # 清理临时文件
            if os.path.exists("/tmp/modsec_test.conf"):
                os.remove("/tmp/modsec_test.conf")
                
        logger.info("Nginx ModSecurity模块安装完成")
    except subprocess.CalledProcessError as e:
        logger.error(f"ModSecurity-nginx安装失败: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"获取Nginx版本或编译模块时出错: {e}")
        sys.exit(1)

# 下载OWASP ModSecurity核心规则集(CRS)
def download_owasp_crs():
    """下载OWASP ModSecurity核心规则集"""
    logger.info("下载OWASP ModSecurity核心规则集...")
    os.chdir(BUILD_DIR)
    
    # 创建CRS目录 - 根据环境选择路径
    if IS_BT_ENV:
        crs_dir = "/www/server/nginx/modsecurity-crs"
    else:
        crs_dir = "/etc/nginx/modsecurity-crs"
        
    logger.info(f"使用CRS规则目录: {crs_dir}")
    os.makedirs(crs_dir, exist_ok=True)
    
    # 优先尝试从supine-win的Gitee镜像下载
    try:
        subprocess.run("git clone https://gitee.com/supine-win/coreruleset.git", 
                     shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.info("从supine-win的Gitee镜像下载CRS成功")
        
        # 复制CRS文件
        src_dir = os.path.join(BUILD_DIR, "coreruleset")
        for item in os.listdir(src_dir):
            s = os.path.join(src_dir, item)
            d = os.path.join(crs_dir, item)
            if os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)
        logger.info(f"CRS文件已复制到{crs_dir}/")
    except subprocess.CalledProcessError:
        logger.warning("从supine-win的镜像下载失败，尝试官方Gitee镜像")
        try:
            subprocess.run("git clone https://gitee.com/mirrors/owasp-modsecurity-crs.git", 
                         shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.info("从Gitee镜像下载CRS成功")
            
            # 复制CRS文件
            src_dir = os.path.join(BUILD_DIR, "owasp-modsecurity-crs")
            for item in os.listdir(src_dir):
                s = os.path.join(src_dir, item)
                d = os.path.join(crs_dir, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)
            logger.info(f"从Gitee镜像下载的CRS文件已复制到{crs_dir}/")
        except subprocess.CalledProcessError:
            logger.warning("从Gitee镜像下载失败，尝试从GitHub下载")
            try:
                subprocess.run("git clone https://github.com/coreruleset/coreruleset.git", 
                             shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                logger.info("从GitHub下载CRS成功")
                
                # 复制CRS文件
                src_dir = os.path.join(BUILD_DIR, "coreruleset")
                for item in os.listdir(src_dir):
                    s = os.path.join(src_dir, item)
                    d = os.path.join(crs_dir, item)
                    if os.path.isdir(s):
                        shutil.copytree(s, d, dirs_exist_ok=True)
                    else:
                        shutil.copy2(s, d)
                logger.info(f"从GitHub下载的CRS文件已复制到{crs_dir}/")
            except subprocess.CalledProcessError:
                logger.error("下载CRS失败")
                sys.exit(1)
    
    # 创建并复制默认配置
    if os.path.exists(os.path.join(crs_dir, "crs-setup.conf.example")):
        shutil.copy(
            os.path.join(crs_dir, "crs-setup.conf.example"),
            os.path.join(crs_dir, "crs-setup.conf")
        )
        logger.info("CRS配置文件已创建")
    else:
        logger.warning("未找到CRS配置示例文件，将创建基本配置")
        with open(os.path.join(crs_dir, "crs-setup.conf"), 'w') as f:
            f.write("# 基本CRS配置\n")
    
    logger.info("OWASP CRS安装完成")

# 配置ModSecurity
def configure_modsecurity():
    """配置ModSecurity"""
    logger.info("配置ModSecurity...")
    
    # 创建ModSecurity配置目录
    if IS_BT_ENV:
        modsec_dir = "/www/server/nginx/modsecurity"
    else:
        modsec_dir = "/etc/nginx/modsecurity"
    
    logger.info(f"使用ModSecurity配置目录: {modsec_dir}")
    os.makedirs(modsec_dir, exist_ok=True)
    
    # 复制默认配置
    modsec_conf_src = os.path.join(BUILD_DIR, "modsecurity/modsecurity.conf-recommended")
    modsec_conf_dst = os.path.join(modsec_dir, "modsecurity.conf")
    shutil.copy(modsec_conf_src, modsec_conf_dst)
    
    # 复制unicode.mapping文件
    unicode_mapping_src = os.path.join(BUILD_DIR, "modsecurity/unicode.mapping")
    unicode_mapping_dst = os.path.join(modsec_dir, "unicode.mapping")
    if os.path.exists(unicode_mapping_src):
        logger.info(f"复制unicode.mapping文件到{modsec_dir}")
        shutil.copy(unicode_mapping_src, unicode_mapping_dst)
    else:
        logger.warning("未找到unicode.mapping文件，尝试从其他目录查找")
        # 尝试从可能的位置查找
        possible_paths = [
            # 已经在上面检查过的路径不需要再次添加: os.path.join(BUILD_DIR, "modsecurity/unicode.mapping")
            os.path.join(BUILD_DIR, "modsecurity-*/unicode.mapping"),
            "/usr/local/modsecurity/unicode.mapping",
            "/usr/share/modsecurity/unicode.mapping",
            "/usr/local/lib/modsecurity/unicode.mapping",
            "/opt/modsecurity/unicode.mapping"
        ]
        
        # 根据环境添加宝塔特定路径
        if IS_BT_ENV:
            possible_paths.append("/www/server/nginx/conf/modsecurity/unicode.mapping")
            possible_paths.append("/www/server/modsecurity/unicode.mapping")
        
        found = False
        for path_pattern in possible_paths:
            for path in glob.glob(path_pattern):
                if os.path.exists(path):
                    logger.info(f"在{path}找到unicode.mapping文件")
                    shutil.copy(path, unicode_mapping_dst)
                    found = True
                    break
            if found:
                break
                
        if not found:
            # 如果仍未找到，创建一个空文件并显示警告
            logger.error("无法找到unicode.mapping文件，请手动配置")
            with open(unicode_mapping_dst, 'w') as f:
                f.write("# This is a placeholder unicode.mapping file\n")
            logger.warning("创建了一个空的unicode.mapping文件，请手动配置")
    
    # 修改配置以启用ModSecurity并修正路径
    with open(modsec_conf_dst, 'r') as file:
        conf_content = file.read()
    
    # 启用ModSecurity
    conf_content = conf_content.replace('SecRuleEngine DetectionOnly', 'SecRuleEngine On')
    
    # 修正unicode.mapping文件路径为绝对路径
    unicode_map_file = os.path.join(modsec_dir, "unicode.mapping")
    
    # 通过正则表达式替换SecUnicodeMapFile指令的路径
    pattern = r'SecUnicodeMapFile\s+[^\n]+'
    replacement = f'SecUnicodeMapFile {unicode_map_file}'
    conf_content = re.sub(pattern, replacement, conf_content)
    
    logger.info(f"将unicode.mapping路径设置为绝对路径: {unicode_map_file}")
    
    with open(modsec_conf_dst, 'w') as file:
        file.write(conf_content)
        
    # 在宝塔环境下，同步标准路径的ModSecurity配置
    if IS_BT_ENV:
        # 确保标准路径的目录存在
        std_modsec_dir = "/etc/nginx/modsecurity"
        std_conf_d_dir = "/etc/nginx/conf.d"
        std_modules_dir = "/etc/nginx/modules-enabled"
        
        os.makedirs(std_modsec_dir, exist_ok=True)
        os.makedirs(std_conf_d_dir, exist_ok=True)
        os.makedirs(std_modules_dir, exist_ok=True)
        
        # 检测模块兼容性
        module_path = os.path.join("/www/server/nginx/modules", "ngx_http_modsecurity_module.so")
        if os.path.exists(module_path):
            logger.info("检测模块与宝塔 Nginx 的兼容性...")
            test_cmd = f"{NGINX_BIN} -t -c /tmp/bt_modsec_test.conf"
            
            # 创建测试配置
            with open("/tmp/bt_modsec_test.conf", "w") as f:
                f.write(f"load_module {module_path};\nevents {{ }}\nhttp {{ }}")
                
            try:
                subprocess.run(test_cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                logger.info("模块与宝塔 Nginx 兼容性测试通过")
            except subprocess.CalledProcessError as e:
                err_output = e.stderr.decode() if e.stderr else ""
                if "not binary compatible" in err_output:
                    logger.error(f"模块与宝塔 Nginx 二进制不兼容，请使用宝塔插件中心安装ModSecurity")
                    logger.error("或者使用宝塔的同一版本Nginx重新编译ModSecurity模块")
                else:
                    logger.error(f"模块测试遇到其他错误: {err_output}")
            finally:
                if os.path.exists("/tmp/bt_modsec_test.conf"):
                    os.remove("/tmp/bt_modsec_test.conf")
        
        # 同步unicode.mapping文件
        std_unicode_mapping = os.path.join(std_modsec_dir, "unicode.mapping")
        if os.path.exists(unicode_mapping_dst):
            logger.info(f"同步unicode.mapping文件到标准路径: {std_unicode_mapping}")
            shutil.copy(unicode_mapping_dst, std_unicode_mapping)
        
        # 同步modsecurity.conf文件
        std_modsec_conf = os.path.join(std_modsec_dir, "modsecurity.conf")
        logger.info(f"同步ModSecurity配置到标准路径: {std_modsec_conf}")
        
        # 修改标准路径的配置文件，确保使用正确的unicode.mapping路径
        with open(modsec_conf_dst, 'r') as file:
            std_conf_content = file.read()
        
        with open(std_modsec_conf, 'w') as file:
            file.write(std_conf_content)
    
    # 创建include.conf配置
    include_conf = os.path.join(modsec_dir, "include.conf")
    
    # 根据环境调整路径
    if IS_BT_ENV:
        crs_path = "/www/server/nginx/modsecurity-crs"
    else:
        crs_path = "/etc/nginx/modsecurity-crs"
    
    with open(include_conf, 'w') as file:
        file.write(f"""# ModSecurity配置
Include "{modsec_dir}/modsecurity.conf"
Include "{crs_path}/crs-setup.conf"
Include "{crs_path}/rules/*.conf"
""")
    
    # 创建Nginx ModSecurity配置 - 拆分为两个文件
    
    # 1. 创建加载模块的配置文件（必须在主配置文件的最顶层）
    if IS_BT_ENV:
        modsec_module_conf = "/www/server/nginx/modules-enabled/50-mod-http-modsecurity.conf"
    else:
        modsec_module_conf = "/etc/nginx/modules-enabled/50-mod-http-modsecurity.conf"
    
    logger.info(f"使用模块配置文件: {modsec_module_conf}")
    os.makedirs(os.path.dirname(modsec_module_conf), exist_ok=True)
    # 获取模块的绝对路径
    module_file = os.path.join(NGINX_PATH, "modules/ngx_http_modsecurity_module.so")
    
    with open(modsec_module_conf, 'w') as file:
        file.write(f"""# 加载ModSecurity模块 - 这必须放在主配置文件的顶层
load_module {module_file};
""")
    
    # 2. 创建实际启用ModSecurity的配置文件（在http块内包含）
    if IS_BT_ENV:
        modsec_nginx_conf = "/www/server/nginx/conf.d/modsecurity.conf"
        std_modsec_nginx_conf = "/etc/nginx/conf.d/modsecurity.conf"
    else:
        modsec_nginx_conf = "/etc/nginx/conf.d/modsecurity.conf"
        std_modsec_nginx_conf = modsec_nginx_conf
        
    logger.info(f"使用Nginx配置文件: {modsec_nginx_conf}")
    os.makedirs(os.path.dirname(modsec_nginx_conf), exist_ok=True)
    
    with open(modsec_nginx_conf, 'w') as file:
        file.write(f"""# 在server块内启用ModSecurity
modsecurity on;
modsecurity_rules_file {modsec_dir}/include.conf;
""")
        
    # 在宝塔环境下，同步标准路径的Nginx配置文件
    if IS_BT_ENV:
        os.makedirs(os.path.dirname(std_modsec_nginx_conf), exist_ok=True)
        logger.info(f"同步Nginx配置到标准路径: {std_modsec_nginx_conf}")
        
        with open(std_modsec_nginx_conf, 'w') as file:
            file.write(f"""# 在server块内启用ModSecurity
modsecurity on;
modsecurity_rules_file {std_modsec_dir}/include.conf;
""")
            
        # 创建标准路径的include.conf文件
        std_include_conf = os.path.join(std_modsec_dir, "include.conf")
        std_crs_path = "/etc/nginx/modsecurity-crs"
        
        with open(std_include_conf, 'w') as file:
            file.write(f"""# ModSecurity配置
Include "{std_modsec_dir}/modsecurity.conf"
Include "{crs_path}/crs-setup.conf"
Include "{crs_path}/rules/*.conf"
""")
    
    if IS_BT_ENV:
        logger.info("宝塔环境ModSecurity配置完成，请按以下步骤手动配置:")
        
        module_path = os.path.join(NGINX_PATH, 'modules/ngx_http_modsecurity_module.so')
        # 检测模块是否存在
        if os.path.exists(module_path):
            logger.info("1. 使用宝塔面板的'网站'功能窗口，选择要保护的网站，点击'设置'")
            logger.info("2. 在Nginx配置中添加以下内容（服务器配置栏目 > '配置修改'）:")
            logger.info("   # 在配置文件顶部(events块之前)添加:")
            logger.info(f"   load_module {module_path};")
            logger.info("")
            logger.info("   # 在http块内添加:")
            logger.info("   modsecurity on;")
            logger.info(f"   modsecurity_rules_file {modsec_dir}/include.conf;")
            logger.info("")
        else:
            logger.warning(f"模块文件{module_path}不存在，可能由于兼容性问题被删除")
            logger.info("***强烈建议使用宝塔插件市场安装ModSecurity***")
            logger.info("1. 访问宝塔面板 > 软件商店 > 安全")
            logger.info("2. 搜索并安装ModSecurity插件")
        
        logger.info("注意：如果在加载模块后出现\"模块不兼容\"的错误，请使用宝塔插件市场安装ModSecurity而不是手动配置")
    else:
        logger.info("ModSecurity配置完成，请将以下内容添加到您的Nginx主配置文件的顶层:")
        logger.info(f"include {modsec_module_conf};")
        logger.info("并将以下内容添加到http块:")
        logger.info(f"include {modsec_nginx_conf};")
    
    # 重启Nginx - 兼容不同系统和环境
    logger.info("测试Nginx配置并重启服务...")
    try:
        # 首先测试配置是否正确 - 使用适当的Nginx可执行文件路径
        nginx_test_cmd = f"{NGINX_BIN} -t -c {NGINX_CONF}"
        logger.info(f"执行配置测试命令: {nginx_test_cmd}")
        subprocess.run(nginx_test_cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.info("Nginx配置测试成功")
        
        # 采用不同的重启策略
        restart_success = False
        
        # 1. 先尝试systemctl命令
        try:
            logger.info("尝试使用systemctl重启Nginx...")
            subprocess.run("systemctl restart nginx", shell=True, check=True, 
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            restart_success = True
            logger.info("使用systemctl重启Nginx成功")
        except subprocess.CalledProcessError:
            logger.warning("systemctl重启失败，尝试其他方法")
        
        # 2. 如果失败，尝试service命令
        if not restart_success:
            try:
                logger.info("尝试使用service重启Nginx...")
                subprocess.run("service nginx restart", shell=True, check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                restart_success = True
                logger.info("使用service重启Nginx成功")
            except subprocess.CalledProcessError:
                logger.warning("service重启失败，尝试其他方法")
        
        # 3. 如果在宝塔环境，尝试宝塔特定命令
        if not restart_success and IS_BT_ENV:
            try:
                logger.info("在宝塔环境中尝试重启Nginx...")
                
                # 首先尝试使用宝塔的Nginx可执行文件
                bt_nginx_reload_cmd = f"{NGINX_BIN} -s reload"
                logger.info(f"尝试使用宝塔Nginx可执行文件: {bt_nginx_reload_cmd}")
                subprocess.run(bt_nginx_reload_cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                restart_success = True
                logger.info("使用宝塔Nginx可执行文件重启成功")
            except subprocess.CalledProcessError:
                logger.warning("宝塔Nginx reload命令失败，尝试启动Nginx...")
                try:
                    # 如果Nginx未运行，尝试启动，必须指定配置文件路径
                    bt_nginx_start_cmd = f"{NGINX_BIN} -c {NGINX_CONF}"
                    logger.info(f"尝试启动Nginx: {bt_nginx_start_cmd}")
                    subprocess.run(bt_nginx_start_cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    restart_success = True
                    logger.info("启动Nginx成功")
                except subprocess.CalledProcessError:
                    logger.warning("宝塔Nginx启动命令失败")
                    
                    # 尝试最后的备选方案，使用Nginx信号控制
                    try:
                        # 尝试发送USR2信号，这对宝塔Nginx也可能能工作
                        nginx_pid_file = "/www/server/nginx/logs/nginx.pid"
                        if os.path.exists(nginx_pid_file):
                            with open(nginx_pid_file, 'r') as f:
                                try:
                                    pid = int(f.read().strip())
                                    logger.info(f"尝试发送重载信号给Nginx进程(PID: {pid})")
                                    os.kill(pid, signal.SIGUSR2)
                                    restart_success = True
                                    logger.info("发送重载信号成功")
                                except (ValueError, ProcessLookupError) as e:
                                    logger.warning(f"无法发送信号到Nginx进程: {e}")
                        else:
                            logger.warning(f"Nginx PID文件不存在: {nginx_pid_file}")
                    except Exception as e:
                        logger.warning(f"尝试发送信号失败: {e}")
                    
                    logger.warning("所有重启Nginx的方法均失败，请手动重启Nginx")
            except subprocess.CalledProcessError:
                logger.warning("宝塔特定重启方式失败")
                
        # 4. 直接尝试nginx -s reload (指定配置文件路径)
        if not restart_success:
            try:
                nginx_reload_cmd = f"nginx -c {NGINX_CONF} -s reload"
                logger.info(f"尝试使用指定配置的nginx重载命令: {nginx_reload_cmd}")
                subprocess.run(nginx_reload_cmd, shell=True, check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                restart_success = True
                logger.info("使用nginx -s reload重新加载成功")
            except subprocess.CalledProcessError:
                logger.warning("nginx -s reload 失败")
        
        if restart_success:
            logger.info("Nginx已重启，ModSecurity现已启用")
        else:
            logger.error("所有重启方法均失败，请手动重启Nginx：")
            if IS_BT_ENV:
                logger.error(f"1. {NGINX_BIN} -c {NGINX_CONF} -s reload")
                logger.error(f"2. {NGINX_BIN} -c {NGINX_CONF}")
            else:
                logger.error("1. systemctl restart nginx")
                logger.error("2. service nginx restart")
                logger.error(f"3. nginx -c {NGINX_CONF} -s reload")
    except subprocess.CalledProcessError:
        logger.error("Nginx配置测试失败，请手动检查配置")
        sys.exit(1)

# 主函数
def main(force_update=False, skip_deps=False):
    """主函数
    
    Args:
        force_update (bool, optional): 强制更新ModSecurity模块，即使已存在也会重新编译。默认为False。
        skip_deps (bool, optional): 是否跳过依赖安装。当系统无法连接到网络时可以使用此选项。默认为False。
    """
    try:
        # 检查是否为root用户
        if os.geteuid() != 0:
            logger.error("此脚本需要以root权限运行")
            sys.exit(1)
        
        # 创建构建目录
        os.makedirs(BUILD_DIR, exist_ok=True)
        
        # 修复CentOS的YUM镜像源问题
        if DISTRO_FAMILY == 'rhel' and not skip_deps:
            try:
                logger.info("检测到CentOS/RHEL系统，尝试修复YUM镜像源...")
                if not fix_centos_yum_mirrors():
                    logger.warning("YUM镜像源修复失败，可能会导致依赖安装问题")
                    # 询问用户是否继续
                    logger.warning("请手动配置YUM源后重试，或使用--skip-deps参数跳过依赖安装")
                    sys.exit(1)
            except Exception as e:
                logger.error(f"修复YUM镜像源时出错: {e}")
                logger.warning("将尝试使用原始YUM源配置继续")
        
        # 安装依赖（除非被要求跳过）
        if skip_deps:
            logger.warning("根据用户请求跳过依赖安装，请确保系统已安装了所有必要的开发包")
        else:
            try:
                install_dependencies()
            except Exception as e:
                logger.error(f"依赖安装遇到问题: {e}")
                if "Could not resolve host" in str(e) or "Failed to connect" in str(e) or "Unable to establish connection" in str(e) or "Cannot find a valid baseurl" in str(e) or "Could not retrieve mirrorlist" in str(e):
                    logger.error("检测到网络连接或YUM源问题，可能是DNS解析失败、网络不可用或镜像源配置错误")
                    logger.error("如果您确定系统已经安装了所有必要的依赖，可以使用 --skip-deps 参数重新运行脚本")
                    logger.error("或者尝试手动配置YUM镜像源后再次运行脚本")
                    
                    # 提供必要的依赖列表供用户参考
                    if DISTRO_FAMILY == 'rhel':
                        logger.info("\n您需要手动安装以下依赖包:\n  - gcc\n  - gcc-c++\n  - make\n  - automake\n  - autoconf\n  - libtool\n  - pcre-devel\n  - libxml2-devel\n  - curl-devel\n  - openssl-devel\n  - zlib-devel\n  - geoip-devel\n  - yajl-devel")
                    
                    sys.exit(1)
                logger.warning("提示: 依赖安装失败，将尝试继续安装流程，但可能会在后续步骤中失败")
        
        # 下载和编译ModSecurity
        download_modsecurity(force_update)
        
        # 安装ModSecurity-nginx
        install_modsecurity_nginx(force_update)
        
        # 下载CRS规则
        download_owasp_crs()
        
        # 配置ModSecurity
        configure_modsecurity()
        
        logger.info("ModSecurity安装完成!")
        logger.info(f"详细日志请查看: {log_file}")
        
    except Exception as e:
        logger.error(f"安装过程中发生错误: {e}")
        sys.exit(1)
    finally:
        # 清理临时文件
        logger.info("清理临时文件...")
        if os.path.exists(BUILD_DIR):
            shutil.rmtree(BUILD_DIR)

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='ModSecurity安装脚本')
    parser.add_argument('-f', '--force', action='store_true', help='强制重新编译ModSecurity模块，即使已存在也会更新')
    parser.add_argument('-v', '--verbose', action='store_true', help='显示详细的安装过程信息')
    parser.add_argument('-s', '--skip-deps', action='store_true', help='跳过依赖安装，适用于无法连接到网络的环境')
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    # 如果指定了详细模式，设置日志级别为DEBUG
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        
    main(force_update=args.force, skip_deps=args.skip_deps)