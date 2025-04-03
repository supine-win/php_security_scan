#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ModSecurity安装主脚本
整合所有模块，提供完整的安装流程
"""

import os
import sys
import logging
import argparse
import tempfile
import time
import shutil
import subprocess
from pathlib import Path

# 导入模块
try:
    from modules.constants import setup_logger, WORK_DIR
    from modules.system_detector import detect_os, system_info_summary
    from modules.repo_manager_ext import check_and_fix_repo_config
    from modules.dependency_installer import install_system_dependencies, init_repo_cache
    from modules.modsecurity_compiler import download_and_build_modsecurity
    from modules.nginx_integrator import install_nginx_modsecurity
    from modules.config_manager import configure_modsecurity
except ImportError as e:
    print(f"错误: 无法导入必要的模块: {e}")
    print("请确认您在正确的目录下运行此脚本，并且modules目录存在。")
    sys.exit(1)

def check_root_privileges():
    """检查是否具有root权限

    Returns:
        bool: 是否具有root权限
    """
    return os.geteuid() == 0

def restart_nginx():
    """重启Nginx服务

    Returns:
        bool: 是否成功重启
    """
    logger = logging.getLogger('modsecurity_installer')
    
    try:
        # 尝试直接使用systemctl重启
        logger.info("尝试重启Nginx服务...")
        subprocess.run("systemctl restart nginx", shell=True, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # 如果失败，尝试使用service命令
        if subprocess.run("systemctl status nginx", shell=True, check=False).returncode != 0:
            logger.info("使用service命令重启Nginx...")
            subprocess.run("service nginx restart", shell=True, check=False)
        
        # 检查Nginx是否正在运行
        time.sleep(2)  # 等待服务启动
        if subprocess.run("pgrep -x nginx", shell=True, check=False).returncode == 0:
            logger.info("Nginx服务已成功重启")
            return True
        else:
            logger.warning("Nginx服务可能未成功重启，请手动检查")
            return False
    except Exception as e:
        logger.error(f"重启Nginx服务失败: {e}")
        return False

def parse_arguments():
    """解析命令行参数

    Returns:
        argparse.Namespace: 解析后的参数
    """
    parser = argparse.ArgumentParser(description='ModSecurity安装脚本')
    parser.add_argument('--no-check-repo', action='store_true', help='跳过软件源检查')
    parser.add_argument('--no-install-deps', action='store_true', help='跳过依赖安装')
    parser.add_argument('--no-restart', '-n', action='store_true', help='安装后不重启Nginx')
    parser.add_argument('--verbose', '-v', action='store_true', help='输出详细日志')
    parser.add_argument('--force', '-f', action='store_true', help='强制安装，跳过所有确认')
    parser.add_argument('--fix-repo', '-r', action='store_true', help='自动修复软件源问题（针对CentOS EOL版本）')
    parser.add_argument('--work-dir', type=str, default=WORK_DIR, help=f'工作目录，默认为{WORK_DIR}')
    parser.add_argument('--log-file', type=str, default=None, help='日志文件路径')
    
    return parser.parse_args()

def main():
    """主函数，执行安装流程"""
    # 解析命令行参数
    args = parse_arguments()
    
    # 设置日志
    logger = setup_logger(args.log_file)
    
    # 检查权限
    if not check_root_privileges():
        logger.error("此脚本需要root权限运行，请使用sudo或以root身份运行")
        return 1
    
    # 输出banner
    logger.info("""
    ========================================
        ModSecurity + Nginx 安装脚本
    ========================================
    """)
    
    # 检测系统信息
    logger.info("正在检测系统信息...")
    sys_info = system_info_summary()
    logger.info(f"系统类型: {sys_info['os_type']}")
    logger.info(f"系统版本: {sys_info['os_version']}")
    logger.info(f"宝塔面板: {'是' if sys_info['is_bt_panel'] else '否'}")
    
    # 检查是否支持安装
    if sys_info['os_type'] == 'unknown':
        logger.error("不支持的系统类型，只支持CentOS/RHEL和Debian/Ubuntu")
        return 1
    
    # 检查Nginx
    if not sys_info['nginx_installed']:
        logger.error("未检测到Nginx安装，无法继续")
        return 1
    
    logger.info(f"Nginx版本: {sys_info['nginx_version']}")
    logger.info(f"Nginx路径: {sys_info['nginx_path']}")
    
    # 检查GCC版本
    if not sys_info['gcc_supports_cpp17']:
        logger.warning("当前GCC版本不支持C++17，ModSecurity可能无法编译")
        logger.warning("将尝试安装或使用更高版本的GCC")
    
    # 检查和修复软件源配置
    if args.fix_repo:
        # 强制执行软件源修复
        logger.info("根据命令行参数，强制修复软件源配置...")
        if sys_info['os_type'] == 'rhel':
            from modules.repo_manager_ext import fix_centos_yum_mirrors
            if not fix_centos_yum_mirrors():
                logger.warning("软件源强制修复失败，将尝试继续安装")
        else:
            logger.warning("当前系统不是CentOS/RHEL，无法修复软件源")
    elif not args.no_check_repo:
        logger.info("检查软件源配置...")
        if sys_info['os_type'] == 'rhel' and (sys_info['is_eol'] or sys_info['os_version'] == '7'):
            logger.info(f"检测到CentOS/RHEL {sys_info['os_version']} EOL版本，将使用特殊配置")
            if not check_and_fix_repo_config(sys_info['os_version']):
                logger.warning("软件源配置问题无法自动修复，可能会影响依赖安装")
        else:
            logger.info("非EOL版本，跳过软件源特殊配置")
    else:
        logger.info("跳过软件源检查")
    
    # 确保工作目录存在
    work_dir = args.work_dir
    os.makedirs(work_dir, exist_ok=True)
    logger.info(f"使用工作目录: {work_dir}")
    
    # 安装系统依赖
    if not args.no_install_deps:
        logger.info("安装系统依赖...")
        if not install_system_dependencies():
            logger.error("安装系统依赖失败，无法继续")
            return 1
    else:
        logger.info("跳过依赖安装")
    
    # 下载和构建ModSecurity
    logger.info("下载和构建ModSecurity...")
    if not download_and_build_modsecurity(work_dir, args.verbose):
        logger.error("ModSecurity构建失败，无法继续")
        return 1
    
    # 安装ModSecurity-Nginx连接器
    logger.info("安装ModSecurity-Nginx连接器...")
    modsec_dir = os.path.join(work_dir, "ModSecurity")
    if not install_nginx_modsecurity(work_dir, modsec_dir, args.verbose):
        logger.error("ModSecurity-Nginx连接器安装失败，无法继续")
        return 1
    
    # 配置ModSecurity
    logger.info("配置ModSecurity...")
    if not configure_modsecurity(work_dir):
        logger.error("ModSecurity配置失败，无法继续")
        return 1
    
    # 重启Nginx
    if not args.no_restart:
        logger.info("重启Nginx服务...")
        if not restart_nginx():
            logger.warning("Nginx重启可能不成功，请手动检查")
    else:
        logger.info("跳过重启Nginx")
        logger.info("请在完成后手动重启Nginx: systemctl restart nginx")
    
    # 安装完成
    logger.info("""
    ========================================
        ModSecurity 安装成功!
    ========================================
    
    默认规则已配置，包括:
    - SQL注入防护
    - XSS防护
    - 命令注入防护
    - 文件包含防护
    - PHP安全规则
    
    配置文件位置:
    - 主配置: /etc/nginx/modsec/main.conf
    - 规则目录: /etc/nginx/modsec/rules/
    
    如果使用宝塔面板，配置文件位于:
    - 主配置: /www/server/nginx/conf/modsec/main.conf
    - 规则目录: /www/server/nginx/conf/modsec/rules/
    
    日志文件:
    - 调试日志: /var/log/modsec_debug.log
    - 审计日志: /var/log/modsec_audit.log
    
    请根据需要调整配置和规则。
    """)
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger = logging.getLogger('modsecurity_installer')
        logger.warning("安装已被用户中断")
        sys.exit(1)
    except Exception as e:
        logger = logging.getLogger('modsecurity_installer')
        logger.exception(f"安装过程中发生未处理的异常: {e}")
        sys.exit(1)
