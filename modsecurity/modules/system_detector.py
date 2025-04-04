#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统检测模块
负责检测操作系统类型、版本和环境信息
"""

import os
import re
import subprocess
import logging
import sys
import time
from datetime import datetime

# 导入常量模块
try:
    from modules.constants import CENTOS_EOL_VERSIONS
except ImportError as e:
    logging.error(f"导入模块时出错: {e}")
    sys.exit(1)

logger = logging.getLogger('modsecurity_installer')

def get_distro_family():
    """检测系统类型
    
    Returns:
        str: 系统类型，'rhel'(CentOS/RHEL)、'debian'(Debian/Ubuntu)或'unknown'
    """
    if os.path.exists('/etc/redhat-release') or os.path.exists('/etc/centos-release'):
        return 'rhel'
    elif os.path.exists('/etc/debian_version'):
        return 'debian'
    else:
        return 'unknown'

def get_centos_version():
    """获取CentOS/RHEL版本号
    
    Returns:
        str: 版本号，如'7'或'8'，默认为'7'
    """
    version = "7"  # 默认值
    
    try:
        if os.path.exists("/etc/centos-release"):
            with open("/etc/centos-release", "r") as f:
                version_line = f.read().strip()
                match = re.search(r'release\s+(\d+)', version_line)
                if match:
                    version = match.group(1)
                    logger.info(f"检测到CentOS版本: {version}")
        elif os.path.exists("/etc/redhat-release"):
            with open("/etc/redhat-release", "r") as f:
                version_line = f.read().strip()
                match = re.search(r'release\s+(\d+)', version_line)
                if match:
                    version = match.group(1)
                    logger.info(f"检测到RHEL版本: {version}")
    except Exception as e:
        logger.warning(f"检测系统版本失败，将使用默认版本 {version}: {e}")
    
    return version

def is_centos_eol(version):
    """检查指定的CentOS版本是否已经EOL
    
    Args:
        version (str): CentOS版本号，如'7'或'8'
    
    Returns:
        bool: 如果版本已EOL返回True，否则返回False
    """
    # CentOS 6于2020年11月EOL
    # CentOS 7于2024年6月EOL
    # CentOS 8于2021年12月EOL
    if version == "6" or version == "8":
        return True
    elif version == "7":
        # 检查当前日期，2024年6月之后CentOS 7也是EOL
        current_date = datetime.now()
        if current_date.year > 2024 or (current_date.year == 2024 and current_date.month > 6):
            return True
    
    return False

def detect_bt_panel():
    """检测是否为宝塔面板环境
    
    Returns:
        bool: 如果检测到宝塔面板返回True，否则返回False
    """
    if os.path.exists("/www/server/panel/class/panelSite.py"):
        logger.info("检测到宝塔面板环境，将使用宝塔路径")
        return True
    return False

def get_nginx_info():
    """获取Nginx信息
    
    Returns:
        tuple: (是否安装, 版本号, 安装路径)
    """
    bt_panel = detect_bt_panel()
    nginx_path = ""
    
    # 根据环境确定Nginx可能的路径
    if bt_panel:
        nginx_path = "/www/server/nginx/sbin/nginx"
    
    # 如果宝塔指定路径不存在，尝试在系统路径中查找
    if not os.path.exists(nginx_path):
        try:
            nginx_path = subprocess.check_output("which nginx", shell=True, stderr=subprocess.PIPE, universal_newlines=True).strip()
        except subprocess.CalledProcessError:
            return False, "", ""
    
    # 检查Nginx是否可执行并获取版本
    if os.path.exists(nginx_path) and os.access(nginx_path, os.X_OK):
        try:
            version_output = subprocess.check_output(f"{nginx_path} -v", shell=True, stderr=subprocess.STDOUT, universal_newlines=True)
            version_match = re.search(r'nginx/(\d+\.\d+\.\d+)', version_output)
            if version_match:
                version = version_match.group(1)
                logger.info(f"检测到Nginx版本: {version}")
                return True, version, nginx_path
        except subprocess.CalledProcessError:
            pass
    
    return False, "", ""

def check_gcc_version():
    """检查GCC版本是否支持C++17
    
    Returns:
        bool: 如果GCC版本>=7返回True，否则返回False
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

def detect_os():
    """检测操作系统类型和版本号
    
    Returns:
        tuple: (os_type, os_version)，os_type可能为'rhel'、'debian'或'unknown'，
               os_version为版本号，如'7'或'8'
    """
    os_type = get_distro_family()
    os_version = ''
    
    if os_type == 'rhel':
        os_version = get_centos_version()
    elif os_type == 'debian':
        try:
            with open('/etc/debian_version', 'r') as f:
                os_version = f.read().strip()
        except Exception as e:
            logger.error(f"读取Debian版本信息失败: {e}")
    
    return os_type, os_version

def system_info_summary():
    """生成系统信息摘要
    
    Returns:
        dict: 包含系统信息的字典
    """
    os_type, os_version = detect_os()
    is_bt = detect_bt_panel()
    nginx_installed, nginx_version, nginx_path = get_nginx_info()
    gcc_supported = check_gcc_version()
    
    # 检查CentOS是否为EOL版本
    is_eol = False
    if os_type == 'rhel':
        is_eol = is_centos_eol(os_version)
        if is_eol:
            logger.warning(f"检测到CentOS {os_version}是EOL版本，将使用特殊配置")
    
    return {
        'os_type': os_type,
        'os_version': os_version,
        'is_bt_panel': is_bt,
        'nginx_installed': nginx_installed,
        'nginx_version': nginx_version,
        'nginx_path': nginx_path,
        'gcc_supports_cpp17': gcc_supported,
        'is_eol': is_eol
    }

# 如果直接运行此脚本，则输出系统信息
if __name__ == "__main__":
    import json
    try:
        from modules.constants import setup_logger
    except ImportError as e:
        logging.error(f"导入模块时出错: {e}")
        sys.exit(1)

    # 设置日志
    logger = setup_logger()
    
    # 获取并打印系统信息
    info = system_info_summary()
    print(json.dumps(info, indent=2))
