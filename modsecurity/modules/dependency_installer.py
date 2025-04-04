#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
依赖安装模块
负责安装ModSecurity所需的系统依赖
"""

import os
import sys
import subprocess
import logging
import time

# 导入相关模块
try:
    from modules.constants import DEPENDENCIES
    from modules.system_detector import detect_os
    from modules.repo_manager_ext import test_yum_repo, fix_centos_yum_mirrors
except ImportError as e:
    logging.error(f"导入模块时出错: {e}")
    sys.exit(1)

logger = logging.getLogger('modsecurity_installer')

def install_epel_repo(version="7"):
    """安装EPEL仓库以提供额外的依赖包
    
    Args:
        version (str): CentOS版本号
        
    Returns:
        bool: 是否成功安装EPEL仓库
    """
    logger.info("尝试安装EPEL仓库以提供额外的依赖包...")
    
    # 检查是否已安装EPEL
    epel_installed = False
    try:
        process = subprocess.run("yum repolist | grep -i epel", shell=True, check=True, 
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        epel_installed = True
        logger.info("EPEL仓库已安装")
        return True
    except subprocess.CalledProcessError:
        logger.info("EPEL仓库未安装，将安装")
    
    # 安装EPEL仓库
    try:
        if version == "7":
            # CentOS 7使用阿里云镜像安装EPEL
            logger.info("尝试从阿里云镜像安装CentOS 7的EPEL...")
            cmd = "yum install -y https://mirrors.aliyun.com/epel/epel-release-latest-7.noarch.rpm"
            process = subprocess.run(cmd, shell=True, check=True, 
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # 替换为国内镜像源
            subprocess.run("sed -i 's|^#baseurl=http://download.fedoraproject.org/pub/epel|baseurl=https://mirrors.aliyun.com/epel|g' /etc/yum.repos.d/epel*.repo", 
                         shell=True, check=True)
            subprocess.run("sed -i 's|^metalink|#metalink|g' /etc/yum.repos.d/epel*.repo", 
                         shell=True, check=True)
            
            logger.info("CentOS 7 EPEL仓库安装成功(阿里云镜像)")
            return True
        elif version == "8":
            # CentOS 8使用阿里云镜像安装EPEL
            logger.info("尝试从阿里云镜像安装CentOS 8的EPEL...")
            cmd = "yum install -y https://mirrors.aliyun.com/epel/epel-release-latest-8.noarch.rpm"
            process = subprocess.run(cmd, shell=True, check=True, 
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # 替换为国内镜像源
            subprocess.run("sed -i 's|^#baseurl=http://download.fedoraproject.org/pub/epel|baseurl=https://mirrors.aliyun.com/epel|g' /etc/yum.repos.d/epel*.repo", 
                         shell=True, check=True)
            subprocess.run("sed -i 's|^metalink|#metalink|g' /etc/yum.repos.d/epel*.repo", 
                         shell=True, check=True)
            
            logger.info("CentOS 8 EPEL仓库安装成功(阿里云镜像)")
            return True
        else:
            # 其他版本使用官方源
            logger.info(f"尝试安装CentOS {version}的EPEL仓库...")
            cmd = "yum install -y epel-release"
            process = subprocess.run(cmd, shell=True, check=True, 
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.info(f"CentOS {version} EPEL仓库安装成功(官方源)")
            return True
    except subprocess.CalledProcessError as e:
        logger.error(f"安装EPEL仓库失败: {e}")
        output = e.stdout.decode() if e.stdout else "" + e.stderr.decode() if e.stderr else ""
        logger.debug(f"错误输出: {output}")
        
        # 如果失败，尝试从官方源安装
        try:
            logger.warning("从阿里云安装失败，尝试官方源...")
            cmd = "yum install -y epel-release"
            process = subprocess.run(cmd, shell=True, check=True, 
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.info(f"CentOS {version} EPEL仓库安装成功(官方源)")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"安装EPEL仓库失败: {e}")
            return False
    except Exception as e:
        logger.error(f"安装EPEL仓库时发生未知错误: {e}")
        return False

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
                # RHEL
                subprocess.run("yum install -y gcc gcc-c++ make", shell=True, check=True)
                logger.warning("对于RHEL系统，可能需要手动安装更高版本的GCC以支持C++17")
                return True
    except subprocess.CalledProcessError as e:
        logger.error(f"安装GCC失败: {e}")
        return False
    except Exception as e:
        logger.error(f"安装GCC时发生未知错误: {e}")
        return False

def check_and_fix_dependency_repos(os_version):
    """检查并修复软件源配置问题
    
    专门解决CentOS 7 EOL软件源错误，自动检测和修复镜像问题
    
    Args:
        os_version (str): 操作系统版本号
        
    Returns:
        bool: 是否成功修复配置
    """
    # 主要针对CentOS/RHEL系统
    if not os.path.exists('/etc/yum.repos.d'):
        logger.info("未检测到YUM软件源目录，跳过修复")
        return True
    
    logger.info("检查YUM软件源配置...")
    
    # 测试软件源是否可用
    if test_yum_repo():
        logger.info("软件源配置正常，无需修复")
        return True
    
    logger.warning("检测到软件源配置问题，尝试修复...")
    return fix_centos_yum_mirrors()

def init_repo_cache():
    """初始化软件源缓存
    
    Returns:
        bool: 是否成功初始化
    """
    os_type, _ = detect_os()
    
    try:
        if os_type == 'rhel':
            logger.info("清理并重建YUM缓存...")
            subprocess.run("yum clean all", shell=True, check=True)
            subprocess.run("yum makecache", shell=True, check=True)
        elif os_type == 'debian':
            logger.info("更新APT缓存...")
            subprocess.run("apt update", shell=True, check=True)
        
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"初始化软件源缓存失败: {e}")
        return False
    except Exception as e:
        logger.error(f"初始化软件源缓存时发生未知错误: {e}")
        return False

# 保持向后兼容
init_repos_cache = init_repo_cache

def clean_yum_transactions():
    """清理YUM未完成的事务
    
    Returns:
        bool: 是否成功清理
    """
    logger.info("检查并清理YUM未完成的事务...")
    
    try:
        # 安装yum-utils包
        logger.info("安装 yum-utils 工具包...")
        subprocess.run("yum install -y yum-utils", shell=True, check=False, 
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # 清理YUM缓存和相关环境 - 非常强力的清理方式
        cleanup_commands = [
            "yum-complete-transaction --cleanup-only",
            "yum history new",  # 创建新的历史事务
            "yum clean all",     # 清理所有缓存
            "rm -f /var/lib/rpm/__db*",  # 清除RPM数据库锁
            "rpm --rebuilddb",   # 重建 RPM数据库
            "yum makecache"      # 重建缓存
        ]
        
        for cmd in cleanup_commands:
            logger.info(f"运行: {cmd}")
            try:
                subprocess.run(cmd, shell=True, check=False,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
            except Exception as subcmd_err:
                logger.warning(f"运行{cmd}时发生错误: {subcmd_err}")
                # 继续尝试其他命令，不返回错误
        
        return True
    except Exception as e:
        logger.warning(f"清理YUM事务时发生错误: {e}")
        return False

def install_single_package(package_name, os_type="rhel"):
    """尝试安装单个软件包
    
    Args:
        package_name (str): 要安装的包名称
        os_type (str): 操作系统类型 ('rhel' 或 'debian')
        
    Returns:
        bool: 是否成功安装
    """
    try:
        if os_type == 'rhel':
            cmd = f"yum install -y --skip-broken {package_name}"
        else:
            cmd = f"apt-get install -y {package_name}"
            
        subprocess.run(cmd, shell=True, check=True,
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        return True
    except Exception as e:
        logger.warning(f"安装{package_name}失败: {e}")
        return False

def install_system_dependencies():
    """安装ModSecurity所需的系统依赖
    
    Returns:
        bool: 是否成功安装所有依赖
    """
    os_type, os_version = detect_os()
    
    # 先检查和修复软件源配置
    if os_type == 'rhel':
        logger.info("修复软件源配置...")
        fix_centos_yum_mirrors()
        # 无论成功与否都继续
    
    # 初始化软件源缓存
    init_repo_cache()
    
    # 对于CentOS/RHEL，强制清理事务
    if os_type == 'rhel':
        logger.info("强制清理YUM状态...")
        clean_yum_transactions()
    
    # 对于CentOS/RHEL，安装EPEL仓库
    if os_type == 'rhel':
        install_epel_repo(os_version) # 即使失败也继续
        
        # 检查GCC版本，如果过低则安装新版本
        # 尤其是CentOS 7上默认GCC 4.8.5不支持C++11/14特性
        logger.info("检查GCC版本...")
        try:
            gcc_ver_cmd = "gcc --version | head -n1 | awk '{print $3}'"
            gcc_version = subprocess.run(gcc_ver_cmd, shell=True, check=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()
            
            logger.info(f"检测到GCC版本: {gcc_version}")
            # 如果是CentOS 7或者GCC版本过低，安装新版本
            if os_version.startswith('7') or gcc_version.startswith('4.'):
                logger.warning(f"GCC版本 {gcc_version} 太旧，不支持现代C++特性")
                logger.info("安装新版本GCC编译器...")
                install_newer_gcc('rhel')
            else:
                logger.info(f"GCC版本 {gcc_version} 已满足要求")
        except Exception as e:
            logger.warning(f"检查GCC版本失败: {e}，将安装新版本")
            install_newer_gcc('rhel')
    
    # 使用强化的包安装方法
    if os_type in DEPENDENCIES:
        deps = DEPENDENCIES.get(os_type, [])
        
        # 采用逻个安装策略，避免YUM事务问题
        if os_type == 'rhel':
            logger.info("采用逐个安装策略，最大限度避免YUM事务冲突...")
            
            # 先检查已有依赖
            success_count = 0
            total_deps = len(deps)
            
            for pkg in deps:
                # 检查包是否已安装
                check_cmd = f"rpm -q {pkg.split()[0]} 2>/dev/null || echo 'not installed'"
                result = subprocess.run(check_cmd, shell=True, stdout=subprocess.PIPE).stdout.decode('utf-8').strip()
                
                if 'not installed' in result:
                    logger.info(f"安装依赖: {pkg}")
                    if install_single_package(pkg, os_type):
                        success_count += 1
                    # 不要中断安装过程，继续下一个包
                else:
                    logger.info(f"包 {pkg} 已安装，跳过")
                    success_count += 1
                    
                # 在每个包安装后清理缓存
                subprocess.run("yum clean all", shell=True, check=False, 
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # 最后一次尝试批量安装任何尚未安装的包
            logger.info("最后一次检查所有依赖包...")
            try:
                # 使用--skip-broken的可能性大一些
                deps_str = " ".join(deps)
                cmd = f"yum install -y --skip-broken {deps_str}"
                subprocess.run(cmd, shell=True, check=False,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
            except Exception as final_e:
                logger.warning(f"最终依赖检查时发生错误: {final_e}")
                
            success_rate = (success_count / total_deps) * 100
            logger.info(f"依赖安装既成: {success_count}/{total_deps} ({success_rate:.1f}%)")
            
            # 只要大部分关键包安装成功就认为安装成功
            return success_count >= (total_deps * 0.8)
            
        elif os_type == 'debian':
            logger.info(f"安装Debian/Ubuntu依赖...")
            try:
                deps_str = " ".join(deps)
                cmd = f"apt-get update && apt-get install -y {deps_str}"
                subprocess.run(cmd, shell=True, check=True)
                logger.info("依赖安装成功")
                return True
            except Exception as e:
                logger.error(f"安装依赖失败: {e}")
                return False
            return False
    else:
        logger.warning(f"不支持的系统类型: {os_type}，跳过依赖安装")
        return False

# 如果直接运行此脚本，则执行测试
if __name__ == "__main__":
    try:
        from modules.constants import setup_logger
    except ImportError as e:
        print(f"导入模块时出错: {e}")
        sys.exit(1)
    
    # 设置日志
    logger = setup_logger()
    
    # 测试系统依赖安装
    os_type, os_version = detect_os()
    logger.info(f"检测到系统: {os_type} {os_version}")
    
    # 测试软件源修复
    if os_type == 'rhel':
        if check_and_fix_dependency_repos(os_version):
            logger.info("软件源检查/修复成功")
        else:
            logger.error("软件源修复失败")
    
    # 测试依赖安装
    if install_system_dependencies():
        logger.info("系统依赖安装成功")
    else:
        logger.error("系统依赖安装失败")
