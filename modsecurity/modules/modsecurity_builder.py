#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ModSecurity构建模块
负责构建和编译ModSecurity核心库
"""

import os
import subprocess
import logging
import shutil
import sys
import time

# 导入相关模块
try:
    from modules.system_detector import check_gcc_version
    from modules.git_manager import clone_git_repo, init_git_submodules, try_alternate_repo
    from modules.constants import MODSEC_VERSION, GIT_REPOS
except ImportError as e:
    logging.error(f"导入模块时出错: {e}")
    sys.exit(1)

logger = logging.getLogger('modsecurity_installer')

def build_modsecurity(build_dir, verbose=False, max_retries=2):
    """构建ModSecurity核心库
    
    Args:
        build_dir (str): 构建目录
        verbose (bool): 是否输出详细信息
        max_retries (int): 最大重试次数
        
    Returns:
        bool: 是否成功构建
    """
    try:
        # 检查目录是否存在
        if not os.path.exists(build_dir):
            logger.error(f"构建目录不存在: {build_dir}")
            return False
        
        # 切换到构建目录
        os.chdir(build_dir)
        
        # 检查编译器版本及 CentOS 7 环境
        is_centos7 = False
        devtoolset_available = False
        maxminddb_updated = False
        
        # 检查是否是 CentOS 7 环境
        try:
            if os.path.exists('/etc/centos-release'):
                with open('/etc/centos-release', 'r') as f:
                    release_info = f.read().strip().lower()
                    if 'centos' in release_info and '7.' in release_info:
                        is_centos7 = True
                        logger.info("检测到 CentOS 7 环境")
            
            # 检查是否安装了 devtoolset-7
            if is_centos7 and os.path.exists('/opt/rh/devtoolset-7/root/usr/bin/gcc'):
                devtoolset_available = True
                logger.info("检测到 devtoolset-7 可用，将使用 GCC 7 进行编译")
        except Exception as e:
            logger.warning(f"检测系统环境时出错: {e}")
        
        # 如果是 CentOS 7 但没有 devtoolset-7，尝试安装
        if is_centos7 and not devtoolset_available:
            try:
                logger.warning("在 CentOS 7 上需要 GCC 7 及以上版本编译 ModSecurity")
                logger.info("尝试安装 devtoolset-7...")
                # 安装 SCL 和 devtoolset-7
                subprocess.run("yum install -y centos-release-scl", shell=True, check=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                subprocess.run("yum install -y devtoolset-7-gcc devtoolset-7-gcc-c++", shell=True, check=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                if os.path.exists('/opt/rh/devtoolset-7/root/usr/bin/gcc'):
                    devtoolset_available = True
                    logger.info("成功安装 devtoolset-7")
                else:
                    logger.warning("无法安装 devtoolset-7，编译可能会失败")
            except Exception as e:
                logger.error(f"安装 devtoolset-7 失败: {e}")
                
        # 在 CentOS 7 环境下升级 libmaxminddb 库
        if is_centos7:
            try:
                logger.info("在CentOS 7上升级libmaxminddb库以解决兼容性问题...")
                
                # 查看当前安装的libmaxminddb版本
                version_check = subprocess.run("rpm -qa | grep libmaxminddb", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                libmaxmind_current = version_check.stdout.decode('utf-8').strip()
                if libmaxmind_current:
                    logger.info(f"当前安装的libmaxminddb版本: {libmaxmind_current}")
                
                # 安装EPEL仓库，它提供更新的libmaxminddb
                logger.info("安装EPEL仓库...")
                subprocess.run("yum install -y epel-release", shell=True, check=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # 现在安装或更新libmaxminddb
                logger.info("安装/更新libmaxminddb...")
                subprocess.run("yum install -y libmaxminddb libmaxminddb-devel", shell=True, check=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # 再次检查安装的版本
                version_check = subprocess.run("rpm -qa | grep libmaxminddb", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                libmaxmind_new = version_check.stdout.decode('utf-8').strip()
                
                if libmaxmind_new and (not libmaxmind_current or libmaxmind_new != libmaxmind_current):
                    logger.info(f"成功升级libmaxminddb至: {libmaxmind_new}")
                    maxminddb_updated = True
                else:
                    if libmaxmind_new == libmaxmind_current:
                        logger.info("当前已经安装最新版本的libmaxminddb")
                        maxminddb_updated = True
                    else:
                        logger.warning("无法安装或更新libmaxminddb库")
                
            except Exception as e:
                logger.warning(f"升级libmaxminddb库失败: {e}")
        
        # 标准 GCC 版本检查
        gcc_version = check_gcc_version()
        if gcc_version:
            logger.info(f"GCC版本: {gcc_version}")
        else:
            logger.warning("无法检测GCC版本，构建可能会失败")
        
        # 检查是否已经编译过
        if os.path.exists(os.path.join(build_dir, 'src', '.libs', 'libmodsecurity.so')):
            logger.info("ModSecurity已经构建完成，跳过构建步骤")
            return True
            
        logger.info("开始构建ModSecurity...")
        
        # 执行构建步骤
        for attempt in range(max_retries + 1):
            try:
                # 步骤1: 生成构建系统
                logger.info("步骤1: 生成构建系统")
                
                # 检测可用的构建系统脚本
                build_scripts = [
                    "./autogen.sh",  # 最常用的方式
                    "./build.sh",    # 有些仓库使用build.sh
                    "./configure.ac" # 如果存在configure.ac，可以手动生成
                ]
                
                build_script = None
                for script in build_scripts:
                    if os.path.exists(script.replace("./", "")):
                        build_script = script
                        break
                
                if not build_script and os.path.exists("configure"):
                    logger.info("找到预配置的configure脚本，跳过构建系统生成步骤")
                    # 如果已经有configure脚本，可以直接跳过这一步骤
                    pass
                elif build_script == "./autogen.sh" or build_script == "./build.sh":
                    logger.info(f"使用 {build_script} 生成构建系统")
                    cmd = build_script
                    subprocess.run(cmd, shell=True, check=True,
                                  stdout=subprocess.PIPE if not verbose else None,
                                  stderr=subprocess.PIPE if not verbose else None)
                elif build_script == "./configure.ac":
                    logger.info("使用autoconf/automake生成构建系统")
                    # 如果只有configure.ac，需要手动运行autoconf
                    cmds = [
                        "aclocal",
                        "autoconf",
                        "automake --add-missing"
                    ]
                    for cmd in cmds:
                        try:
                            subprocess.run(cmd, shell=True, check=True,
                                          stdout=subprocess.PIPE if not verbose else None,
                                          stderr=subprocess.PIPE if not verbose else None)
                        except subprocess.CalledProcessError:
                            logger.warning(f"运行 {cmd} 失败，尝试继续")
                else:
                    logger.warning("未找到标准构建脚本，尝试直接运行configure")
                    # 如果无法找到构建脚本，我们尝试直接运行configure
                    if not os.path.exists("configure"):
                        logger.error("无法找到configure脚本，尝试git子模块方式")
                        # 尝试一个备用方案 - 用git子模块编译
                        try:
                            subprocess.run("git submodule init && git submodule update", shell=True, check=True,
                                          stdout=subprocess.PIPE if not verbose else None,
                                          stderr=subprocess.PIPE if not verbose else None)
                            if os.path.exists("./bindings/autoconf/configure.ac"):
                                os.chdir("./bindings/autoconf")
                                subprocess.run("aclocal && autoconf && automake --add-missing", shell=True, check=True,
                                              stdout=subprocess.PIPE if not verbose else None,
                                              stderr=subprocess.PIPE if not verbose else None)
                                os.chdir(build_dir)  # 返回原工作目录
                            else:
                                logger.error("构建系统初始化失败，无法找到构建脚本")
                                return False
                        except subprocess.CalledProcessError as e:
                            logger.error(f"初始化git子模块失败: {e}")
                            return False
                
                # 步骤2: 配置
                logger.info("步骤2: 配置构建选项")
                
                # 在CentOS 7环境下使用devtoolset-7
                if is_centos7:
                    # 如果成功升级了libmaxminddb，则不需要特殊编译选项
                    if maxminddb_updated:
                        if devtoolset_available:
                            logger.info("在CentOS 7环境下使用devtoolset-7进行编译，已升级libmaxminddb库")
                            configure_cmd = "scl enable devtoolset-7 -- ./configure"
                        else:
                            logger.info("使用已升级的libmaxminddb库进行编译")
                            configure_cmd = "./configure"
                    # 如果升级失败，则使用-fpermissive编译选项作为备选方案
                    else:
                        if devtoolset_available:
                            logger.info("在CentOS 7环境下使用devtoolset-7进行编译，并添加-fpermissive编译选项作为备选方案")
                            configure_cmd = "scl enable devtoolset-7 -- ./configure CXXFLAGS=\"-fpermissive\" CFLAGS=\"-fpermissive\""
                        else:
                            logger.info("在CentOS 7环境下添加-fpermissive编译选项作为备选方案")
                            configure_cmd = "./configure CXXFLAGS=\"-fpermissive\" CFLAGS=\"-fpermissive\""
                else:
                    configure_cmd = "./configure"
                
                logger.info(f"运行配置命令: {configure_cmd}")
                configure_process = subprocess.run(configure_cmd, shell=True, check=True, executable='/bin/bash',
                                                 stdout=subprocess.PIPE if not verbose else None,
                                                 stderr=subprocess.PIPE if not verbose else None)
                
                # 步骤3: 编译
                logger.info("步骤3: 编译ModSecurity")
                
                # 在CentOS 7环境下使用devtoolset-7进行编译
                if is_centos7 and devtoolset_available:
                    make_cmd = "scl enable devtoolset-7 -- make -j$(nproc)"
                else:
                    make_cmd = "make -j$(nproc)"
                    
                logger.info(f"运行编译命令: {make_cmd}")
                make_process = subprocess.run(make_cmd, shell=True, check=True, executable='/bin/bash',
                                           stdout=subprocess.PIPE if not verbose else None,
                                           stderr=subprocess.PIPE if not verbose else None)
                
                # 检查编译结果
                if os.path.exists(os.path.join(build_dir, 'src', '.libs', 'libmodsecurity.so')):
                    logger.info("ModSecurity成功编译")
                    return True
                else:
                    logger.warning("编译过程完成，但未找到libmodsecurity.so文件")
                    if attempt < max_retries:
                        logger.info(f"尝试重新编译 (尝试 {attempt+1}/{max_retries+1})")
                        # 清理构建文件
                        if is_centos7 and devtoolset_available:
                            clean_cmd = "scl enable devtoolset-7 -- make clean"
                        else:
                            clean_cmd = "make clean"
                            
                        logger.info(f"运行清理命令: {clean_cmd}")
                        subprocess.run(clean_cmd, shell=True, check=False, executable='/bin/bash')
                        time.sleep(2)
                    else:
                        logger.error("所有编译尝试失败")
                        return False
                
            except subprocess.CalledProcessError as e:
                logger.error(f"构建ModSecurity时出错: {e}")
                if e.stderr:
                    logger.debug(f"错误输出: {e.stderr.decode()}")
                
                if attempt < max_retries:
                    logger.info(f"尝试重新构建 (尝试 {attempt+1}/{max_retries+1})")
                    # 尝试清理并重新开始
                    subprocess.run("make clean", shell=True, check=False)
                    time.sleep(2)
                else:
                    logger.error("所有构建尝试失败")
                    return False
        
        return False
        
    except Exception as e:
        logger.error(f"构建ModSecurity时发生未知错误: {e}")
        return False


def download_and_build_modsecurity(build_dir, verbose=False, use_gitee=True, use_cache=True, cache_dir=None):
    """下载并构建ModSecurity
    
    Args:
        build_dir (str): 构建目录
        verbose (bool): 是否输出详细信息
        use_gitee (bool): 是否使用Gitee仓库（适合中国网络环境）
        use_cache (bool): 是否使用缓存
        cache_dir (str): 缓存目录路径，如为None则使用默认目录
        
    Returns:
        bool: 是否成功下载和构建
    """
    try:
        # 确保构建目录存在
        if not os.path.exists(build_dir):
            os.makedirs(build_dir)
        
        # ModSecurity目标目录
        modsec_dir = os.path.join(build_dir, "ModSecurity")
        
        # 确定要使用的存储库源
        repo_source = "gitee" if use_gitee else "github"
        
        # 尝试从主仓库克隆
        logger.info(f"尝试从{repo_source}克隆ModSecurity...")
        main_repo_url = GIT_REPOS[repo_source]["modsecurity"]
        fallback_repo_url = GIT_REPOS["github" if use_gitee else "gitee"]["modsecurity"]
        
        if not try_alternate_repo(main_repo_url, fallback_repo_url, modsec_dir, verbose, 
                           cache_dir=cache_dir, use_cache=use_cache):
            logger.error("无法克隆ModSecurity仓库，构建失败")
            return False
        
        # 初始化子模块
        logger.info("初始化ModSecurity子模块...")
        if not init_git_submodules(modsec_dir, verbose=verbose, cache_dir=cache_dir, use_cache=use_cache):
            logger.warning("无法初始化ModSecurity子模块，尝试继续构建")
        
        # 构建ModSecurity
        logger.info("开始构建ModSecurity...")
        if not build_modsecurity(modsec_dir, verbose):
            logger.error("ModSecurity构建失败")
            return False
        
        logger.info("ModSecurity下载并构建成功")
        return True
    except Exception as e:
        logger.error(f"下载并构建ModSecurity时发生未知错误: {e}")
        return False


# 测试函数
if __name__ == "__main__":
    import tempfile
    try:
        from modules.constants import setup_logger
    except ImportError as e:
        logging.error(f"导入模块时出错: {e}")
        sys.exit(1)

    # 设置日志
    logger = setup_logger(verbose=True)
    
    # 测试目录
    with tempfile.TemporaryDirectory() as temp_dir:
        logger.info(f"使用临时目录进行测试: {temp_dir}")
        
        # 测试下载和构建
        result = download_and_build_modsecurity(temp_dir, verbose=True, use_gitee=True)
        logger.info(f"ModSecurity下载和构建结果: {'成功' if result else '失败'}")
