#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ModSecurity模块管理器
负责下载和管理ModSecurity相关模块，包括Nginx连接器和OWASP CRS规则集
"""

import os
import subprocess
import logging
import shutil
import sys
import time

# 导入相关模块
try:
    from modules.git_manager import clone_git_repo, try_alternate_repo
    from modules.downloader import download_file
    from modules.constants import GIT_REPOS, MODSEC_CONNECTOR_VERSION, OWASP_CRS_VERSION, NGINX_DOWNLOAD_URL, DEFAULT_CACHE_DIR
except ImportError as e:
    logging.error(f"导入模块时出错: {e}")
    sys.exit(1)

logger = logging.getLogger('modsecurity_installer')

def download_modules(build_dir, nginx_version, verbose=False, use_gitee=True, use_cache=True, cache_dir=None):
    """下载 ModSecurity 相关模块
    
    Args:
        build_dir (str): 构建目录
        nginx_version (str): Nginx版本
        verbose (bool): 是否显示详细信息
        use_gitee (bool): 是否使用Gitee仓库
        use_cache (bool): 是否使用缓存
        cache_dir (str): 缓存目录路径，如为None则使用默认目录
        
    Returns:
        dict: 包含下载结果的字典
        {
            'success': bool,
            'message': str,
            'connector_dir': str,
            'crs_dir': str,
            'nginx_dir': str
        }
    """
    result = {
        'success': False,
        'message': '',
        'connector_dir': '',
        'crs_dir': '',
        'nginx_dir': ''
    }
    
    try:
        # 确保构建目录存在
        if not os.path.exists(build_dir):
            os.makedirs(build_dir)
        
        # 确定要使用的仓库源
        repo_source = "gitee" if use_gitee else "github"
        logger.info(f"使用 {repo_source} 作为主要代码源")
        
        # 下载 ModSecurity-Nginx 连接器
        connector_dir = os.path.join(build_dir, "ModSecurity-nginx")
        logger.info(f"下载 ModSecurity-Nginx 连接器...")
        
        main_connector_url = GIT_REPOS[repo_source]["connector"]
        fallback_connector_url = GIT_REPOS["github" if use_gitee else "gitee"]["connector"]
        
        if not try_alternate_repo(main_connector_url, fallback_connector_url, connector_dir, verbose, 
                               cache_dir=cache_dir, use_cache=use_cache):
            result['message'] = "无法下载 ModSecurity-Nginx 连接器"
            logger.error(result['message'])
            return result
        
        logger.info(f"ModSecurity-Nginx 连接器下载成功: {connector_dir}")
        result['connector_dir'] = connector_dir
        
        # 下载 OWASP ModSecurity 核心规则集
        crs_dir = os.path.join(build_dir, "owasp-modsecurity-crs")
        logger.info(f"下载 OWASP ModSecurity 核心规则集...")
        
        main_crs_url = GIT_REPOS[repo_source]["crs"]
        fallback_crs_url = GIT_REPOS["github" if use_gitee else "gitee"]["crs"]
        
        if not try_alternate_repo(main_crs_url, fallback_crs_url, crs_dir, verbose,
                              cache_dir=cache_dir, use_cache=use_cache):
            result['message'] = "无法下载 OWASP ModSecurity 核心规则集"
            logger.error(result['message'])
            return result
        
        logger.info(f"OWASP ModSecurity 核心规则集下载成功: {crs_dir}")
        result['crs_dir'] = crs_dir
        
        # 下载 Nginx 源码
        logger.info(f"下载 Nginx {nginx_version} 源码...")
        nginx_tar = os.path.join(build_dir, f"nginx-{nginx_version}.tar.gz")
        # 直接使用已定义的完整URL
        nginx_url = NGINX_DOWNLOAD_URL
        
        # 使用缓存支持的下载函数
        if not download_file(nginx_url, nginx_tar, timeout=180, retries=3, 
                         use_cache=use_cache, cache_dir=cache_dir, version=nginx_version):
            result['message'] = f"Nginx 源码下载失败: {nginx_tar}"
            logger.error(result['message'])
            return result
            
        # 检查下载是否成功
        if not os.path.exists(nginx_tar) or os.path.getsize(nginx_tar) < 1000:
            result['message'] = f"Nginx 源码下载失败或文件损坏: {nginx_tar}"
            logger.error(result['message'])
            return result
        
        # 解压 Nginx 源码
        nginx_dir = os.path.join(build_dir, f"nginx-{nginx_version}")
        extract_cmd = f"tar -xzf {nginx_tar} -C {build_dir}"
        subprocess.run(extract_cmd, shell=True, check=True,
                      stdout=subprocess.PIPE if not verbose else None,
                      stderr=subprocess.PIPE if not verbose else None)
        
        if not os.path.exists(nginx_dir):
            result['message'] = f"Nginx 源码解压失败: {nginx_dir}"
            logger.error(result['message'])
            return result
        
        logger.info(f"Nginx 源码下载并解压成功: {nginx_dir}")
        result['nginx_dir'] = nginx_dir
        
        # 所有模块下载成功
        result['success'] = True
        result['message'] = "所有模块下载成功"
        return result
        
    except Exception as e:
        result['message'] = f"下载模块时发生未知错误: {e}"
        logger.error(result['message'])
        return result


def configure_modules(modsec_dir, connector_dir, crs_dir, nginx_dir, verbose=False):
    """配置 ModSecurity 相关模块
    
    Args:
        modsec_dir (str): ModSecurity目录
        connector_dir (str): ModSecurity-Nginx连接器目录
        crs_dir (str): OWASP CRS规则集目录
        nginx_dir (str): Nginx源码目录
        verbose (bool): 是否显示详细信息
        
    Returns:
        bool: 是否成功配置
    """
    try:
        # 检查目录是否存在
        for dir_path, dir_name in [
            (modsec_dir, "ModSecurity"),
            (connector_dir, "ModSecurity-Nginx连接器"),
            (crs_dir, "OWASP CRS规则集"),
            (nginx_dir, "Nginx源码")
        ]:
            if not os.path.exists(dir_path):
                logger.error(f"{dir_name}目录不存在: {dir_path}")
                return False
        
        # 配置CRS规则集
        logger.info("配置CRS规则集...")
        crs_setup_path = os.path.join(crs_dir, "crs-setup.conf.example")
        crs_setup_dest = os.path.join(crs_dir, "crs-setup.conf")
        
        if os.path.exists(crs_setup_path):
            shutil.copy2(crs_setup_path, crs_setup_dest)
            logger.info(f"已配置CRS规则集: {crs_setup_dest}")
        else:
            logger.warning(f"CRS规则集配置文件不存在: {crs_setup_path}")
        
        # 检查Nginx配置选项
        logger.info("检查Nginx配置选项...")
        nginx_configure_cmd = f"cd {nginx_dir} && ./configure --help"
        try:
            process = subprocess.run(nginx_configure_cmd, shell=True, check=True,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
            
            config_options = process.stdout.decode()
            if "--add-module" not in config_options:
                logger.warning("Nginx不支持--add-module选项，可能无法集成ModSecurity")
            
        except subprocess.CalledProcessError as e:
            logger.warning(f"检查Nginx配置选项时出错: {e}")
        
        logger.info("ModSecurity相关模块配置完成")
        return True
        
    except Exception as e:
        logger.error(f"配置模块时发生未知错误: {e}")
        return False


def compile_nginx_with_modsecurity(nginx_dir, modsec_dir, connector_dir, verbose=False):
    """编译带有ModSecurity模块的Nginx
    
    Args:
        nginx_dir (str): Nginx源码目录
        modsec_dir (str): ModSecurity目录
        connector_dir (str): ModSecurity-Nginx连接器目录
        verbose (bool): 是否显示详细信息
        
    Returns:
        bool: 是否成功编译
    """
    try:
        # 检查目录是否存在
        for dir_path, dir_name in [
            (nginx_dir, "Nginx源码"),
            (modsec_dir, "ModSecurity"),
            (connector_dir, "ModSecurity-Nginx连接器")
        ]:
            if not os.path.exists(dir_path):
                logger.error(f"{dir_name}目录不存在: {dir_path}")
                return False
        
        logger.info("配置并编译带有ModSecurity模块的Nginx...")
        
        # 配置Nginx
        logger.info("步骤1: 配置Nginx")
        configure_cmd = f"cd {nginx_dir} && ./configure --add-module={connector_dir}"
        
        # 确保编译日志可用于调试
        log_file = os.path.join(os.path.dirname(nginx_dir), "nginx_configure.log")
        
        if verbose:
            # 直接显示输出
            proc = subprocess.run(configure_cmd, shell=True, check=True)
        else:
            # 将输出重定向到日志文件
            proc = subprocess.run(
                f"{configure_cmd} > {log_file} 2>&1",
                shell=True, 
                check=True
            )
        
        # 编译Nginx
        logger.info("步骤2: 编译Nginx")
        compile_cmd = f"cd {nginx_dir} && make -j$(nproc)"
        
        compile_log = os.path.join(os.path.dirname(nginx_dir), "nginx_compile.log")
        
        if verbose:
            # 直接显示输出
            proc = subprocess.run(compile_cmd, shell=True, check=True)
        else:
            # 将输出重定向到日志文件
            proc = subprocess.run(
                f"{compile_cmd} > {compile_log} 2>&1",
                shell=True, 
                check=True
            )
        
        # 检查编译结果
        nginx_binary = os.path.join(nginx_dir, "objs", "nginx")
        if os.path.exists(nginx_binary):
            logger.info(f"成功编译Nginx（含ModSecurity模块）: {nginx_binary}")
            return True
        else:
            logger.error(f"Nginx编译失败，未找到二进制文件: {nginx_binary}")
            return False
        
    except subprocess.CalledProcessError as e:
        logger.error(f"编译Nginx时出错: {e}")
        logger.info(f"查看日志文件以获取更多信息: {log_file if 'log_file' in locals() else 'N/A'}, {compile_log if 'compile_log' in locals() else 'N/A'}")
        return False
    except Exception as e:
        logger.error(f"编译Nginx时发生未知错误: {e}")
        return False


# 测试函数
if __name__ == "__main__":
    import tempfile
    try:
        from modules.constants import setup_logger, NGINX_VERSION
    except ImportError as e:
        logging.error(f"导入模块时出错: {e}")
        sys.exit(1)
    
    # 设置日志
    logger = setup_logger(verbose=True)
    
    # 测试下载模块
    with tempfile.TemporaryDirectory() as temp_dir:
        logger.info(f"使用临时目录进行测试: {temp_dir}")
        
        # 测试下载模块
        result = download_modules(temp_dir, NGINX_VERSION, verbose=True, use_gitee=True)
        
        if result['success']:
            logger.info(f"模块下载成功: {result}")
            
            # 创建一个模拟的ModSecurity目录
            modsec_dir = os.path.join(temp_dir, "ModSecurity")
            if not os.path.exists(modsec_dir):
                os.makedirs(modsec_dir)
            
            # 测试配置模块
            if configure_modules(
                modsec_dir,
                result['connector_dir'],
                result['crs_dir'],
                result['nginx_dir'],
                verbose=True
            ):
                logger.info("模块配置成功")
            else:
                logger.error("模块配置失败")
        else:
            logger.error(f"模块下载失败: {result['message']}")
