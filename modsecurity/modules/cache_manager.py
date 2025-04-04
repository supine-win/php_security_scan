#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缓存管理模块
负责管理下载文件和Git仓库的缓存，减少重复下载
"""

import os
import shutil
import logging
import urllib.parse

logger = logging.getLogger('modsecurity_installer')

def setup_cache_dir(cache_dir):
    """
    设置缓存目录结构
    
    Args:
        cache_dir (str): 缓存根目录
    
    Returns:
        dict: 包含各种缓存子目录的字典
    """
    # 创建主缓存目录
    os.makedirs(cache_dir, exist_ok=True)
    
    # 创建Git仓库缓存目录
    git_cache_dir = os.path.join(cache_dir, "git")
    os.makedirs(git_cache_dir, exist_ok=True)
    
    # 创建文件缓存目录
    file_cache_dir = os.path.join(cache_dir, "files")
    os.makedirs(file_cache_dir, exist_ok=True)
    
    logger.info(f"缓存目录已设置: {cache_dir}")
    
    return {
        "root": cache_dir,
        "git": git_cache_dir,
        "files": file_cache_dir
    }

def clear_cache(cache_dir):
    """
    清除缓存目录
    
    Args:
        cache_dir (str): 缓存根目录
    """
    if os.path.exists(cache_dir):
        logger.info(f"清除缓存目录: {cache_dir}")
        try:
            shutil.rmtree(cache_dir)
            # 重新创建空目录
            setup_cache_dir(cache_dir)
            logger.info("缓存目录已清除并重新创建")
        except Exception as e:
            logger.error(f"清除缓存目录时出错: {e}")
    else:
        logger.info(f"缓存目录不存在: {cache_dir}")
        setup_cache_dir(cache_dir)

def get_git_cache_path(cache_dir, repo_url, branch=None):
    """
    获取Git仓库的缓存路径
    
    Args:
        cache_dir (str): 缓存根目录
        repo_url (str): 仓库URL
        branch (str): 分支名，可选
    
    Returns:
        str: 缓存路径
    """
    # 提取仓库名称
    repo_name = repo_url.split('/')[-1]
    if repo_name.endswith('.git'):
        repo_name = repo_name[:-4]
    
    # 添加分支信息
    if branch:
        repo_name = f"{repo_name}_{branch}"
    
    return os.path.join(cache_dir, "git", repo_name)

def get_file_cache_path(cache_dir, file_url, version=None):
    """
    获取文件的缓存路径
    
    按照"类型/版本/文件名"的结构组织缓存
    
    Args:
        cache_dir (str): 缓存根目录
        file_url (str): 文件URL
        version (str): 版本号，可选
    
    Returns:
        str: 缓存路径
    """
    # 解析URL获取文件名
    parsed_url = urllib.parse.urlparse(file_url)
    file_name = os.path.basename(parsed_url.path)
    
    # 从路径中提取类型(例如：modsecurity, nginx)
    path_parts = parsed_url.path.split('/')
    file_type = "unknown"
    
    # 尝试推断文件类型
    for type_key in ["modsecurity", "nginx", "connector", "crs", "coreruleset"]:
        if any(type_key in part.lower() for part in path_parts):
            file_type = type_key
            break
    
    # 如果未指定版本，使用"latest"
    if not version:
        version = "latest"
    
    # 创建缓存目录结构
    type_dir = os.path.join(cache_dir, "files", file_type)
    version_dir = os.path.join(type_dir, version)
    
    os.makedirs(type_dir, exist_ok=True)
    os.makedirs(version_dir, exist_ok=True)
    
    return os.path.join(version_dir, file_name)

def cache_file_exists(cache_dir, file_url, version=None):
    """
    检查文件是否已缓存
    
    Args:
        cache_dir (str): 缓存根目录
        file_url (str): 文件URL
        version (str): 版本号，可选
    
    Returns:
        bool: 文件是否已缓存
    """
    cache_path = get_file_cache_path(cache_dir, file_url, version)
    return os.path.exists(cache_path)

# 测试函数
if __name__ == "__main__":
    from constants import DEFAULT_CACHE_DIR, MODSEC_DOWNLOAD_URL, NGINX_DOWNLOAD_URL
    from constants import GIT_REPOS, MODSEC_VERSION
    
    # 设置测试日志
    logging.basicConfig(level=logging.INFO)
    
    # 测试缓存目录设置
    cache_dirs = setup_cache_dir(DEFAULT_CACHE_DIR)
    print(f"Cache directories: {cache_dirs}")
    
    # 测试Git缓存路径
    git_repo_url = GIT_REPOS["github"]["modsecurity"]
    git_cache_path = get_git_cache_path(DEFAULT_CACHE_DIR, git_repo_url)
    print(f"Git cache path: {git_cache_path}")
    
    # 测试文件缓存路径
    file_cache_path = get_file_cache_path(DEFAULT_CACHE_DIR, MODSEC_DOWNLOAD_URL, MODSEC_VERSION)
    print(f"File cache path: {file_cache_path}")
