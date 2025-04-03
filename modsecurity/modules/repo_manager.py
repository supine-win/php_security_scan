#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
软件源管理模块
负责检查和修复软件源配置，特别是针对CentOS EOL环境
"""

import os
import re
import shutil
import subprocess
import logging
import time
from pathlib import Path

# 导入相关模块
from modules.system_detector import detect_os, is_centos_eol, get_centos_version
from modules.constants import MIRRORS, CENTOS_EOL_VERSIONS

logger = logging.getLogger('modsecurity_installer')

def test_yum_repo():
    """测试YUM软件源是否可用
    
    Returns:
        bool: 如果YUM源正常返回True，否则返回False
    """
    logger.info("测试YUM软件源配置...")
    try:
        # 使用makecache测试仓库连接
        process = subprocess.run("yum makecache", shell=True, stdout=subprocess.PIPE, 
                             stderr=subprocess.PIPE, universal_newlines=True, timeout=60)
        output = process.stdout + process.stderr
        
        # 检查常见错误模式
        if "Could not retrieve mirrorlist" in output or "Cannot find a valid baseurl" in output:
            logger.warning("检测到YUM镜像源错误")
            return False
        
        # 执行简单的搜索以确认仓库正常工作
        process = subprocess.run("yum search gcc -q", shell=True, stdout=subprocess.PIPE, 
                              stderr=subprocess.PIPE, universal_newlines=True, timeout=30)
        
        # 如果退出码为0，则说明源可用
        return process.returncode == 0
    except subprocess.TimeoutExpired:
        logger.warning("YUM源测试超时，网络可能存在问题")
        return False
    except Exception as e:
        logger.warning(f"测试YUM源时发生错误: {e}")
        return False

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
    
    logger.info(f"备份原始YUM仓库配置到 {backup_dir}")
    
    try:
        for file in os.listdir("/etc/yum.repos.d"):
            if file.endswith(".repo"):
                source = os.path.join("/etc/yum.repos.d", file)
                target = os.path.join(backup_dir, file)
                # 只在目标文件不存在时复制
                if not os.path.exists(target):
                    shutil.copy2(source, target)
        return True
    except Exception as e:
        logger.error(f"备份YUM仓库配置失败: {e}")
        return False

def disable_all_repo_files():
    """禁用所有默认的YUM仓库配置文件
    
    Returns:
        bool: 是否成功禁用所有仓库
    """
    logger.info("临时禁用所有默认YUM仓库配置")
    
    try:
        for file in os.listdir("/etc/yum.repos.d"):
            if file.endswith(".repo") and not file.startswith(("aliyun", "tsinghua")):
                source = os.path.join("/etc/yum.repos.d", file)
                disabled = os.path.join("/etc/yum.repos.d", f"{file}.disabled")
                # 移动文件以禁用仓库
                if os.path.exists(source) and not os.path.exists(disabled):
                    shutil.move(source, disabled)
        return True
    except Exception as e:
        logger.error(f"禁用YUM仓库配置失败: {e}")
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
baseurl=https://mirrors.aliyun.com/centos-vault/{vault_version}/os/$basearch/
gpgcheck=0
enabled=1

[updates]
name=CentOS-{version} - Updates
baseurl=https://mirrors.aliyun.com/centos-vault/{vault_version}/updates/$basearch/
gpgcheck=0
enabled=1

[extras]
name=CentOS-{version} - Extras
baseurl=https://mirrors.aliyun.com/centos-vault/{vault_version}/extras/$basearch/
gpgcheck=0
enabled=1

# EPEL仓库
[epel]
name=Extra Packages for Enterprise Linux {version}
baseurl=https://mirrors.aliyun.com/epel/{version}/$basearch
enabled=1
gpgcheck=0
"""
    else:  # version == "8"
        return f"""# CentOS {version} - 阿里云镜像
[base]
name=CentOS-{version} - Base
baseurl=https://mirrors.aliyun.com/centos-vault/{vault_version}/BaseOS/$basearch/os/
gpgcheck=0
enabled=1

[appstream]
name=CentOS-{version} - AppStream
baseurl=https://mirrors.aliyun.com/centos-vault/{vault_version}/AppStream/$basearch/os/
gpgcheck=0
enabled=1

[extras]
name=CentOS-{version} - Extras
baseurl=https://mirrors.aliyun.com/centos-vault/{vault_version}/extras/$basearch/os/
gpgcheck=0
enabled=1

# EPEL仓库
[epel]
name=Extra Packages for Enterprise Linux {version}
baseurl=https://mirrors.aliyun.com/epel/{version}/Everything/$basearch
enabled=1
gpgcheck=0
"""
