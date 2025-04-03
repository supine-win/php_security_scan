#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ModSecurity安装脚本 - 优化版
支持多种Linux发行版，自动处理依赖关系、源码下载和编译安装
特别支持CentOS 7 EOL环境和宝塔面板环境
"""

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

#############################################################
# 常量定义 - 便于统一维护和修改
#############################################################

# 软件版本
MODSEC_VERSION = "3.0.14"
PCRE_VERSION = "8.45"

# 路径常量
DEFAULT_REPOS_CACHE = os.path.expanduser("~/.modsecurity_repos")
DEFAULT_BUILD_DIR = os.path.join(tempfile.gettempdir(), "modsecurity_build")
DEFAULT_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modsecurity_install.log")

# 宝塔相关路径
BT_PANEL_PATHS = ['/www/server/panel', '/www/server/nginx']
BT_NGINX_PATH = "/www/server/nginx"
BT_NGINX_BIN = "/www/server/nginx/sbin/nginx"
BT_NGINX_CONF = "/www/server/nginx/conf/nginx.conf"
BT_MODSEC_DIR = "/www/server/nginx/modsecurity"
BT_CRS_DIR = "/www/server/nginx/modsecurity-crs"
BT_MODULES_DIR = "/www/server/nginx/modules"

# 标准环境相关路径
STD_NGINX_PATH = "/etc/nginx"
STD_NGINX_BIN = "/usr/sbin/nginx"
STD_NGINX_CONF = "/etc/nginx/nginx.conf"
STD_MODSEC_DIR = "/etc/nginx/modsecurity"
STD_CRS_DIR = "/etc/nginx/modsecurity-crs"
STD_MODULES_DIR = "/etc/nginx/modules"

# 源码库URL配置
REPO_URLS = {
    "modsecurity": {
        "primary": "https://gitee.com/supine-win/ModSecurity.git",
        "secondary": "https://gitee.com/mirrors/ModSecurity.git",
        "fallback": "https://github.com/SpiderLabs/ModSecurity.git"
    },
    "modsecurity-nginx": {
        "primary": "https://gitee.com/supine-win/ModSecurity-nginx.git",
        "secondary": "https://gitee.com/mirrors/ModSecurity-nginx.git",
        "fallback": "https://github.com/SpiderLabs/ModSecurity-nginx.git"
    },
    "coreruleset": {
        "primary": "https://gitee.com/supine-win/coreruleset.git",
        "secondary": "https://gitee.com/mirrors/owasp-modsecurity-crs.git",
        "fallback": "https://github.com/coreruleset/coreruleset.git"
    }
}

# PCRE库下载URLs
PCRE_URLS = [
    "https://github.com/PCRE2Project/pcre2/releases/download/pcre2-10.42/pcre2-10.42.tar.gz",
    "https://ftp.exim.org/pub/pcre/pcre-8.45.tar.gz",
    "https://ftp.pcre.org/pub/pcre/pcre-8.45.tar.gz"
]

# 系统依赖包
RHEL_DEPENDENCIES = [
    "git", "gcc", "gcc-c++", "make", "automake", "autoconf", "libtool", 
    "pcre-devel", "libxml2-devel", "curl-devel", "openssl-devel", 
    "yajl-devel", "libmaxminddb-devel", "lua-devel",
    "zlib-devel", "gd-devel", "perl-devel", "perl-ExtUtils-Embed",
    "kernel-devel", "cmake", 
    "GeoIP", "GeoIP-devel"
]

DEBIAN_DEPENDENCIES = [
    "git", "build-essential", "automake", "autoconf", "libtool", 
    "libpcre3-dev", "libxml2-dev", "libcurl4-openssl-dev", "libssl-dev", 
    "libyajl-dev", "libmaxminddb-dev", "liblua5.3-dev",
    "zlib1g-dev", "gcc", "g++", "make", "cmake", "pkg-config",
    "libgeoip-dev", "libgeoip1"
]

DEBIAN_CRITICAL_DEPS = ["build-essential", "libpcre3-dev", "libxml2-dev", "libcurl4-openssl-dev"]

# 错误消息模板
ERROR_MESSAGES = {
    "not_root": "此脚本需要以root权限运行",
    "download_fail": "下载失败，请检查网络连接",
    "compile_fail": "编译失败，请检查系统环境和依赖",
    "nginx_binary_incompatible": "模块与当前Nginx版本不兼容"
}

#############################################################
# 日志配置
#############################################################

def setup_logging(log_file=DEFAULT_LOG_FILE, verbose=False):
    """配置日志系统
    
    Args:
        log_file (str): 日志文件路径
        verbose (bool): 是否启用详细日志
    
    Returns:
        logging.Logger: 配置好的日志器
    """
    # 创建日志器
    logger = logging.getLogger('ModSecurity')
    
    # 设置日志级别
    log_level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(log_level)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    
    # 创建文件处理器
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)  # 文件始终记录所有详细日志
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    
    # 添加处理器到日志器
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger

# 创建全局日志器
logger = setup_logging()

#############################################################
# 环境检测与信息收集
#############################################################

def is_bt_environment():
    """检测是否为宝塔环境
    
    Returns:
        bool: 是否为宝塔环境
    """
    return any(os.path.exists(path) for path in BT_PANEL_PATHS)

def get_distro_family():
    """检测当前系统类型
    
    Returns:
        str: 系统类型，'rhel'(CentOS/RHEL)、'debian'(Debian/Ubuntu)或'unknown'
    """
    if os.path.exists('/etc/redhat-release') or os.path.exists('/etc/centos-release'):
        return 'rhel'
    elif os.path.exists('/etc/debian_version'):
        return 'debian'
    else:
        return 'unknown'

def get_nginx_info(bt_env=False):
    """获取Nginx版本和编译信息
    
    Args:
        bt_env (bool): 是否为宝塔环境
        
    Returns:
        tuple: (nginx_version, configure_args, nginx_binary)
    """
    try:
        nginx_bin = BT_NGINX_BIN if bt_env else "nginx"
        if bt_env and os.path.exists(BT_NGINX_BIN):
            nginx_bin = BT_NGINX_BIN
        
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

def check_gcc_version():
    """检查GCC版本是否支持C++17
    
    Returns:
        bool: 是否支持C++17
    """
    try:
        gcc_version_output = subprocess.check_output("gcc --version", shell=True, stderr=subprocess.STDOUT, universal_newlines=True)
        version_match = re.search(r'\s(\d+\.\d+\.\d+)', gcc_version_output)
        if version_match:
            gcc_version = version_match.group(1)
            logger.info(f"检测到GCC版本: {gcc_version}")
            
            major_version = int(gcc_version.split('.')[0])
            
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

#############################################################
# 信号处理与清理
#############################################################

def cleanup_handler(signum, frame, build_dir=DEFAULT_BUILD_DIR):
    """在收到信号时清理临时文件
    
    Args:
        signum: 信号编号
        frame: 栈帧
        build_dir (str): 构建目录路径
    """
    logger.info(f"接收到信号 {signum}，正在清理临时文件...")
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
    logger.info("清理完成，退出")
    sys.exit(1)

def setup_signal_handlers(build_dir=DEFAULT_BUILD_DIR):
    """设置信号处理函数
    
    Args:
        build_dir (str): 构建目录路径
    """
    signal.signal(signal.SIGINT, lambda s, f: cleanup_handler(s, f, build_dir))  # Ctrl+C
    signal.signal(signal.SIGTERM, lambda s, f: cleanup_handler(s, f, build_dir)) # 终止信号

#############################################################
# GCC和编译工具安装
#############################################################

def install_newer_gcc(distro_family):
    """安装支持C++17的更高版本GCC
    
    Args:
        distro_family (str): 系统类型
    
    Returns:
        bool: 是否成功安装
    """
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

#############################################################
# 镜像源和仓库管理
#############################################################

def install_epel_repo():
    """安装EPEL仓库以提供额外的依赖包
    
    Returns:
        bool: 是否成功安装EPEL仓库
    """
    distro_family = get_distro_family()
    if distro_family != 'rhel':
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
#############################################################
# 仓库管理功能
#############################################################

def init_repos_cache(repos_cache=DEFAULT_REPOS_CACHE):
    """初始化代码仓库缓存目录
    
    Args:
        repos_cache (str): 仓库缓存的根目录
        
    Returns:
        bool: 是否成功初始化
    """
    if not os.path.exists(repos_cache):
        try:
            os.makedirs(repos_cache, exist_ok=True)
            for repo_name in REPO_URLS.keys():
                os.makedirs(os.path.join(repos_cache, repo_name), exist_ok=True)
            logger.info(f"创建仓库缓存目录: {repos_cache}")
            return True
        except Exception as e:
            logger.error(f"创建仓库缓存目录失败: {e}")
            return False
    return True

def clone_or_update_repo(repo_name, destination, force_update=False, repos_cache=DEFAULT_REPOS_CACHE):
    """克隆或更新代码仓库，优先使用缓存
    
    Args:
        repo_name (str): 仓库名称，必须是REPO_URLS中定义的键
        destination (str): 目标目录
        force_update (bool): 是否强制更新，即使缓存存在
        repos_cache (str): 仓库缓存根目录
        
    Returns:
        bool: 是否成功
    """
    if repo_name not in REPO_URLS:
        logger.error(f"未定义的仓库名称: {repo_name}")
        return False
        
    # 检查是否已存在目标目录
    if os.path.exists(destination) and not force_update:
        logger.info(f"目标目录 {destination} 已存在且不是强制更新模式，跳过克隆")
        return True
        
    # 确保缓存目录存在
    cache_dir = os.path.join(repos_cache, repo_name)
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir, exist_ok=True)
    
    # 检查缓存是否已存在，且非强制更新模式
    if os.path.exists(cache_dir) and os.listdir(cache_dir) and not force_update:
        logger.info(f"使用缓存的 {repo_name} 仓库...")
        try:
            # 复制缓存到目标目录
            if os.path.exists(destination):
                shutil.rmtree(destination)
            shutil.copytree(cache_dir, destination)
            logger.info(f"从缓存复制 {repo_name} 到 {destination} 成功")
            return True
        except Exception as e:
            logger.error(f"从缓存复制 {repo_name} 失败: {e}")
            # 如果复制失败，尝试直接克隆
            
    # 如果没有缓存或强制更新，尝试从远程克隆
    logger.info(f"从远程克隆 {repo_name} 仓库...")
    return download_repo_with_fallback(repo_name, destination, cache_dir, force_update)

def download_repo_with_fallback(repo_name, destination, cache_dir, force_update=False):
    """使用多级下载源尝试下载代码仓库
    
    Args:
        repo_name (str): 仓库名称，必须是REPO_URLS中定义的键
        destination (str): 目标目录
        cache_dir (str): 缓存目录
        force_update (bool): 是否强制更新
        
    Returns:
        bool: 是否成功下载
    """
    urls = REPO_URLS.get(repo_name, {})
    if not urls:
        logger.error(f"未找到 {repo_name} 的URL配置")
        return False
        
    # 定义尝试顺序
    sources = ["primary", "secondary", "fallback"]
    
    # 清理目标目录（如果存在且强制更新）
    if os.path.exists(destination) and force_update:
        shutil.rmtree(destination)
        
    # 尝试按顺序从不同源下载
    for source in sources:
        url = urls.get(source)
        if not url:
            continue
            
        try:
            logger.info(f"尝试从 {source} 源下载 {repo_name}...")
            clone_cmd = f"git clone {url} {destination}"
            subprocess.run(clone_cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.info(f"从 {source} 源下载 {repo_name} 成功")
            
            # 如果下载成功，更新缓存
            if os.path.exists(destination):
                update_repo_cache(destination, cache_dir)
                
            return True
        except subprocess.CalledProcessError:
            logger.warning(f"从 {source} 源下载 {repo_name} 失败")
            
    logger.error(f"所有源下载 {repo_name} 均失败")
    return False

def update_repo_cache(source_dir, cache_dir):
    """更新仓库缓存
    
    Args:
        source_dir (str): 源目录
        cache_dir (str): 缓存目录
        
    Returns:
        bool: 是否成功更新缓存
    """
    try:
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
        shutil.copytree(source_dir, cache_dir)
        logger.info(f"更新缓存 {cache_dir} 成功")
        return True
    except Exception as e:
        logger.error(f"更新缓存失败: {e}")
        return False

def download_file_with_fallback(urls, destination):
    """使用多个备选URL下载文件
    
    Args:
        urls (list): URL列表
        destination (str): 目标文件路径
        
    Returns:
        bool: 是否成功下载
    """
    for url in urls:
        try:
            logger.info(f"尝试从 {url} 下载文件...")
            
            # 检测系统中可用的下载工具
            if shutil.which("wget"):
                cmd = f"wget -q {url} -O {destination}"
            elif shutil.which("curl"):
                cmd = f"curl -s -L {url} -o {destination}"
            else:
                logger.error("系统中未找到wget或curl下载工具")
                return False
                
            subprocess.run(cmd, shell=True, check=True)
            
            # 验证下载是否成功（文件存在且大小合理）
            if os.path.exists(destination) and os.path.getsize(destination) > 1024:  # 至少1KB
                logger.info(f"从 {url} 下载文件成功")
                return True
            else:
                logger.warning(f"下载的文件 {destination} 大小异常")
                if os.path.exists(destination):
                    os.remove(destination)
        except subprocess.CalledProcessError:
            logger.warning(f"从 {url} 下载文件失败")
            
    logger.error("所有URL下载均失败")
    return False

#############################################################
# CentOS镜像源修复功能
#############################################################

def fix_centos_yum_mirrors():
    """修复CentOS的YUM镜像源问题
    
    禁用fastmirror插件，备份并替换为阿里云或清华源
    
    Returns:
        bool: 是否成功修复镜像源
    """
    distro_family = get_distro_family()
    if distro_family != 'rhel':
        logger.info("非CentOS/RHEL系统，跳过YUM镜像源修复")
        return True
    
    logger.info("开始修复CentOS YUM镜像源...")
    
    # 检测CentOS版本
    centos_version = get_centos_version()
    
    # 禁用fastmirror插件
    disable_fastmirror()
    
    # 备份现有YUM源配置
    backup_repo_files()
    
    # 创建新的镜像源配置
    if is_centos_eol(centos_version):
        # 针对EOL版本使用特殊配置
        if create_eol_mirror_config(centos_version):
            return True
    else:
        # 针对非EOL版本使用标准配置
        if create_standard_mirror_config(centos_version):
            return True
    
    # 如果上述方法都失败，尝试恢复原始配置
    restore_original_repo_files()
    logger.error("无法配置可用的YUM源，请手动配置软件源后重试")
    return False

def get_centos_version():
    """获取CentOS版本号
    
    Returns:
        str: CentOS版本号，如"7"或"8"，默认为"7"
    """
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
    
    return centos_version

def disable_fastmirror():
    """禁用fastmirror插件以提高稳定性
    
    Returns:
        bool: 是否成功禁用
    """
    fastmirror_conf = "/etc/yum/pluginconf.d/fastestmirror.conf"
    if not os.path.exists(fastmirror_conf):
        return True
        
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
        return True
    except Exception as e:
        logger.warning(f"禁用fastmirror插件失败: {e}")
        return False

def backup_repo_files():
    """备份所有YUM仓库配置文件
    
    Returns:
        bool: 是否成功备份
    """
    backup_dir = "/etc/yum.repos.d/original_backup"
    os.makedirs(backup_dir, exist_ok=True)
    
    # 备份所有.repo文件
    repo_files = glob.glob("/etc/yum.repos.d/*.repo")
    if not repo_files:
        logger.warning("未找到YUM仓库配置文件")
        return False
        
    for repo_file in repo_files:
        backup_file = os.path.join(backup_dir, os.path.basename(repo_file))
        if not os.path.exists(backup_file):
            logger.info(f"备份仓库文件 {repo_file} 到 {backup_file}")
            shutil.copy2(repo_file, backup_file)
        
        # 暂时禁用原始文件
        disabled_file = f"{repo_file}.disabled"
        if not os.path.exists(disabled_file):
            os.rename(repo_file, disabled_file)
    
    logger.info("已备份所有YUM仓库配置文件")
    return True

def restore_original_repo_files():
    """恢复原始YUM仓库配置文件
    
    Returns:
        bool: 是否成功恢复
    """
    for disabled_file in glob.glob("/etc/yum.repos.d/*.disabled"):
        original_file = disabled_file.replace(".disabled", "")
        try:
            logger.info(f"恢复原始配置文件: {original_file}")
            os.rename(disabled_file, original_file)
        except Exception as e:
            logger.warning(f"恢复配置文件失败: {e}")
    
    logger.info("已尝试恢复所有原始YUM仓库配置文件")
    return True

def is_centos_eol(version):
    """检查CentOS版本是否已经EOL(End Of Life)
    
    Args:
        version (str): CentOS版本号
        
    Returns:
        bool: 是否为EOL版本
    """
    return version in ["7", "8"]

def create_eol_mirror_config(centos_version):
    """为EOL版本的CentOS创建镜像源配置
    
    Args:
        centos_version (str): CentOS版本号
        
    Returns:
        bool: 是否成功创建配置
    """
    logger.info(f"检测到CentOS {centos_version} EOL版本，使用vault归档镜像")
    
    # 不同版本的CentOS使用不同的vault版本
    vault_version = "7.9.2009" if centos_version == "7" else "8.5.2111"
    
    # 尝试使用阿里云镜像
    mirror_config = generate_aliyun_eol_config(centos_version, vault_version)
    
    mirror_file = "/etc/yum.repos.d/aliyun-mirror.repo"
    try:
        with open(mirror_file, 'w') as f:
            f.write(mirror_config)
        logger.info("成功创建阿里云镜像源配置")
        
        # 测试镜像源是否可用
        if test_yum_repo():
            return True
    except Exception as e:
        logger.error(f"创建阿里云镜像源配置失败: {e}")
    
    # 如果阿里云镜像失败，尝试清华镜像
    try:
        # 删除阿里云配置
        if os.path.exists(mirror_file):
            os.remove(mirror_file)
        
        # 创建清华源配置
        tsinghua_config = generate_tsinghua_eol_config(centos_version, vault_version)
        tsinghua_file = "/etc/yum.repos.d/tsinghua-mirror.repo"
        
        with open(tsinghua_file, 'w') as f:
            f.write(tsinghua_config)
        logger.info("成功创建清华镜像源配置")
        
        # 测试镜像源是否可用
        if test_yum_repo():
            return True
    except Exception as e:
        logger.error(f"创建清华镜像源配置失败: {e}")
    
    return False

def create_standard_mirror_config(centos_version):
    """为非EOL版本的CentOS创建标准镜像源配置
    
    Args:
        centos_version (str): CentOS版本号
        
    Returns:
        bool: 是否成功创建配置
    """
    logger.info(f"为CentOS {centos_version} 创建标准镜像源配置")
    
    # 尝试使用阿里云镜像
    mirror_config = generate_aliyun_standard_config(centos_version)
    
    mirror_file = "/etc/yum.repos.d/aliyun-mirror.repo"
    try:
        with open(mirror_file, 'w') as f:
            f.write(mirror_config)
        logger.info("成功创建阿里云镜像源配置")
        
        # 测试镜像源是否可用
        if test_yum_repo():
            return True
    except Exception as e:
        logger.error(f"创建阿里云镜像源配置失败: {e}")
    
    # 如果阿里云镜像失败，尝试清华镜像
    try:
        # 删除阿里云配置
        if os.path.exists(mirror_file):
            os.remove(mirror_file)
        
        # 创建清华源配置
        tsinghua_config = generate_tsinghua_standard_config(centos_version)
        tsinghua_file = "/etc/yum.repos.d/tsinghua-mirror.repo"
        
        with open(tsinghua_file, 'w') as f:
            f.write(tsinghua_config)
        logger.info("成功创建清华镜像源配置")
        
        # 测试镜像源是否可用
        if test_yum_repo():
            return True
    except Exception as e:
        logger.error(f"创建清华镜像源配置失败: {e}")
    
    return False

def test_yum_repo():
    """测试YUM仓库是否可用
    
    Returns:
        bool: 是否可用
    """
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
        logger.error(f"镜像源测试失败: {e}")
        return False

def generate_aliyun_eol_config(version, vault_version):
    """生成阿里云EOL版本配置
    
    Args:
        version (str): CentOS版本号
        vault_version (str): vault归档版本号
        
    Returns:
        str: 配置内容
    """
    if version == "7":
        return f"""# CentOS {version} - 阿里云镜像
[base]
name=CentOS-{version} - Base
baseurl=[https://mirrors.aliyun.com/centos-vault/{vault_version}/os/$basearch/](https://mirrors.aliyun.com/centos-vault/{vault_version}/os/$basearch/)
gpgcheck=0
enabled=1

[updates]
name=CentOS-{version} - Updates
baseurl=[https://mirrors.aliyun.com/centos-vault/{vault_version}/updates/$basearch/](https://mirrors.aliyun.com/centos-vault/{vault_version}/updates/$basearch/)
gpgcheck=0
enabled=1

[extras]
name=CentOS-{version} - Extras
baseurl=[https://mirrors.aliyun.com/centos-vault/{vault_version}/extras/$basearch/](https://mirrors.aliyun.com/centos-vault/{vault_version}/extras/$basearch/)
gpgcheck=0
enabled=1

# EPEL仓库
[epel]
name=Extra Packages for Enterprise Linux {version}
baseurl=[https://mirrors.aliyun.com/epel/{version}/$basearch](https://mirrors.aliyun.com/epel/{version}/$basearch)
enabled=1
gpgcheck=0
"""
    else:  # version == "8"
        return f"""# CentOS {version} - 阿里云镜像
[base]
name=CentOS-{version} - Base
baseurl=[https://mirrors.aliyun.com/centos-vault/{vault_version}/BaseOS/$basearch/os/](https://mirrors.aliyun.com/centos-vault/{vault_version}/BaseOS/$basearch/os/)
gpgcheck=0
enabled=1

[appstream]
name=CentOS-{version} - AppStream
baseurl=[https://mirrors.aliyun.com/centos-vault/{vault_version}/AppStream/$basearch/os/](https://mirrors.aliyun.com/centos-vault/{vault_version}/AppStream/$basearch/os/)
gpgcheck=0
enabled=1

[extras]
name=CentOS-{version} - Extras
baseurl=[https://mirrors.aliyun.com/centos-vault/{vault_version}/extras/$basearch/os/](https://mirrors.aliyun.com/centos-vault/{vault_version}/extras/$basearch/os/)
gpgcheck=0
enabled=1

# EPEL仓库
[epel]
name=Extra Packages for Enterprise Linux {version}
baseurl=[https://mirrors.aliyun.com/epel/{version}/Everything/$basearch](https://mirrors.aliyun.com/epel/{version}/Everything/$basearch)
enabled=1
gpgcheck=0
"""

def generate_tsinghua_eol_config(version, vault_version):
    """生成清华EOL版本配置
    
    Args:
        version (str): CentOS版本号
        vault_version (str): vault归档版本号
        
    Returns:
        str: 配置内容
    """
    if version == "7":
        return f"""# CentOS {version} - 清华镜像
[base]
name=CentOS-{version} - Base
baseurl=[https://mirrors.tuna.tsinghua.edu.cn/centos-vault/{vault_version}/os/$basearch/](https://mirrors.tuna.tsinghua.edu.cn/centos-vault/{vault_version}/os/$basearch/)
gpgcheck=0
enabled=1

[updates]
name=CentOS-{version} - Updates
baseurl=[https://mirrors.tuna.tsinghua.edu.cn/centos-vault/{vault_version}/updates/$basearch/](https://mirrors.tuna.tsinghua.edu.cn/centos-vault/{vault_version}/updates/$basearch/)
gpgcheck=0
enabled=1

[extras]
name=CentOS-{version} - Extras
baseurl=[https://mirrors.tuna.tsinghua.edu.cn/centos-vault/{vault_version}/extras/$basearch/](https://mirrors.tuna.tsinghua.edu.cn/centos-vault/{vault_version}/extras/$basearch/)
gpgcheck=0
enabled=1

# EPEL仓库
[epel]
name=Extra Packages for Enterprise Linux {version}
baseurl=[https://mirrors.tuna.tsinghua.edu.cn/epel/{version}/$basearch](https://mirrors.tuna.tsinghua.edu.cn/epel/{version}/$basearch)
enabled=1
gpgcheck=0
"""
    else:  # version == "8"
        return f"""# CentOS {version} - 清华镜像
[base]
name=CentOS-{version} - Base
baseurl=[https://mirrors.tuna.tsinghua.edu.cn/centos-vault/{vault_version}/BaseOS/$basearch/os/](https://mirrors.tuna.tsinghua.edu.cn/centos-vault/{vault_version}/BaseOS/$basearch/os/)
gpgcheck=0
enabled=1

[appstream]
name=CentOS-{version} - AppStream
baseurl=[https://mirrors.tuna.tsinghua.edu.cn/centos-vault/{vault_version}/AppStream/$basearch/os/](https://mirrors.tuna.tsinghua.edu.cn/centos-vault/{vault_version}/AppStream/$basearch/os/)
gpgcheck=0
enabled=1

[extras]
name=CentOS-{version} - Extras
baseurl=[https://mirrors.tuna.tsinghua.edu.cn/centos-vault/{vault_version}/extras/$basearch/os/](https://mirrors.tuna.tsinghua.edu.cn/centos-vault/{vault_version}/extras/$basearch/os/)
gpgcheck=0
enabled=1

# EPEL仓库
[epel]
name=Extra Packages for Enterprise Linux {version}
baseurl=[https://mirrors.tuna.tsinghua.edu.cn/epel/{version}/Everything/$basearch](https://mirrors.tuna.tsinghua.edu.cn/epel/{version}/Everything/$basearch)
enabled=1
gpgcheck=0
"""

def generate_aliyun_standard_config(version):
    """生成阿里云标准版本配置
    
    Args:
        version (str): CentOS版本号
        
    Returns:
        str: 配置内容
    """
    return f"""# CentOS {version} - 阿里云镜像
[base]
name=CentOS-{version} - Base
baseurl=[https://mirrors.aliyun.com/centos/{version}/BaseOS/$basearch/os/](https://mirrors.aliyun.com/centos/{version}/BaseOS/$basearch/os/)
gpgcheck=0
enabled=1

[appstream]
name=CentOS-{version} - AppStream
baseurl=[https://mirrors.aliyun.com/centos/{version}/AppStream/$basearch/os/](https://mirrors.aliyun.com/centos/{version}/AppStream/$basearch/os/)
gpgcheck=0
enabled=1

[extras]
name=CentOS-{version} - Extras
baseurl=[https://mirrors.aliyun.com/centos/{version}/extras/$basearch/os/](https://mirrors.aliyun.com/centos/{version}/extras/$basearch/os/)
gpgcheck=0
enabled=1

# EPEL仓库
[epel]
name=Extra Packages for Enterprise Linux {version}
baseurl=[https://mirrors.aliyun.com/epel/{version}/Everything/$basearch](https://mirrors.aliyun.com/epel/{version}/Everything/$basearch)
enabled=1
gpgcheck=0
"""

def generate_tsinghua_standard_config(version):
    """生成清华标准版本配置
    
    Args:
        version (str): CentOS版本号
        
    Returns:
        str: 配置内容
    """
    return f"""# CentOS {version} - 清华镜像
[base]
name=CentOS-{version} - Base
baseurl=[https://mirrors.tuna.tsinghua.edu.cn/centos/{version}/BaseOS/$basearch/os/](https://mirrors.tuna.tsinghua.edu.cn/centos/{version}/BaseOS/$basearch/os/)
gpgcheck=0
enabled=1

[appstream]
name=CentOS-{version} - AppStream
baseurl=[https://mirrors.tuna.tsinghua.edu.cn/centos/{version}/AppStream/$basearch/os/](https://mirrors.tuna.tsinghua.edu.cn/centos/{version}/AppStream/$basearch/os/)
gpgcheck=0
enabled=1

[extras]
name=CentOS-{version} - Extras
baseurl=[https://mirrors.tuna.tsinghua.edu.cn/centos/{version}/extras/$basearch/os/](https://mirrors.tuna.tsinghua.edu.cn/centos/{version}/extras/$basearch/os/)
gpgcheck=0
enabled=1

# EPEL仓库
[epel]
name=Extra Packages for Enterprise Linux {version}
baseurl=[https://mirrors.tuna.tsinghua.edu.cn/epel/{version}/Everything/$basearch](https://mirrors.tuna.tsinghua.edu.cn/epel/{version}/Everything/$basearch)
enabled=1
gpgcheck=0
"""
#############################################################
# 依赖安装功能
#############################################################

def install_dependencies(skip_deps=False, bt_env=False):
    """安装ModSecurity所需的系统依赖
    
    Args:
        skip_deps (bool): 是否跳过依赖安装
        bt_env (bool): 是否为宝塔环境
        
    Returns:
        bool: 是否成功安装依赖
    """
    if skip_deps:
        logger.warning("根据参数跳过依赖安装")
        return True
        
    logger.info("安装系统依赖...")
    
    distro_family = get_distro_family()
    
    # 检测是否已安装Nginx
    nginx_installed, nginx_version = check_nginx_installed(bt_env)
    
    # 准备依赖包列表
    dependencies = prepare_dependency_list(distro_family, nginx_installed, bt_env)
    
    # 安装依赖
    if distro_family == 'rhel':
        return install_rhel_dependencies(dependencies)
    elif distro_family == 'debian':
        return install_debian_dependencies(dependencies)
    else:
        logger.error("不支持的系统类型")
        return False

def check_nginx_installed(bt_env=False):
    """检查系统中是否已安装Nginx
    
    Args:
        bt_env (bool): 是否为宝塔环境
        
    Returns:
        tuple: (是否已安装, Nginx版本)
    """
    try:
        nginx_version, _, _ = get_nginx_info(bt_env)
        if nginx_version:
            logger.info(f"检测到系统中已安装Nginx v{nginx_version}")
            return True, nginx_version
    except Exception:
        logger.info("未检测到Nginx")
    
    return False, None

def prepare_dependency_list(distro_family, nginx_installed, bt_env=False):
    """准备依赖包列表
    
    Args:
        distro_family (str): 系统类型
        nginx_installed (bool): 是否已安装Nginx
        bt_env (bool): 是否为宝塔环境
        
    Returns:
        list: 依赖包列表
    """
    if distro_family == 'rhel':
        dependencies = RHEL_DEPENDENCIES.copy()
    else:  # debian
        dependencies = DEBIAN_DEPENDENCIES.copy()
    
    # 如果未安装nginx且不是宝塔环境，添加nginx依赖
    if not nginx_installed and not bt_env:
        dependencies.append("nginx")
        logger.info("将安装Nginx服务器")
    else:
        logger.info("跳过Nginx安装，使用现有Nginx")
    
    return dependencies

def install_rhel_dependencies(dependencies):
    """在RHEL/CentOS系统上安装依赖
    
    Args:
        dependencies (list): 依赖包列表
        
    Returns:
        bool: 是否成功安装依赖
    """
    # 首先尝试安装EPEL仓库
    epel_installed = install_epel_repo()
    if epel_installed:
        logger.info("成功添加EPEL仓库，这将提供更多依赖包")
        subprocess.run("yum clean all && yum makecache", shell=True, check=False)
    else:
        logger.warning("无法安装EPEL仓库，某些依赖包可能不可用")
    
    # 构建安装命令
    cmd = f"yum install -y {' '.join(dependencies)}"
    
    # 执行安装命令
    return execute_dependency_installation(cmd, 'rhel', dependencies)

def install_debian_dependencies(dependencies):
    """在Debian/Ubuntu系统上安装依赖
    
    Args:
        dependencies (list): 依赖包列表
        
    Returns:
        bool: 是否成功安装依赖
    """
    # 构建安装命令
    cmd = f"apt update && apt install -y {' '.join(dependencies)}"
    
    # 执行安装命令
    return execute_dependency_installation(cmd, 'debian', dependencies)

def execute_dependency_installation(cmd, distro_family, dependencies):
    """执行依赖安装命令
    
    Args:
        cmd (str): 安装命令
        distro_family (str): 系统类型
        dependencies (list): 依赖包列表
        
    Returns:
        bool: 是否成功安装依赖
    """
    try:
        logger.info(f"执行依赖安装命令: {cmd}")
        process = subprocess.run(cmd, shell=True, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        
        # 检查是否出现镜像源错误
        if process.returncode != 0:
            error_output = process.stderr
            logger.warning(f"依赖安装失败，错误信息: {error_output}")
            
            # 检查CentOS的特殊错误
            if distro_family == 'rhel' and ('Could not retrieve mirrorlist' in error_output or 'Cannot find a valid baseurl' in error_output):
                logger.warning("检测到YUM镜像源错误，尝试修复...")
                
                # 尝试修复镜像源
                if fix_centos_yum_mirrors():
                    # 如果修复成功，重新尝试安装
                    logger.info("镜像源修复成功，重新尝试安装依赖")
                    process = subprocess.run(cmd, shell=True, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                else:
                    # 如果镜像源修复失败，尝试直接安装RPM包
                    logger.warning("镜像源修复失败，尝试使用直接RPM包安装方法")
                    return install_direct_rpm_dependencies(dependencies)
            
            # 如果还是失败，返回失败状态
            if process.returncode != 0:
                logger.error("依赖安装失败，尝试使用直接RPM包安装或跳过依赖安装")
                return False
        
        logger.info("依赖安装成功")
        return True
    except Exception as e:
        logger.error(f"依赖安装过程中发生异常: {e}")
        return False

def install_direct_rpm_dependencies(dependencies=None):
    """使用直接RPM包安装方式，完全绕过YUM的依赖安装方案
    
    专为CentOS 7 EOL环境设计，直接从镜像站点下载RPM包并安装
    
    Args:
        dependencies (list): 可选的依赖包列表，如果为None则使用预定义列表
        
    Returns:
        bool: 是否成功安装依赖
    """
    logger.info("使用直接RPM包安装方法，绕过YUM")
    
    # 确定CentOS版本
    centos_version = get_centos_version()
    
    # 针对CentOS 7预定义的RPM包列表
    rpm_packages = {
        # 基本开发工具
        'development-tools': [
            "https://mirrors.aliyun.com/centos-vault/7.9.2009/os/x86_64/Packages/gcc-4.8.5-44.el7.x86_64.rpm",
            "https://mirrors.aliyun.com/centos-vault/7.9.2009/os/x86_64/Packages/gcc-c++-4.8.5-44.el7.x86_64.rpm",
            "https://mirrors.aliyun.com/centos-vault/7.9.2009/os/x86_64/Packages/make-3.82-24.el7.x86_64.rpm"
        ],
        # 核心依赖
        'core-deps': [
            "https://mirrors.aliyun.com/centos-vault/7.9.2009/os/x86_64/Packages/pcre-devel-8.32-17.el7.x86_64.rpm",
            "https://mirrors.aliyun.com/centos-vault/7.9.2009/os/x86_64/Packages/openssl-devel-1.0.2k-25.el7_9.x86_64.rpm",
            "https://mirrors.aliyun.com/centos-vault/7.9.2009/os/x86_64/Packages/zlib-devel-1.2.7-19.el7_9.x86_64.rpm"
        ],
        # ModSecurity依赖
        'modsecurity-deps': [
            "https://mirrors.aliyun.com/centos-vault/7.9.2009/os/x86_64/Packages/geoip-devel-1.5.0-14.el7.x86_64.rpm",
            "https://mirrors.aliyun.com/centos-vault/7.9.2009/os/x86_64/Packages/libxml2-devel-2.9.1-6.el7_9.6.x86_64.rpm",
            "https://mirrors.aliyun.com/centos-vault/7.9.2009/os/x86_64/Packages/libcurl-devel-7.29.0-59.el7_9.1.x86_64.rpm",
            "https://mirrors.aliyun.com/centos-vault/7.9.2009/os/x86_64/Packages/yajl-devel-2.0.4-4.el7.x86_64.rpm"
        ],
        # EPEL依赖
        'epel-deps': [
            "https://mirrors.aliyun.com/epel/7/x86_64/Packages/c/cjson-devel-1.7.12-1.el7.x86_64.rpm"
        ]
    }
    
    # 创建临时目录用于下载RPM包
    temp_dir = "/tmp/modsecurity_rpms"
    os.makedirs(temp_dir, exist_ok=True)
    
    # 统计成功安装的包数量
    install_success_count = 0
    total_packages = sum(len(pkgs) for pkgs in rpm_packages.values())
    
    # 逐个类别安装
    for category, packages in rpm_packages.items():
        logger.info(f"安装 {category} 类别的RPM包...")
        
        # 逐个包下载和安装
        for pkg_url in packages:
            try:
                # 提取包名
                pkg_name = os.path.basename(pkg_url)
                pkg_path = os.path.join(temp_dir, pkg_name)
                
                # 下载包
                logger.info(f"下载 {pkg_name}...")
                download_success = download_rpm_package(pkg_url, pkg_path)
                
                if not download_success:
                    logger.warning(f"下载 {pkg_name} 失败，尝试下一个包")
                    continue
                
                # 验证RPM包
                if not validate_rpm_package(pkg_path):
                    logger.warning(f"验证 {pkg_name} 失败，尝试下一个包")
                    continue
                
                # 安装包
                logger.info(f"安装 {pkg_name}...")
                install_cmd = f"rpm -Uvh --force --nodeps {pkg_path}"
                process = subprocess.run(install_cmd, shell=True, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                
                if process.returncode == 0:
                    logger.info(f"成功安装 {pkg_name}")
                    install_success_count += 1
                else:
                    logger.warning(f"安装 {pkg_name} 失败: {process.stderr}")
            except Exception as e:
                logger.error(f"处理包时出错: {e}")
    
    # 清理临时目录
    try:
        shutil.rmtree(temp_dir)
    except Exception as e:
        logger.warning(f"清理临时目录失败: {e}")
    
    # 如果至少安装了一半的包，就认为基本成功
    if install_success_count >= total_packages / 2:
        logger.info(f"直接RPM安装部分成功: {install_success_count}/{total_packages} 包已安装")
        return True
    else:
        logger.error(f"直接RPM安装失败: 只有 {install_success_count}/{total_packages} 包安装成功")
        return False

def download_rpm_package(url, destination):
    """从多个镜像源下载RPM包
    
    Args:
        url (str): 包的URL
        destination (str): 目标文件路径
        
    Returns:
        bool: 是否成功下载
    """
    # 生成备选URL
    alternate_urls = [url]
    
    # 如果是阿里云URL，添加清华源作为备选
    if "mirrors.aliyun.com" in url:
        tsinghua_url = url.replace("mirrors.aliyun.com", "mirrors.tuna.tsinghua.edu.cn")
        alternate_urls.append(tsinghua_url)
    
    # 尝试从不同URL下载
    for alt_url in alternate_urls:
        try:
            logger.debug(f"尝试从 {alt_url} 下载...")
            
            # 检测系统中可用的下载工具
            if shutil.which("wget"):
                cmd = f"wget -q {alt_url} -O {destination}"
            elif shutil.which("curl"):
                cmd = f"curl -s -L {alt_url} -o {destination}"
            else:
                logger.error("系统中未找到wget或curl下载工具")
                return False
                
            subprocess.run(cmd, shell=True, check=True)
            
            # 验证下载是否成功（文件存在且大小合理）
            if os.path.exists(destination) and os.path.getsize(destination) > 10240:  # 至少10KB
                logger.debug(f"从 {alt_url} 下载文件成功")
                return True
            else:
                logger.warning(f"下载的文件 {destination} 大小异常")
                if os.path.exists(destination):
                    os.remove(destination)
        except subprocess.CalledProcessError:
            logger.warning(f"从 {alt_url} 下载文件失败")
            if os.path.exists(destination):
                os.remove(destination)
            
    logger.error(f"所有URL下载均失败: {url}")
    return False

def validate_rpm_package(package_path):
    """验证下载的RPM包是否有效
    
    Args:
        package_path (str): RPM包的路径
        
    Returns:
        bool: 是否为有效的RPM包
    """
    try:
        # 检查文件类型是否为RPM
        file_cmd = f"file {package_path}"
        process = subprocess.run(file_cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        
        if "RPM" in process.stdout:
            return True
        else:
            logger.warning(f"{package_path} 不是有效的RPM包")
            return False
    except Exception as e:
        logger.error(f"验证RPM包失败: {e}")
        return False

#############################################################
# ModSecurity下载和安装功能
#############################################################

def download_modsecurity(force_update=False):
    """下载ModSecurity源代码并准备编译环境
    
    Args:
        force_update (bool): 是否强制更新已存在的代码
        
    Returns:
        tuple: (bool, str) 是否成功及源代码目录路径
    """
    logger.info("开始下载ModSecurity...")
    
    # 创建构建目录
    build_dir = DEFAULT_BUILD_DIR
    if not os.path.exists(build_dir):
        os.makedirs(build_dir, exist_ok=True)
    
    # ModSecurity主库路径
    modsec_dir = os.path.join(build_dir, "ModSecurity")
    
    # 下载ModSecurity代码
    if not clone_or_update_repo("modsecurity", modsec_dir, force_update):
        logger.error("下载ModSecurity失败")
        return False, ""
    
    # 编译ModSecurity
    if not compile_modsecurity(modsec_dir):
        logger.error("编译ModSecurity失败")
        return False, ""
    
    # 下载ModSecurity-Nginx连接器
    connector_dir = os.path.join(build_dir, "ModSecurity-nginx")
    if not clone_or_update_repo("modsecurity-nginx", connector_dir, force_update):
        logger.error("下载ModSecurity-Nginx连接器失败")
        return False, ""
    
    # 下载 OWASP CRS 规则集
    crs_dir = os.path.join(build_dir, "owasp-modsecurity-crs")
    if not clone_or_update_repo("owasp-crs", crs_dir, force_update):
        logger.warning("下载 OWASP CRS 规则集失败，但将继续安装ModSecurity")
    
    return True, modsec_dir

def compile_modsecurity(modsec_dir):
    """编译ModSecurity库
    
    Args:
        modsec_dir (str): ModSecurity源代码目录
        
    Returns:
        bool: 编译是否成功
    """
    logger.info("开始编译ModSecurity...")
    
    try:
        # 进入源代码目录
        os.chdir(modsec_dir)
        
        # 执行编译前准备
        logger.info("生成编译配置...")
        commands = [
            "./build.sh",
            "./configure --disable-doxygen-doc"
        ]
        
        for cmd in commands:
            logger.info(f"执行: {cmd}")
            process = subprocess.run(cmd, shell=True, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            
            if process.returncode != 0:
                logger.error(f"命令 {cmd} 执行失败: {process.stderr}")
                return False
        
        # 编译和安装
        logger.info("编译和安装ModSecurity...")
        compile_cmds = [
            "make",
            "make install"
        ]
        
        for cmd in compile_cmds:
            logger.info(f"执行: {cmd}")
            process = subprocess.run(cmd, shell=True, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            
            if process.returncode != 0:
                logger.error(f"命令 {cmd} 执行失败: {process.stderr}")
                return False
        
        logger.info("ModSecurity编译安装成功")
        return True
    except Exception as e:
        logger.error(f"ModSecurity编译过程发生异常: {e}")
        return False

def download_nginx_source(version):
    """下载特定版本的Nginx源代码
    
    Args:
        version (str): Nginx版本号
        
    Returns:
        str: Nginx源代码目录路径，失败返回空字符串
    """
    logger.info(f"下载Nginx v{version} 源代码...")
    
    # 创建下载目录
    build_dir = DEFAULT_BUILD_DIR
    nginx_src_dir = os.path.join(build_dir, f"nginx-{version}")
    
    # 如果目录已存在，跳过下载
    if os.path.exists(nginx_src_dir):
        logger.info(f"Nginx源代码已存在于 {nginx_src_dir}，跳过下载")
        return nginx_src_dir
    
    # 下载源代码包
    nginx_tar = os.path.join(build_dir, f"nginx-{version}.tar.gz")
    download_url = f"https://nginx.org/download/nginx-{version}.tar.gz"
    
    try:
        # 下载命令
        if shutil.which("wget"):
            cmd = f"wget -q {download_url} -O {nginx_tar}"
        elif shutil.which("curl"):
            cmd = f"curl -s -L {download_url} -o {nginx_tar}"
        else:
            logger.error("系统中未找到wget或curl下载工具")
            return ""
        
        subprocess.run(cmd, shell=True, check=True)
        
        # 解压源代码
        extract_cmd = f"tar -xzf {nginx_tar} -C {build_dir}"
        subprocess.run(extract_cmd, shell=True, check=True)
        
        # 验证解压结果
        if not os.path.exists(nginx_src_dir):
            logger.error(f"Nginx源代码解压后不存在: {nginx_src_dir}")
            return ""
        
        logger.info(f"Nginx源代码下载并解压到 {nginx_src_dir}")
        return nginx_src_dir
    except Exception as e:
        logger.error(f"下载Nginx源代码时出错: {e}")
        return ""

def compile_dynamic_module(nginx_src_dir, connector_dir, configure_args):
    """编译ModSecurity动态模块
    
    Args:
        nginx_src_dir (str): Nginx源代码目录
        connector_dir (str): ModSecurity-Nginx连接器目录
        configure_args (str): Nginx的原始配置参数
        
    Returns:
        bool: 编译是否成功
    """
    logger.info("开始编译ModSecurity-Nginx动态模块...")
    
    try:
        # 进入Nginx源代码目录
        os.chdir(nginx_src_dir)
        
        # 解析原始的configure参数，去除--prefix和--add-dynamic-module
        args = configure_args.split()
        filtered_args = []
        skip_next = False
        
        for arg in args:
            if skip_next:
                skip_next = False
                continue
                
            if arg.startswith('--prefix=') or arg.startswith('--add-dynamic-module'):
                continue
            elif arg == '--prefix' or arg == '--add-dynamic-module':
                skip_next = True
                continue
            
            filtered_args.append(arg)
        
        # 添加ModSecurity模块
        filtered_args.append(f"--add-dynamic-module={connector_dir}")
        
        # 构建新的configure命令
        new_configure_cmd = "./configure " + " ".join(filtered_args)
        
        # 执行配置和编译
        logger.info(f"配置Nginx动态模块: {new_configure_cmd}")
        process = subprocess.run(new_configure_cmd, shell=True, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        
        if process.returncode != 0:
            logger.error(f"配置Nginx模块失败: {process.stderr}")
            return False
        
        # 构建模块（只编译模块而不是整个Nginx）
        logger.info("编译ModSecurity动态模块...")
        make_cmd = "make modules"
        process = subprocess.run(make_cmd, shell=True, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        
        if process.returncode != 0:
            logger.error(f"编译模块失败: {process.stderr}")
            return False
        
        # 检查模块是否成功创建
        module_path = os.path.join(nginx_src_dir, "objs/ngx_http_modsecurity_module.so")
        if not os.path.exists(module_path):
            logger.error(f"编译后的模块文件不存在: {module_path}")
            return False
            
        logger.info(f"ModSecurity动态模块成功编译: {module_path}")
        return True
    except Exception as e:
        logger.error(f"编译ModSecurity-Nginx模块时出错: {e}")
        return False

def install_modsecurity_nginx(modsec_dir, force_update=False, bt_env=False):
    """安装ModSecurity-Nginx模块
    
    Args:
        modsec_dir (str): ModSecurity源代码目录
        force_update (bool): 是否强制更新
        bt_env (bool): 是否为宝塔环境
        
    Returns:
        bool: 安装是否成功
    """
    logger.info("开始编译安装ModSecurity-Nginx模块...")
    
    # 获取Nginx信息
    nginx_version, configure_args, nginx_binary = get_nginx_info(bt_env)
    if not nginx_version:
        logger.error("无法获取Nginx版本和编译参数，请确保Nginx已安装")
        return False
    
    logger.info(f"Nginx版本: {nginx_version}, 二进制路径: {nginx_binary}")
    
    # 确定模块目录和模块文件路径
    modules_dir = BT_MODULES_DIR if bt_env else STD_MODULES_DIR
    module_path = os.path.join(modules_dir, "ngx_http_modsecurity_module.so")
    os.makedirs(modules_dir, exist_ok=True)
    
    # 如果模块已存在且非强制更新，跳过
    if os.path.exists(module_path) and not force_update:
        logger.info(f"ModSecurity模块已存在于 {module_path}，跳过编译")
        return True
    elif os.path.exists(module_path) and force_update:
        logger.info(f"强制更新模式，删除现有模块: {module_path}")
        os.remove(module_path)
    
    # 获取Nginx源码
    nginx_src_dir = download_nginx_source(nginx_version)
    if not nginx_src_dir:
        logger.error("下载Nginx源码失败")
        return False
    
    # 获取ModSecurity-Nginx连接器路径
    connector_dir = os.path.join(DEFAULT_BUILD_DIR, "ModSecurity-nginx")
    if not os.path.exists(connector_dir):
        logger.error(f"ModSecurity-Nginx连接器目录不存在: {connector_dir}")
        return False
    
    # 创建动态模块
    if not compile_dynamic_module(nginx_src_dir, connector_dir, configure_args):
        logger.error("编译ModSecurity-Nginx动态模块失败")
        return False
    
    # 复制模块到最终位置
    objs_module_path = os.path.join(nginx_src_dir, "objs/ngx_http_modsecurity_module.so")
    if not os.path.exists(objs_module_path):
        logger.error(f"编译后的模块文件不存在: {objs_module_path}")
        return False
    
    shutil.copy2(objs_module_path, module_path)
    logger.info(f"ModSecurity模块成功安装到: {module_path}")
    
    # 创建 ModSecurity 配置目录
    modsec_conf_dir = BT_MODSEC_DIR if bt_env else STD_MODSEC_DIR
    if not os.path.exists(modsec_conf_dir):
        os.makedirs(modsec_conf_dir, exist_ok=True)
    
    # 配置ModSecurity
    modsec_recommended_file = os.path.join(modsec_dir, "modsecurity.conf-recommended")
    if os.path.exists(modsec_recommended_file):
        shutil.copy2(modsec_recommended_file, os.path.join(modsec_conf_dir, "modsecurity.conf"))
    
    unicode_map_file = os.path.join(modsec_dir, "unicode.mapping")
    if os.path.exists(unicode_map_file):
        shutil.copy2(unicode_map_file, os.path.join(modsec_conf_dir, "unicode.mapping"))
    
    # 创建基础配置文件
    create_modsecurity_main_config(modsec_conf_dir)
    
    # 安装OWASP CRS规则集
    crs_dir = BT_CRS_DIR if bt_env else STD_CRS_DIR
    install_owasp_crs(crs_dir)
    
    # 修改Nginx配置加载ModSecurity模块
    update_nginx_config_for_modsecurity(bt_env, module_path, modsec_conf_dir)
    
    # 测试Nginx配置
    if not test_nginx_config(bt_env):
        logger.error("修改后的Nginx配置无效，回滚中...")
        # 此处可以添加回滚逻辑
        return False
    
    # 重启Nginx
    if not restart_nginx(bt_env):
        logger.error("Nginx重启失败，请手动检查配置并重启")
        return False
    
    logger.info("ModSecurity-Nginx模块安装成功")
    return True

def create_modsecurity_main_config(modsec_conf_dir):
    """创建ModSecurity的主配置文件
    
    Args:
        modsec_conf_dir (str): ModSecurity配置目录
    """
    logger.info("创建ModSecurity主配置文件...")
    main_conf_file = os.path.join(modsec_conf_dir, "main.conf")
    
    with open(main_conf_file, 'w') as f:
        f.write("# ModSecurity main configuration\n")
        f.write("Include \"modsecurity.conf\"\n")
        f.write("# -- Rule engine initialization ----------------------------------------------\n\n")
        f.write("# Enable ModSecurity, attaching it to every transaction. Use detection\n")
        f.write("# only to start with, because that minimises the chances of post-installation\n")
        f.write("# disruption.\n")
        f.write("SecRuleEngine On\n\n")
        f.write("# -- Request body handling ---------------------------------------------------\n\n")
        f.write("# Allow ModSecurity to access request bodies. If you don't, ModSecurity\n")
        f.write("# won't be able to see any POST parameters, which opens a large security\n")
        f.write("# hole for attackers to exploit.\n")
        f.write("SecRequestBodyAccess On\n\n")
        f.write("# Maximum request body size we will accept for buffering\n")
        f.write("SecRequestBodyLimit 13107200\n")
        f.write("# Maximum request body size we will accept for buffering\n")
        f.write("SecRequestBodyNoFilesLimit 131072\n\n")
        f.write("# Include OWASP CRS rules if available\n")
        f.write("Include /etc/nginx/modsecurity/owasp-crs/crs-setup.conf\n")
        f.write("Include /etc/nginx/modsecurity/owasp-crs/rules/*.conf\n")
    
    logger.info(f"创建了ModSecurity主配置文件: {main_conf_file}")

def install_owasp_crs(crs_dir):
    """安装OWASP ModSecurity核心规则集(CRS)
    
    Args:
        crs_dir (str): CRS规则集目录
        
    Returns:
        bool: 安装是否成功
    """
    logger.info("安装OWASP ModSecurity核心规则集...")
    
    # 创建目录
    if not os.path.exists(crs_dir):
        os.makedirs(crs_dir, exist_ok=True)
    
    # 检查规则集源代码是否已下载
    source_crs_dir = os.path.join(DEFAULT_BUILD_DIR, "owasp-modsecurity-crs")
    if not os.path.exists(source_crs_dir):
        logger.warning(f"OWASP CRS源代码目录不存在: {source_crs_dir}")
        return False
    
    try:
        # 复制所有CRS文件
        # 1. 复制配置文件
        crs_setup_example = os.path.join(source_crs_dir, "crs-setup.conf.example")
        if os.path.exists(crs_setup_example):
            shutil.copy2(crs_setup_example, os.path.join(crs_dir, "crs-setup.conf"))
        
        # 2. 复制规则目录
        rules_dir = os.path.join(source_crs_dir, "rules")
        target_rules_dir = os.path.join(crs_dir, "rules")
        
        if os.path.exists(target_rules_dir):
            shutil.rmtree(target_rules_dir)
        
        if os.path.exists(rules_dir):
            shutil.copytree(rules_dir, target_rules_dir)
        
        logger.info(f"OWASP CRS规则集已安装到 {crs_dir}")
        return True
    except Exception as e:
        logger.error(f"安装OWASP CRS规则集时出错: {e}")
        return False

def update_nginx_config_for_modsecurity(bt_env, module_path, modsec_conf_dir):
    """更新Nginx配置以加载ModSecurity模块
    
    Args:
        bt_env (bool): 是否为宝塔环境
        module_path (str): ModSecurity模块路径
        modsec_conf_dir (str): ModSecurity配置目录
        
    Returns:
        bool: 更新是否成功
    """
    logger.info("更新Nginx配置以加载ModSecurity模块...")
    
    # 确定Nginx配置目录
    nginx_conf_dir = BT_NGINX_CONF_DIR if bt_env else STD_NGINX_CONF_DIR
    
    # 创建ModSecurity模块配置文件
    modsec_module_conf = os.path.join(nginx_conf_dir, "modules/modsecurity.conf")
    
    # 确保模块目录存在
    os.makedirs(os.path.dirname(modsec_module_conf), exist_ok=True)
    
    try:
        # 写入模块加载配置
        with open(modsec_module_conf, 'w') as f:
            f.write(f"load_module {module_path};\n")
        
        logger.info(f"创建了ModSecurity模块加载配置: {modsec_module_conf}")
        
        # 创建或更新modsecurity.conf包含文件
        modsec_include_conf = os.path.join(nginx_conf_dir, "conf.d/modsecurity.conf")
        os.makedirs(os.path.dirname(modsec_include_conf), exist_ok=True)
        
        with open(modsec_include_conf, 'w') as f:
            f.write("# ModSecurity configuration\n")
            f.write("modsecurity on;\n")
            f.write(f"modsecurity_rules_file {os.path.join(modsec_conf_dir, 'main.conf')};\n")
        
        logger.info(f"创建了ModSecurity规则加载配置: {modsec_include_conf}")
        
        # 在http块中包含模块配置
        main_nginx_conf = os.path.join(nginx_conf_dir, "nginx.conf")
        
        if os.path.exists(main_nginx_conf):
            # 读取当前配置
            with open(main_nginx_conf, 'r') as f:
                content = f.read()
            
            # 如果已存在modsecurity.conf包含指令，跳过
            if "include modules/modsecurity.conf;" in content and "include conf.d/modsecurity.conf;" in content:
                logger.info("Nginx配置文件已包含ModSecurity配置，跳过更新")
                return True
            
            # 备份原始配置
            backup_file = main_nginx_conf + ".bak"
            shutil.copy2(main_nginx_conf, backup_file)
            logger.info(f"已备份Nginx配置文件到 {backup_file}")
            
            # 添加include指令到http块的开头
            pattern = re.compile(r'(\s*http\s*{)', re.MULTILINE)
            new_content = pattern.sub(r'\1\n    include modules/modsecurity.conf;\n    include conf.d/modsecurity.conf;', content, count=1)
            
            # 写回文件
            with open(main_nginx_conf, 'w') as f:
                f.write(new_content)
            
            logger.info(f"成功更新Nginx主配置文件: {main_nginx_conf}")
        else:
            logger.error(f"Nginx主配置文件不存在: {main_nginx_conf}")
            return False
        
        return True
    except Exception as e:
        logger.error(f"更新Nginx配置文件时出错: {e}")
        return False

def test_nginx_config(bt_env):
    """测试Nginx配置是否有效
    
    Args:
        bt_env (bool): 是否为宝塔环境
        
    Returns:
        bool: 配置是否有效
    """
    logger.info("测试Nginx配置...")
    
    try:
        nginx_binary = BT_NGINX_BINARY if bt_env else STD_NGINX_BINARY
        
        cmd = f"{nginx_binary} -t"
        process = subprocess.run(cmd, shell=True, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        
        if process.returncode == 0:
            logger.info("Nginx配置测试通过")
            return True
        else:
            logger.error(f"Nginx配置测试失败: {process.stderr}")
            return False
    except Exception as e:
        logger.error(f"测试Nginx配置时出错: {e}")
        return False

def restart_nginx(bt_env):
    """重启Nginx服务
    
    Args:
        bt_env (bool): 是否为宝塔环境
        
    Returns:
        bool: 重启是否成功
    """
    logger.info("重启Nginx服务...")
    
    try:
        if bt_env:
            # 宝塔环境使用宝塔的重启脚本
            cmd = "bt nginx restart"
        else:
            # 标准环境使用systemctl或service
            if os.path.exists("/bin/systemctl") or os.path.exists("/usr/bin/systemctl"):
                cmd = "systemctl restart nginx"
            else:
                cmd = "service nginx restart"
        
        process = subprocess.run(cmd, shell=True, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        
        if process.returncode == 0:
            logger.info("Nginx成功重启")
            return True
        else:
            logger.error(f"Nginx重启失败: {process.stderr}")
            return False
    except Exception as e:
        logger.error(f"重启Nginx时出错: {e}")
        return False

def get_nginx_info(bt_env=False):
    """获取Nginx版本和编译信息
    
    Args:
        bt_env (bool, optional): 是否为宝塔环境
    
    Returns:
        tuple: (nginx_version, configure_args, nginx_binary)
    """
    logger.info("获取Nginx版本和编译信息...")
    
    try:
        # 确定Nginx二进制文件路径
        nginx_binary = BT_NGINX_BINARY if bt_env else STD_NGINX_BINARY
        
        # 检查Nginx是否安装
        if not os.path.exists(nginx_binary):
            logger.error(f"Nginx二进制文件不存在: {nginx_binary}")
            return None, None, None
        
        # 获取Nginx版本
        version_cmd = f"{nginx_binary} -v"
        process = subprocess.run(version_cmd, shell=True, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        
        # 解析版本输出（通常在stderr中）
        version_output = process.stderr if process.stderr else process.stdout
        version_match = re.search(r'nginx/(\d+\.\d+\.\d+)', version_output)
        
        if not version_match:
            logger.error(f"无法解析Nginx版本: {version_output}")
            return None, None, None
        
        nginx_version = version_match.group(1)
        logger.info(f"检测到Nginx版本: {nginx_version}")
        
        # 获取编译参数
        if bt_env:
            # 宝塔环境的编译参数可能存储在特定位置
            nginx_configure_path = "/www/server/nginx/src/configure.txt"
            if os.path.exists(nginx_configure_path):
                with open(nginx_configure_path, 'r') as f:
                    configure_args = f.read().strip()
            else:
                # 如果找不到配置文件，则尝试使用编译信息获取
                configure_cmd = f"{nginx_binary} -V"
                process = subprocess.run(configure_cmd, shell=True, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                configure_output = process.stderr if process.stderr else process.stdout
                configure_match = re.search(r'configure arguments:\s*(.*)', configure_output)
                
                if configure_match:
                    configure_args = configure_match.group(1)
                else:
                    logger.error(f"无法获取Nginx编译参数: {configure_output}")
                    return nginx_version, "", nginx_binary
        else:
            # 标准环境直接获取编译信息
            configure_cmd = f"{nginx_binary} -V"
            process = subprocess.run(configure_cmd, shell=True, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            configure_output = process.stderr if process.stderr else process.stdout
            configure_match = re.search(r'configure arguments:\s*(.*)', configure_output)
            
            if configure_match:
                configure_args = configure_match.group(1)
            else:
                logger.error(f"无法获取Nginx编译参数: {configure_output}")
                return nginx_version, "", nginx_binary
        
        logger.info(f"获取到Nginx编译参数: {configure_args[:80]}...")
        return nginx_version, configure_args, nginx_binary
    
    except Exception as e:
        logger.error(f"获取Nginx信息时出错: {e}")
        return None, None, None

#############################################################
# 主函数
#############################################################

def main(force_update=False, skip_deps=False, verbose=False):
    """主函数：安装和配置ModSecurity
    
    Args:
        force_update (bool, optional): 强制更新ModSecurity模块，即使已存在也会重新编译。默认为False。
        skip_deps (bool, optional): 是否跳过依赖安装。当系统无法连接到网络时可以使用此选项。默认为False。
        verbose (bool, optional): 是否显示详细日志。默认为False。
    
    Returns:
        bool: 安装是否成功
    """
    if verbose:
        logger.setLevel(logging.DEBUG)
    
    # 检查是否为root用户
    if os.geteuid() != 0:
        logger.error("此脚本需要root权限运行")
        return False
    
    # 检测是否为宝塔面板环境
    bt_env = os.path.exists("/www/server/panel/")
    if bt_env:
        logger.info("检测到宝塔面板环境，将使用宝塔路径")
    
    try:
        # 预检查软件源配置（仅针对RHEL/CentOS系统）
        os_type, os_version = detect_os()
        if os_type == "rhel":
            logger.info("执行软件源预检查...")
            check_and_fix_repo_config(os_version)
        
        # 初始化仓库缓存
        init_repo_cache()
        
        # 安装系统依赖
        if not skip_deps:
            logger.info("开始安装系统依赖...")
            if not install_dependencies(bt_env):
                logger.warning("系统依赖安装失败，尝试使用备选方法安装关键依赖...")
                if os_type == "rhel":
                    # 对于CentOS 7 EOL系统，尝试直接RPM安装
                    if not install_direct_rpm_dependencies():
                        logger.error("所有尝试安装依赖的方法都失败了")
                        return False
                else:
                    logger.error("无法安装系统依赖，请手动安装必要的开发工具后重试")
                    return False
        else:
            logger.info("跳过依赖安装")
        
        # 下载和编译ModSecurity
        logger.info("开始下载和编译ModSecurity...")
        success, modsec_dir = download_modsecurity(force_update)
        if not success:
            logger.error("下载和编译ModSecurity失败")
            return False
        
        # 安装ModSecurity-Nginx模块
        logger.info("开始安装ModSecurity-Nginx模块...")
        if not install_modsecurity_nginx(modsec_dir, force_update, bt_env):
            logger.error("安装ModSecurity-Nginx模块失败")
            return False
        
        logger.info("ModSecurity安装成功！")
        logger.info("现在您可以通过修改/etc/nginx/modsecurity/main.conf来配置ModSecurity规则")
        return True
    
    except Exception as e:
        logger.error(f"安装过程中发生异常: {e}")
        return False

if __name__ == "__main__":
    # 设置参数解析
    parser = argparse.ArgumentParser(description="ModSecurity安装脚本")
    parser.add_argument("-f", "--force", action="store_true", help="强制更新ModSecurity模块，即使已存在也会重新编译")
    parser.add_argument("--skip-deps", action="store_true", help="跳过依赖安装，当系统无法连接到网络时可以使用此选项")
    parser.add_argument("-v", "--verbose", action="store_true", help="显示详细的安装过程信息")
    args = parser.parse_args()
    
    # 运行主函数
    success = main(force_update=args.force, skip_deps=args.skip_deps, verbose=args.verbose)
    
    # 根据安装结果设置退出码
    sys.exit(0 if success else 1)