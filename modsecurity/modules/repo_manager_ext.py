#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
软件源管理模块扩展
包含清华源配置和软件源检查修复功能
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

# 定义一个公共函数test_yum_repo用于导出，内部调用local_test_yum_repo实现
def test_yum_repo():
    """测试YUM软件源是否可用
    
    Returns:
        bool: 如果YUM源正常返回True，否则返回False
    """
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

def fix_centos_yum_mirrors():
    """修复CentOS的YUM镜像源配置
    
    根据CentOS系统版本自动选择并配置适合的镜像源，特别是对EOL版本的支持
    
    Returns:
        bool: 是否成功修复镜像源
    """
    logger.info("尝试修复CentOS YUM镜像源...")
    
    # 检测当前系统
    os_type, os_version = detect_os()
    if os_type != 'rhel':
        logger.warning("当前系统不是CentOS/RHEL，跳过镜像源修复")
        return False
    
    # 使用检查和修复功能
    return check_and_fix_repo_config(os_version)

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
baseurl=https://mirrors.tuna.tsinghua.edu.cn/centos-vault/{vault_version}/os/$basearch/
gpgcheck=0
enabled=1

[updates]
name=CentOS-{version} - Updates
baseurl=https://mirrors.tuna.tsinghua.edu.cn/centos-vault/{vault_version}/updates/$basearch/
gpgcheck=0
enabled=1

[extras]
name=CentOS-{version} - Extras
baseurl=https://mirrors.tuna.tsinghua.edu.cn/centos-vault/{vault_version}/extras/$basearch/
gpgcheck=0
enabled=1

# EPEL仓库
[epel]
name=Extra Packages for Enterprise Linux {version}
baseurl=https://mirrors.tuna.tsinghua.edu.cn/epel/{version}/$basearch
enabled=1
gpgcheck=0
"""
    else:  # version == "8"
        return f"""# CentOS {version} - 清华镜像
[base]
name=CentOS-{version} - Base
baseurl=https://mirrors.tuna.tsinghua.edu.cn/centos-vault/{vault_version}/BaseOS/$basearch/os/
gpgcheck=0
enabled=1

[appstream]
name=CentOS-{version} - AppStream
baseurl=https://mirrors.tuna.tsinghua.edu.cn/centos-vault/{vault_version}/AppStream/$basearch/os/
gpgcheck=0
enabled=1

[extras]
name=CentOS-{version} - Extras
baseurl=https://mirrors.tuna.tsinghua.edu.cn/centos-vault/{vault_version}/extras/$basearch/os/
gpgcheck=0
enabled=1

# EPEL仓库
[epel]
name=Extra Packages for Enterprise Linux {version}
baseurl=https://mirrors.tuna.tsinghua.edu.cn/epel/{version}/Everything/$basearch
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
baseurl=https://mirrors.aliyun.com/centos/{version}/BaseOS/$basearch/os/
gpgcheck=0
enabled=1

[appstream]
name=CentOS-{version} - AppStream
baseurl=https://mirrors.aliyun.com/centos/{version}/AppStream/$basearch/os/
gpgcheck=0
enabled=1

[extras]
name=CentOS-{version} - Extras
baseurl=https://mirrors.aliyun.com/centos/{version}/extras/$basearch/os/
gpgcheck=0
enabled=1

# EPEL仓库
[epel]
name=Extra Packages for Enterprise Linux {version}
baseurl=https://mirrors.aliyun.com/epel/{version}/Everything/$basearch
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
baseurl=https://mirrors.tuna.tsinghua.edu.cn/centos/{version}/BaseOS/$basearch/os/
gpgcheck=0
enabled=1

[appstream]
name=CentOS-{version} - AppStream
baseurl=https://mirrors.tuna.tsinghua.edu.cn/centos/{version}/AppStream/$basearch/os/
gpgcheck=0
enabled=1

[extras]
name=CentOS-{version} - Extras
baseurl=https://mirrors.tuna.tsinghua.edu.cn/centos/{version}/extras/$basearch/os/
gpgcheck=0
enabled=1

# EPEL仓库
[epel]
name=Extra Packages for Enterprise Linux {version}
baseurl=https://mirrors.tuna.tsinghua.edu.cn/epel/{version}/Everything/$basearch
enabled=1
gpgcheck=0
"""

def check_and_fix_repo_config(os_version=None):
    """检查并修复软件源配置
    
    主动检测和修复CentOS/RHEL软件源问题，特别是针对EOL版本
    
    Args:
        os_version (str, optional): 操作系统版本，如果为None则自动检测
        
    Returns:
        bool: 是否成功修复软件源
    """
    logger.info("检查软件源配置...")
    
    # 只针对CentOS/RHEL系统
    if not os.path.exists('/etc/yum.repos.d'):
        logger.info("当前不是CentOS/RHEL系统，跳过软件源检查")
        return True
    
    # 如果未提供系统版本，自动检测
    if os_version is None:
        os_type, os_version = detect_os()
        if os_type != 'rhel':
            logger.warning("当前不是CentOS/RHEL系统，跳过镜像源修复")
            return False
    
    # 测试当前软件源是否可用
    # 直接实现test_yum_repo功能，避免循环导入
    def local_test_yum_repo():
        """测试YUM软件源是否可用
        
        Returns:
            bool: 如果YUM源正常返回True，否则返回False
        """
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
    
    if local_test_yum_repo():
        logger.info("当前软件源配置正常，无需修复")
        return True
    
    logger.warning("检测到软件源配置问题，尝试修复...")
    
    # 检测是否为EOL版本
    eol_status = is_centos_eol(os_version)
    if eol_status:
        logger.info(f"检测到CentOS {os_version}是EOL版本，将使用vault归档镜像")
    
    # 备份原始软件源配置
    # 直接实现相关函数，避免循环导入
    def local_backup_repo_files():
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
                    if not os.path.exists(target):
                        shutil.copy2(source, target)
            return True
        except Exception as e:
            logger.error(f"备份软件源配置文件失败: {e}")
            return False
    
    def local_disable_fastmirror():
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
    
    def local_disable_all_repo_files():
        """禁用所有默认的YUM仓库配置文件
        
        Returns:
            bool: 是否成功禁用所有仓库
        """
        logger.info("禁用所有原始YUM仓库配置文件")
        
        try:
            for file in os.listdir("/etc/yum.repos.d"):
                if file.endswith(".repo") and not file.startswith(("original_backup", "aliyun", "tsinghua")):
                    source = os.path.join("/etc/yum.repos.d", file)
                    disabled = os.path.join("/etc/yum.repos.d", f"{file}.disabled")
                    shutil.move(source, disabled)
            return True
        except Exception as e:
            logger.error(f"禁用原始仓库配置失败: {e}")
            return False
    
    # 调用本地实现的函数
    local_backup_repo_files()
    
    # 禁用fastmirror插件
    local_disable_fastmirror()
    
    # 禁用所有原有repo文件
    local_disable_all_repo_files()
    
    # 根据系统版本和EOL状态使用不同的镜像源配置
    success = False
    if eol_status:
        success = create_eol_mirror_config(os_version)
    else:
        success = create_standard_mirror_config(os_version)
    
    # 清理并重建YUM缓存
    try:
        logger.info("清理并重建YUM缓存...")
        subprocess.run("yum clean all", shell=True, check=True, 
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run("yum makecache", shell=True, check=True, 
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        logger.warning(f"清理或重建YUM缓存失败: {e}")
    
    # 再次测试软件源
    if success and local_test_yum_repo():
        logger.info("成功修复CentOS软件源配置")
        return True
    else:
        logger.error("修复CentOS软件源配置失败，尝试恢复原始配置")
        # 尝试恢复原始配置
        restore_original_repo_files()
        return False

def restore_original_repo_files():
    """恢复原始的YUM仓库配置文件
    
    Returns:
        bool: 是否成功恢复
    """
    backup_dir = "/etc/yum.repos.d/original_backup"
    if not os.path.exists(backup_dir):
        logger.warning("找不到YUM仓库配置备份，无法恢复")
        return False
    
    logger.info("恢复原始YUM仓库配置")
    
    try:
        # 清除当前配置
        for file in os.listdir("/etc/yum.repos.d"):
            if file.endswith((".repo", ".disabled")) and not file.startswith(("original_backup")):
                os.remove(os.path.join("/etc/yum.repos.d", file))
        
        # 恢复备份
        for file in os.listdir(backup_dir):
            if file.endswith(".repo"):
                source = os.path.join(backup_dir, file)
                target = os.path.join("/etc/yum.repos.d", file)
                shutil.copy2(source, target)
        
        # 重建YUM缓存
        subprocess.run("yum clean all", shell=True, check=False)
        subprocess.run("yum makecache", shell=True, check=False)
        
        logger.info("成功恢复原始YUM仓库配置")
        return True
    except Exception as e:
        logger.error(f"恢复YUM仓库配置失败: {e}")
        return False

def create_eol_mirror_config(centos_version):
    """为EOL版本的CentOS创建镜像源配置
    
    Args:
        centos_version (str): CentOS版本号
        
    Returns:
        bool: 是否成功创建配置
    """
    logger.info(f"检测到CentOS {centos_version} EOL版本，使用vault归档镜像")
    
    # 不同版本的CentOS使用不同的vault版本
    vault_version = CENTOS_EOL_VERSIONS.get(centos_version, "7.9.2009")
    
    # 尝试使用阿里云镜像
    mirror_config = generate_aliyun_eol_config(centos_version, vault_version)
    
    mirror_file = "/etc/yum.repos.d/aliyun-mirror.repo"
    try:
        with open(mirror_file, 'w') as f:
            f.write(mirror_config)
        logger.info("成功创建阿里云镜像源配置")
        
        # 测试镜像源是否可用
        if local_test_yum_repo():
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
        if local_test_yum_repo():
            return True
    except Exception as e:
        logger.error(f"创建清华镜像源配置失败: {e}")
    
    return False

def create_standard_mirror_config(centos_version):
    """为标准版本的CentOS创建镜像源配置
    
    Args:
        centos_version (str): CentOS版本号
        
    Returns:
        bool: 是否成功创建配置
    """
    logger.info(f"为CentOS {centos_version}创建标准版本镜像源配置")
    
    # 尝试使用阿里云镜像
    mirror_config = generate_aliyun_standard_config(centos_version)
    
    mirror_file = "/etc/yum.repos.d/aliyun-mirror.repo"
    try:
        with open(mirror_file, 'w') as f:
            f.write(mirror_config)
        logger.info("成功创建阿里云标准镜像源配置")
        
        # 测试镜像源是否可用
        if local_test_yum_repo():
            return True
    except Exception as e:
        logger.error(f"创建阿里云标准镜像源配置失败: {e}")
    
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
        logger.info("成功创建清华标准镜像源配置")
        
        # 测试镜像源是否可用
        if local_test_yum_repo():
            return True
    except Exception as e:
        logger.error(f"创建清华标准镜像源配置失败: {e}")
    
    return False
