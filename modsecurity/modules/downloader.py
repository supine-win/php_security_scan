#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件下载模块
负责处理网络文件下载，支持缓存、重试和状态报告
"""

import os
import subprocess
import logging
import time
import shutil
import sys

logger = logging.getLogger('modsecurity_installer')

# 尝试导入缓存管理模块
try:
    try:
        from modules.cache_manager import get_file_cache_path, cache_file_exists
        from modules.constants import DEFAULT_CACHE_DIR, MODSEC_VERSION, NGINX_VERSION, OWASP_CRS_VERSION
    except ImportError as e:
        logging.error(f"导入模块时出错: {e}")
        # 允许程序继续运行，但缓存功能可能受限
    _cache_support = True
except ImportError:
    logger.warning("缓存管理模块导入失败，将禁用文件缓存功能")
    _cache_support = False

def download_file(url, target_file, timeout=180, retries=3, delay=2, use_cache=True, cache_dir=None, version=None):
    """下载文件，支持缓存系统
    
    按照类型/版本/文件名的结构缓存下载文件
    
    Args:
        url (str): 下载URL
        target_file (str): 目标文件路径
        timeout (int): 超时时间(秒)
        retries (int): 重试次数
        delay (int): 重试间隔时间(秒)
        use_cache (bool): 是否使用缓存
        cache_dir (str): 缓存目录，如为None则使用默认缓存目录
        version (str): 文件版本，如为None则根据文件名自动推断
        
    Returns:
        bool: 是否成功下载
    """
    try:
        # 创建目标目录
        target_dir = os.path.dirname(target_file)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
            
        # 计算版本信息（如果未提供）
        if version is None:
            # 尝试从 URL 或文件名推断版本
            file_name = os.path.basename(url)
            if 'modsecurity' in url.lower() and MODSEC_VERSION in url:
                version = MODSEC_VERSION
            elif 'nginx' in url.lower() and NGINX_VERSION in url:
                version = NGINX_VERSION
            elif 'coreruleset' in url.lower() or 'crs' in url.lower():
                version = OWASP_CRS_VERSION
            else:
                # 如果无法推断，使用通用版本标记
                version = "latest"
                
        # 检查缓存
        cache_file = None
        if _cache_support and use_cache:
            # 如果未提供缓存目录，使用默认目录
            if cache_dir is None:
                cache_dir = DEFAULT_CACHE_DIR
                
            # 获取缓存文件路径
            cache_file = get_file_cache_path(cache_dir, url, version)
            
            # 检查缓存是否存在
            if os.path.exists(cache_file) and os.path.getsize(cache_file) > 0:
                logger.info(f"使用缓存文件: {cache_file}")
                
                # 从缓存复制到目标文件
                try:
                    shutil.copy2(cache_file, target_file)
                    logger.info(f"成功从缓存复制文件 ({os.path.getsize(target_file)} 字节)")
                    return True
                except Exception as e:
                    logger.warning(f"从缓存复制文件失败: {e}")
                    # 如果复制失败，尝试直接下载
                    
        # 如果缓存不可用或缓存复制失败，执行下载
        logger.info(f"下载 {url} 到 {target_file}")
        
        attempt = 0
        while attempt < retries:
            try:
                attempt += 1
                
                # 构建curl命令，添加超时和重试参数
                cmd = f"curl -L --connect-timeout 30 --retry 3 --max-time {timeout} -o {target_file} {url}"
                process = subprocess.run(cmd, shell=True, check=True, 
                                        stdout=subprocess.PIPE, 
                                        stderr=subprocess.PIPE,
                                        timeout=timeout + 30)  # 给subprocess的超时稍微长一点
                
                # 验证文件是否存在且大小大于0
                if os.path.exists(target_file) and os.path.getsize(target_file) > 0:
                    file_size = os.path.getsize(target_file)
                    logger.info(f"成功下载文件 ({file_size} 字节)")
                    
                    # 如果缓存支持并启用，将文件保存到缓存
                    if _cache_support and use_cache and cache_file:
                        try:
                            # 确保缓存目录存在
                            cache_dir = os.path.dirname(cache_file)
                            if not os.path.exists(cache_dir):
                                os.makedirs(cache_dir, exist_ok=True)
                                
                            # 将文件复制到缓存
                            shutil.copy2(target_file, cache_file)
                            logger.info(f"文件已保存到缓存: {cache_file}")
                        except Exception as e:
                            logger.warning(f"保存文件到缓存失败: {e}")
                            # 保存到缓存失败不影响整体成功
                    
                    return True
                else:
                    logger.warning(f"下载文件结果异常: 文件为空或不存在")
                    if attempt < retries:
                        logger.info(f"将在 {delay} 秒后进行第 {attempt+1}/{retries} 次尝试")
                        time.sleep(delay)
                    continue
                
            except subprocess.CalledProcessError as e:
                logger.warning(f"下载文件失败 (尝试 {attempt}/{retries}): {e}")
                if e.stderr:
                    logger.debug(f"错误输出: {e.stderr.decode()}")
                
                if attempt < retries:
                    logger.info(f"将在 {delay} 秒后进行第 {attempt+1}/{retries} 次尝试")
                    time.sleep(delay)
                    # 尝试使用不同的时间参数
                    timeout = timeout + 30
                else:
                    return False
                    
            except subprocess.TimeoutExpired:
                logger.warning(f"下载文件超时 (尝试 {attempt}/{retries})")
                if attempt < retries:
                    logger.info(f"将在 {delay} 秒后进行第 {attempt+1}/{retries} 次尝试")
                    time.sleep(delay)
                    # 尝试使用更长的超时时间
                    timeout = timeout + 60
                else:
                    return False
        
        return False
    except Exception as e:
        logger.error(f"下载文件时发生未知错误: {e}")
        return False


def is_url_accessible(url, timeout=10):
    """检查URL是否可访问
    
    Args:
        url (str): 要检查的URL
        timeout (int): 超时时间(秒)
        
    Returns:
        bool: URL是否可访问
    """
    try:
        # 使用curl检查URL可访问性
        cmd = f"curl -s -I --connect-timeout {timeout} {url}"
        result = subprocess.run(cmd, shell=True, check=False, 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE,
                               timeout=timeout+5)
        
        # 检查状态码
        if result.returncode == 0:
            return True
        else:
            logger.debug(f"URL {url} 访问失败，状态码: {result.returncode}")
            return False
    except Exception as e:
        logger.debug(f"检查URL {url} 可访问性时发生错误: {e}")
        return False


# 测试函数
if __name__ == "__main__":
    try:
        from modules.constants import setup_logger
    except ImportError as e:
        print(f"导入模块时出错: {e}")
        sys.exit(1)
    
    # 设置日志
    logger = setup_logger(verbose=True)
    
    # 测试URL可访问性
    test_urls = [
        "https://gitee.com/supine-win/ModSecurity.git",
        "https://github.com/SpiderLabs/ModSecurity.git",
        "https://nginx.org/download/nginx-1.24.0.tar.gz"
    ]
    
    logger.info("测试URL可访问性:")
    for url in test_urls:
        result = is_url_accessible(url)
        logger.info(f"{url}: {'可访问' if result else '不可访问'}")
    
    # 测试文件下载
    import tempfile
    with tempfile.TemporaryDirectory() as temp_dir:
        test_file = os.path.join(temp_dir, "test.txt")
        result = download_file("https://gitee.com/supine-win/ModSecurity/raw/master/README.md", test_file)
        logger.info(f"文件下载结果: {'成功' if result else '失败'}")
