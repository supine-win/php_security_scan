#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Git仓库管理模块
负责Git仓库克隆、更新和子模块管理，支持缓存系统
"""

import os
import subprocess
import logging
import time
import shutil
import sys

# 尝试导入缓存管理器
    
logger = logging.getLogger('modsecurity_installer')

# 从缓存管理器导入缓存相关函数
try:
    try:
        from modules.cache_manager import get_git_cache_path
        from modules.constants import DEFAULT_CACHE_DIR
    except ImportError as e:
        logging.error(f"导入模块时出错: {e}")
        # 备选处理
        def get_git_cache_path(repo_url, cache_dir):
            # 简化处理方式
            import os
            import hashlib
            repo_hash = hashlib.md5(repo_url.encode()).hexdigest()
            return os.path.join(cache_dir, "git", repo_hash)
            
        DEFAULT_CACHE_DIR = os.path.expanduser("~/.modsecurity_cache")
    _cache_support = True
except ImportError:
    logger.warning("缓存管理模块导入失败，将禁用缓存功能")
    _cache_support = False

def check_submodules_initialized(repo_dir, verbose=False):
    """检查Git仓库的子模块是否已经完全初始化
    
    Args:
        repo_dir (str): Git仓库目录
        verbose (bool): 是否显示详细输出
        
    Returns:
        bool: 如果所有子模块都已初始化则返回True，否则返回False
    """
    try:
        # 保存当前目录
        original_dir = os.getcwd()
        os.chdir(repo_dir)
        
        # 检查是否有子模块配置
        if not os.path.exists('.gitmodules'):
            # 没有子模块配置文件，视为已初始化
            os.chdir(original_dir)
            return True
            
        # 使用git submodule status检查子模块状态
        submodule_status = subprocess.run("git submodule status", shell=True, check=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=5, universal_newlines=True).stdout
        
        # 返回原始目录
        os.chdir(original_dir)
        
        # 检查是否有未初始化的子模块 ('-' 开头表示未初始化)
        needs_init = any(line.strip().startswith('-') for line in submodule_status.split('\n') if line.strip())
        
        if needs_init:
            logger.info("检测到未初始化的子模块")
            return False
        else:
            logger.info("所有子模块已完全初始化")
            return True
            
    except Exception as e:
        # 确保恢复原始目录
        if 'original_dir' in locals():
            os.chdir(original_dir)
        logger.warning(f"检查子模块状态时出错: {e}")
        # 出错时保守起见返回False，建议初始化
        return False

def clone_git_repo(repo_url, target_dir, verbose=False, depth=2, branch=None, timeout=180, cache_dir=None, use_cache=True):
    """从 Git 仓库克隆代码，支持缓存系统
    
    Args:
        repo_url (str): 仓库URL
        target_dir (str): 目标目录
        verbose (bool): 是否显示详细输出
        depth (int): Git克隆深度，1表示只克隆最新提交
        branch (str): 指定分支，默认为None表示使用默认分支
        timeout (int): 命令超时时间(秒)
        cache_dir (str): 缓存目录，如为None则使用默认缓存目录
        use_cache (bool): 是否使用缓存，默认为是
        
    Returns:
        bool: 是否成功克隆
    """
    try:
        # 如果目录已存在则移除
        if os.path.exists(target_dir):
            logger.info(f"目录已存在，清除: {target_dir}")
            shutil.rmtree(target_dir)
        
        # 检查是否可以使用缓存
        if _cache_support and use_cache:
            # 如果未提供缓存目录，使用默认目录
            if cache_dir is None:
                cache_dir = DEFAULT_CACHE_DIR
            
            # 获取缓存路径
            cache_repo_path = get_git_cache_path(cache_dir, repo_url, branch)
            
            if os.path.exists(cache_repo_path):
                logger.info(f"使用缓存仓库: {cache_repo_path}")
                
                # 更新缓存仓库
                try:
                    original_dir = os.getcwd()
                    os.chdir(cache_repo_path)
                    
                    # 重置以避免本地修改冲突
                    subprocess.run("git reset --hard HEAD", shell=True, check=True,
                                  stdout=subprocess.PIPE if not verbose else None,
                                  stderr=subprocess.PIPE if not verbose else None)
                    
                    # 尝试更新仓库，如果失败也不中断
                    try:
                        logger.info("尝试更新缓存仓库...")
                        subprocess.run("git pull", shell=True, check=True,
                                     stdout=subprocess.PIPE if not verbose else None,
                                     stderr=subprocess.PIPE if not verbose else None,
                                     timeout=30)
                    except Exception as e:
                        logger.warning(f"更新缓存仓库失败，使用现有缓存: {e}")
                    
                    # 返回到原始目录
                    os.chdir(original_dir)
                    
                    # 从缓存复制到目标目录
                    logger.info(f"从缓存复制到目标目录: {target_dir}")
                    
                    # 创建目标目录的父目录
                    os.makedirs(os.path.dirname(target_dir), exist_ok=True)
                    
                    # 浅克隆仓库不支持 --local 参数，所以使用文件复制然后更新子模块
                    logger.info(f"使用直接文件复制写入缓存目录")
                    
                    # 先清除目标目录
                    if os.path.exists(target_dir):
                        shutil.rmtree(target_dir)
                        
                    # 使用文件复制实现克隆
                    shutil.copytree(cache_repo_path, target_dir, symlinks=True)
                    
                    # 检查子模块状态并智能决定是否需要初始化
                    try:
                        # 切换到克隆目录
                        original_dir = os.getcwd()
                        os.chdir(target_dir)
                        
                        # 检查子模块是否已经初始化
                        if check_submodules_initialized(target_dir, verbose):
                            logger.info("缓存中的子模块已完全初始化，跳过重复初始化")
                        else:
                            # 需要初始化子模块
                            logger.info(f"初始化和更新子模块")
                            subprocess.run("git submodule init", shell=True, check=True,
                                        stdout=subprocess.PIPE if not verbose else None,
                                        stderr=subprocess.PIPE if not verbose else None)
                            subprocess.run("git submodule update", shell=True, check=True,
                                        stdout=subprocess.PIPE if not verbose else None,
                                        stderr=subprocess.PIPE if not verbose else None)
                        
                        # 返回原始目录
                        os.chdir(original_dir)
                    except Exception as e:
                        logger.warning(f"子模块更新失败，将执行递归克隆: {e}")
                        # 返回原始目录
                        if 'original_dir' in locals():
                            os.chdir(original_dir)
                        
                        # 如果子模块更新失败，清除目录并执行一次完整的网络克隆
                        if os.path.exists(target_dir):
                            shutil.rmtree(target_dir)
                        
                        # 执行递归克隆
                        clone_cmd = f"git clone --recursive {repo_url} {target_dir}"
                        subprocess.run(clone_cmd, shell=True, check=True,
                                    stdout=subprocess.PIPE if not verbose else None,
                                    stderr=subprocess.PIPE if not verbose else None,
                                    timeout=timeout)
                    
                    # 检查是否成功
                    if os.path.exists(os.path.join(target_dir, '.git')):
                        logger.info(f"成功使用缓存克隆到: {target_dir}")
                        return True
                except Exception as e:
                    logger.warning(f"使用缓存克隆失败: {e}")
                    # 如果使用缓存失败，继续使用普通方式克隆
            else:
                # 缓存不存在，我们需要先创建缓存
                logger.info(f"创建新的缓存仓库: {cache_repo_path}")
                
                # 确保缓存目录存在
                os.makedirs(os.path.dirname(cache_repo_path), exist_ok=True)
                
                # 克隆到缓存目录，递归克隆所有子模块
                cache_cmd = f"git clone --recursive --depth={depth}"
                if branch:
                    cache_cmd += f" -b {branch}"
                cache_cmd += f" {repo_url} {cache_repo_path}"
                
                try:
                    # 克隆到缓存目录
                    logger.info(f"先克隆到缓存目录: {cache_repo_path}")
                    subprocess.run(cache_cmd, shell=True, check=True,
                                stdout=subprocess.PIPE if not verbose else None,
                                stderr=subprocess.PIPE if not verbose else None,
                                timeout=timeout)
                    
                    # 从缓存中复制到目标目录
                    logger.info(f"从缓存复制到目标目录: {target_dir}")
                    os.makedirs(os.path.dirname(target_dir), exist_ok=True)
                    
                    # 浅克隆仓库不支持 --local 参数，所以使用文件复制然后更新子模块
                    logger.info(f"使用直接文件复制写入目标目录")
                    
                    # 先清除目标目录
                    if os.path.exists(target_dir):
                        shutil.rmtree(target_dir)
                        
                    # 使用文件复制实现克隆
                    shutil.copytree(cache_repo_path, target_dir, symlinks=True)
                    
                    # 检查子模块状态并智能决定是否需要初始化
                    try:
                        # 切换到克隆目录
                        original_dir = os.getcwd()
                        os.chdir(target_dir)
                        
                        # 检查子模块是否已经初始化
                        if check_submodules_initialized(target_dir, verbose):
                            logger.info("缓存中的子模块已完全初始化，跳过重复初始化")
                        else:
                            # 需要初始化子模块
                            logger.info(f"初始化和更新子模块")
                            subprocess.run("git submodule init", shell=True, check=True,
                                        stdout=subprocess.PIPE if not verbose else None,
                                        stderr=subprocess.PIPE if not verbose else None)
                            subprocess.run("git submodule update", shell=True, check=True,
                                        stdout=subprocess.PIPE if not verbose else None,
                                        stderr=subprocess.PIPE if not verbose else None)
                        
                        # 返回原始目录
                        os.chdir(original_dir)
                    except Exception as e:
                        logger.warning(f"子模块更新失败，将执行递归克隆: {e}")
                        # 返回原始目录
                        if 'original_dir' in locals():
                            os.chdir(original_dir)
                        
                        # 如果子模块更新失败，清除目录并执行一次完整的网络克隆
                        if os.path.exists(target_dir):
                            shutil.rmtree(target_dir)
                        
                        # 执行递归克隆
                        clone_cmd = f"git clone --recursive {repo_url} {target_dir}"
                        subprocess.run(clone_cmd, shell=True, check=True,
                                    stdout=subprocess.PIPE if not verbose else None,
                                    stderr=subprocess.PIPE if not verbose else None,
                                    timeout=timeout)
                    
                    # 检查是否成功
                    if os.path.exists(os.path.join(target_dir, '.git')):
                        logger.info(f"成功创建缓存并克隆到: {target_dir}")
                        return True
                    else:
                        logger.warning("本地克隆失败，尝试直接克隆")
                except Exception as e:
                    logger.warning(f"创建缓存失败: {e}")
                    # 如果创建缓存失败，继续使用普通方式克隆
        
        # 如果缓存不可用或者缓存操作失败，执行普通克隆，并递归克隆子模块
        cmd = f"git clone --recursive --depth={depth}"
        if branch:
            cmd += f" -b {branch}"
        cmd += f" {repo_url} {target_dir}"
        
        logger.info(f"从 {repo_url} 直接克隆到 {target_dir}")
        
        # 执行克隆命令
        subprocess.run(cmd, shell=True, check=True,
                     stdout=subprocess.PIPE if not verbose else None,
                     stderr=subprocess.PIPE if not verbose else None,
                     timeout=timeout)
        
        # 就算使用 --recursive 参数，也显式执行子模块初始化和更新
        # 这样可以确保子模块正确初始化
        try:
            # 切换到克隆目录
            original_dir = os.getcwd()
            os.chdir(target_dir)
            
            # 检查子模块是否已经初始化
            if check_submodules_initialized(target_dir, verbose):
                logger.info("子模块已完全初始化，跳过重复初始化")
            else:
                # 更新子模块
                logger.info(f"显式初始化和更新子模块")
                subprocess.run("git submodule init", shell=True, check=True,
                            stdout=subprocess.PIPE if not verbose else None,
                            stderr=subprocess.PIPE if not verbose else None)
                subprocess.run("git submodule update", shell=True, check=True,
                            stdout=subprocess.PIPE if not verbose else None,
                            stderr=subprocess.PIPE if not verbose else None)
            
            # 返回原始目录
            os.chdir(original_dir)
        except Exception as e:
            logger.warning(f"子模块更新失败: {e}")
            # 返回原始目录
            if 'original_dir' in locals():
                os.chdir(original_dir)
                
        # 如果启用了缓存，将已克隆和初始化子模块的仓库备份到缓存
        if _cache_support and use_cache and os.path.exists(target_dir) and os.path.exists(os.path.join(target_dir, '.git')):
            try:
                cache_repo_path = get_git_cache_path(cache_dir, repo_url, branch)
                
                # 如果缓存已存在，先删除
                if os.path.exists(cache_repo_path):
                    logger.info(f"更新现有缓存: {cache_repo_path}")
                    shutil.rmtree(cache_repo_path)
                
                # 创建缓存目录的父目录
                os.makedirs(os.path.dirname(cache_repo_path), exist_ok=True)
                
                # 将已初始化子模块的仓库复制到缓存
                logger.info(f"将已初始化的仓库备份到缓存: {cache_repo_path}")
                shutil.copytree(target_dir, cache_repo_path, symlinks=True)
            except Exception as e:
                logger.warning(f"备份到缓存失败: {e}")
        
        # 检查结果
        if os.path.exists(os.path.join(target_dir, '.git')):
            logger.info(f"成功克隆仓库到 {target_dir}")
            return True
        else:
            logger.error(f"克隆失败: {target_dir} 不是Git仓库")
            return False
    except subprocess.CalledProcessError as e:
        logger.error(f"克隆Git仓库失败: {e}")
        logger.debug(f"错误输出: {e.stderr.decode() if e.stderr else 'None'}")
        return False
    except subprocess.TimeoutExpired:
        logger.error(f"克隆Git仓库超时 (>{timeout}秒)")
        return False
    except Exception as e:
        logger.error(f"克隆仓库时发生未知错误: {e}")
        return False

def init_git_submodules(repo_dir, verbose=False, timeout=180, retry=2, use_cache=True, cache_dir=None):
    """初始化并更新Git子模块，支持缓存
    
    Args:
        repo_dir (str): Git仓库目录
        verbose (bool): 是否显示详细输出 
        timeout (int): 命令超时时间(秒)
        retry (int): 失败重试次数
        use_cache (bool): 是否使用缓存
        cache_dir (str): 缓存目录路径，如为None则使用默认目录
        
    Returns:
        bool: 是否成功初始化
    """
    try:
        if not os.path.exists(os.path.join(repo_dir, '.git')):
            logger.warning(f"目录 {repo_dir} 不是Git仓库")
            return False
        
        logger.info(f"初始化Git子模块: {repo_dir}")
        
        # 检查子模块是否已经初始化
        if check_submodules_initialized(repo_dir, verbose):
            logger.info("子模块已完全初始化，无需重复初始化")
            return True
        
        # 尝试多次，因为子模块可能较多
        for attempt in range(retry + 1):
            try:
                # 初始化子模块
                init_cmd = f"cd {repo_dir} && git submodule init"
                subprocess.run(init_cmd, shell=True, check=True, 
                              stdout=subprocess.PIPE if not verbose else None, 
                              stderr=subprocess.PIPE if not verbose else None,
                              timeout=timeout)
                
                # 更新子模块
                update_cmd = f"cd {repo_dir} && git submodule update"
                subprocess.run(update_cmd, shell=True, check=True, 
                              stdout=subprocess.PIPE if not verbose else None, 
                              stderr=subprocess.PIPE if not verbose else None,
                              timeout=timeout)
                
                logger.info("成功初始化和更新Git子模块")
                return True
                
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                if attempt < retry:
                    logger.warning(f"子模块初始化失败，尝试 {attempt+1}/{retry+1}: {e}")
                    # 可能网络问题，增加超时时间
                    timeout += 60
                    time.sleep(5)
                else:
                    if isinstance(e, subprocess.CalledProcessError):
                        logger.error(f"初始化Git子模块失败: {e}")
                        logger.debug(f"错误输出: {e.stderr.decode() if e.stderr else 'None'}")
                    else:
                        logger.error(f"初始化Git子模块超时 (>{timeout}秒)")
                    return False
        
        return False
    except Exception as e:
        logger.error(f"初始化Git子模块时发生未知错误: {e}")
        return False

def try_alternate_repo(primary_url, fallback_url, target_dir, verbose=False, cache_dir=None, use_cache=True):
    """先尝试主要仓库，失败时使用备用仓库
    
    特别适合中国环境：先尝试Gitee，失败后使用GitHub
    
    Args:
        primary_url (str): 主要仓库URL (通常是Gitee)
        fallback_url (str): 备用仓库URL (通常是GitHub)
        target_dir (str): 目标目录
        verbose (bool): 是否显示详细输出
        cache_dir (str): 缓存目录，如为None则使用默认缓存目录
        use_cache (bool): 是否使用缓存
        
    Returns:
        bool: 是否成功克隆
    """
    logger.info(f"尝试从主要仓库克隆: {primary_url}")
    success = clone_git_repo(primary_url, target_dir, verbose, cache_dir=cache_dir, use_cache=use_cache)
    
    if not success:
        logger.warning(f"从主要仓库克隆失败，尝试备用仓库: {fallback_url}")
        success = clone_git_repo(fallback_url, target_dir, verbose, cache_dir=cache_dir, use_cache=use_cache)
        
        if success:
            logger.info(f"从备用仓库克隆成功: {fallback_url}")
        else:
            logger.error("所有仓库克隆尝试均失败")
            
    return success

# 测试函数
if __name__ == "__main__":
    import tempfile
    try:
        logging.basicConfig(level=logging.INFO)
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_url = "https://github.com/SpiderLabs/ModSecurity.git"
            target_dir = os.path.join(temp_dir, "ModSecurity")
            success = clone_git_repo(repo_url, target_dir, verbose=True)
            if success:
                print(f"成功克隆到 {target_dir}")
            else:
                print("克隆失败")
    except Exception as e:
        print(f"测试时出错: {e}")
