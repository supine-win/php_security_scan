#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ModSecurity编译模块
负责下载、配置和编译ModSecurity核心库
"""

import os
import re
import shutil
import subprocess
import logging
import time
import tempfile
from pathlib import Path

# 导入相关模块
from modules.constants import MODSEC_VERSION, MODSEC_CONNECTOR_VERSION, MODSEC_DOWNLOAD_URL
from modules.system_detector import check_gcc_version

logger = logging.getLogger('modsecurity_installer')

def download_file(url, target_file, timeout=180):
    """下载文件
    
    Args:
        url (str): 下载URL
        target_file (str): 目标文件路径
        timeout (int): 超时时间(秒)
        
    Returns:
        bool: 是否成功下载
    """
    try:
        # 创建目标目录
        target_dir = os.path.dirname(target_file)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
        
        # 使用curl下载文件
        logger.info(f"下载 {url} 到 {target_file}")
        
        cmd = f"curl -L --connect-timeout 30 --retry 3 -o {target_file} {url}"
        process = subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # 验证文件是否存在且大小大于0
        if os.path.exists(target_file) and os.path.getsize(target_file) > 0:
            logger.info(f"成功下载文件 ({os.path.getsize(target_file)} 字节)")
            return True
        else:
            logger.error(f"下载文件失败: 文件为空")
            return False
    except subprocess.CalledProcessError as e:
        logger.error(f"下载文件失败: {e}")
        logger.debug(f"错误输出: {e.stderr.decode() if e.stderr else 'None'}")
        return False
    except Exception as e:
        logger.error(f"下载文件时发生未知错误: {e}")
        return False

def extract_archive(archive_file, extract_dir):
    """解压归档文件
    
    Args:
        archive_file (str): 归档文件路径
        extract_dir (str): 解压目录
        
    Returns:
        bool: 是否成功解压
    """
    try:
        if not os.path.exists(extract_dir):
            os.makedirs(extract_dir)
        
        logger.info(f"解压 {archive_file} 到 {extract_dir}")
        
        # 检查文件类型并使用相应的解压命令
        if archive_file.endswith('.tar.gz') or archive_file.endswith('.tgz'):
            cmd = f"tar -xzf {archive_file} -C {extract_dir}"
        elif archive_file.endswith('.tar.bz2'):
            cmd = f"tar -xjf {archive_file} -C {extract_dir}"
        elif archive_file.endswith('.zip'):
            cmd = f"unzip -q {archive_file} -d {extract_dir}"
        else:
            logger.error(f"不支持的归档格式: {archive_file}")
            return False
        
        process = subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"解压归档文件失败: {e}")
        logger.debug(f"错误输出: {e.stderr.decode() if e.stderr else 'None'}")
        return False
    except Exception as e:
        logger.error(f"解压归档文件时发生未知错误: {e}")
        return False

def init_git_submodules(repo_dir):
    """初始化并更新Git子模块
    
    Args:
        repo_dir (str): Git仓库目录
        
    Returns:
        bool: 是否成功初始化
    """
    try:
        if not os.path.exists(os.path.join(repo_dir, '.git')):
            logger.warning(f"目录 {repo_dir} 不是Git仓库")
            return False
        
        logger.info(f"初始化Git子模块: {repo_dir}")
        
        # 初始化子模块
        init_cmd = f"cd {repo_dir} && git submodule init"
        subprocess.run(init_cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # 更新子模块
        update_cmd = f"cd {repo_dir} && git submodule update"
        subprocess.run(update_cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        logger.info("成功初始化和更新Git子模块")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"初始化Git子模块失败: {e}")
        logger.debug(f"错误输出: {e.stderr.decode() if e.stderr else 'None'}")
        return False
    except Exception as e:
        logger.error(f"初始化Git子模块时发生未知错误: {e}")
        return False

def build_modsecurity(build_dir, verbose=False):
    """构建ModSecurity核心库
    
    Args:
        build_dir (str): 构建目录
        verbose (bool): 是否输出详细信息
        
    Returns:
        bool: 是否成功构建
    """
    modsec_dir = os.path.join(build_dir, "ModSecurity")
    
    if not os.path.exists(modsec_dir):
        logger.error(f"ModSecurity源码目录不存在: {modsec_dir}")
        return False
    
    # 检查GCC版本
    if not check_gcc_version():
        logger.warning("GCC版本不满足要求，ModSecurity需要GCC 7或更高版本支持C++17")
    
    try:
        logger.info("开始构建ModSecurity...")
        
        # 切换到ModSecurity目录
        os.chdir(modsec_dir)
        
        # 初始化Git子模块（重要）
        if not init_git_submodules(modsec_dir):
            logger.error("初始化Git子模块失败，无法继续构建")
            return False
        
        # 执行构建脚本
        logger.info("生成编译配置...")
        build_cmd = "./build.sh"
        process = subprocess.run(build_cmd, shell=True, check=True, 
                                stdout=subprocess.PIPE if not verbose else None, 
                                stderr=subprocess.PIPE if not verbose else None)
        
        # 配置
        logger.info("执行: ./configure --disable-doxygen-doc")
        configure_cmd = "./configure --disable-doxygen-doc"
        process = subprocess.run(configure_cmd, shell=True, check=True, 
                                stdout=subprocess.PIPE if not verbose else None, 
                                stderr=subprocess.PIPE if not verbose else None)
        
        # 编译
        logger.info("执行: make")
        make_cmd = "make"
        process = subprocess.run(make_cmd, shell=True, check=True, 
                                stdout=subprocess.PIPE if not verbose else None, 
                                stderr=subprocess.PIPE if not verbose else None)
        
        # 安装
        logger.info("执行: make install")
        install_cmd = "make install"
        process = subprocess.run(install_cmd, shell=True, check=True, 
                                stdout=subprocess.PIPE if not verbose else None, 
                                stderr=subprocess.PIPE if not verbose else None)
        
        logger.info("ModSecurity核心库构建完成")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"构建ModSecurity失败: {e}")
        logger.debug(f"错误输出: {e.stderr.decode() if e.stderr else 'None'}")
        return False
    except Exception as e:
        logger.error(f"构建ModSecurity时发生未知错误: {e}")
        return False

def download_and_build_modsecurity(build_dir, verbose=False):
    """下载并构建ModSecurity
    
    Args:
        build_dir (str): 构建目录
        verbose (bool): 是否输出详细信息
        
    Returns:
        bool: 是否成功下载和构建
    """
    # 创建构建目录
    if not os.path.exists(build_dir):
        os.makedirs(build_dir)
    
    # 下载ModSecurity
    archive_name = f"modsecurity-v{MODSEC_VERSION}.tar.gz"
    archive_path = os.path.join(build_dir, archive_name)
    
    if not os.path.exists(archive_path):
        if not download_file(MODSEC_DOWNLOAD_URL, archive_path):
            logger.error("下载ModSecurity失败")
            return False
    
    # 解压ModSecurity
    extract_path = build_dir
    if not extract_archive(archive_path, extract_path):
        logger.error("解压ModSecurity失败")
        return False
    
    # 确认ModSecurity目录
    modsec_dir = os.path.join(build_dir, f"modsecurity-v{MODSEC_VERSION}")
    if os.path.exists(modsec_dir):
        # 重命名为标准名称
        os.rename(modsec_dir, os.path.join(build_dir, "ModSecurity"))
    
    # 检查ModSecurity目录
    modsec_dir = os.path.join(build_dir, "ModSecurity")
    if not os.path.exists(modsec_dir):
        logger.error(f"未找到ModSecurity目录: {modsec_dir}")
        return False
    
    # 构建ModSecurity
    return build_modsecurity(build_dir, verbose)

# 如果直接运行此脚本，则执行测试
if __name__ == "__main__":
    import tempfile
    from modules.constants import setup_logger
    
    # 设置日志
    logger = setup_logger()
    
    # 创建临时构建目录
    with tempfile.TemporaryDirectory() as temp_dir:
        logger.info(f"使用临时目录: {temp_dir}")
        
        # 测试下载和构建ModSecurity
        if download_and_build_modsecurity(temp_dir, verbose=True):
            logger.info("ModSecurity构建测试成功")
        else:
            logger.error("ModSecurity构建测试失败")
