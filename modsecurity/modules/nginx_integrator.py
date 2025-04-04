#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nginx集成模块
负责下载、配置和构建ModSecurity-Nginx连接器
"""

import os
import re
import shutil
import subprocess
import logging
import sys
import time
import tempfile
from pathlib import Path

# 导入相关模块
try:
    from modules.constants import MODSEC_VERSION, MODSEC_CONNECTOR_VERSION, MODSEC_CONNECTOR_URL
    from modules.system_detector import get_nginx_info, detect_bt_panel
except ImportError as e:
    logging.error(f"导入模块时出错: {e}")
    sys.exit(1)

logger = logging.getLogger('modsecurity_installer')

def download_connector(build_dir):
    """下载ModSecurity-Nginx连接器
    
    Args:
        build_dir (str): 构建目录
        
    Returns:
        str: 连接器目录路径，失败返回空字符串
    """
    # 创建构建目录
    if not os.path.exists(build_dir):
        os.makedirs(build_dir)
    
    # 连接器文件名
    connector_name = f"ModSecurity-nginx-v{MODSEC_CONNECTOR_VERSION}.tar.gz"
    connector_path = os.path.join(build_dir, connector_name)
    
    # 如果文件已存在，不需要下载
    if os.path.exists(connector_path):
        logger.info(f"连接器已下载: {connector_path}")
    else:
        # 定义下载URL优先级列表
        download_urls = [
            # 首选Gitee镜像
            MODSEC_CONNECTOR_GITEE_URL,
            # 备用GitHub地址
            MODSEC_CONNECTOR_GITHUB_URL
        ]
        
        # 依次尝试每个URL
        download_success = False
        for url in download_urls:
            try:
                logger.info(f"尝试从 {url} 下载连接器...")
                cmd = f"curl -L --connect-timeout 30 --retry 3 -o {connector_path} {url}"
                subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                download_success = True
                logger.info(f"下载连接器成功: {url}")
                break
            except subprocess.CalledProcessError as e:
                logger.warning(f"从 {url} 下载连接器失败: {e}，尝试下一个URL")
                continue
        
        # 如果所有URL都失败了
        if not download_success:
            logger.error(f"从所有源下载连接器均失败")
            return ""
    
    # 解压连接器
    connector_dir = os.path.join(build_dir, f"ModSecurity-nginx-{MODSEC_CONNECTOR_VERSION}")
    if os.path.exists(connector_dir):
        logger.info(f"连接器已解压: {connector_dir}")
        return connector_dir
    
    # 验证下载文件
    if not os.path.exists(connector_path) or os.path.getsize(connector_path) == 0:
        logger.error(f"下载的文件无效或不存在: {connector_path}")
        return ""
        
    try:
        # 在解压前验证tar文件
        logger.info(f"验证tar文件完整性: {connector_path}")
        verify_cmd = f"tar -tf {connector_path} > /dev/null"
        try:
            subprocess.run(verify_cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            logger.error(f"文件损坏或不是有效的tar归档文件: {e}")
            # 删除损坏的文件
            os.remove(connector_path)
            return ""
        
        logger.info(f"解压连接器到: {build_dir}")
        # 使用verbose模式后重定向到文件，以便排错
        cmd = f"tar -xvzf {connector_path} -C {build_dir} > {build_dir}/extract.log 2>&1"
        subprocess.run(cmd, shell=True, check=True)
        
        # 输出解压结果
        logger.info(f"连接器解压输出:")
        try:
            with open(f"{build_dir}/extract.log", "r") as f:
                extract_output = f.read()
                logger.info(extract_output)
        except Exception as e:
            logger.warning(f"无法读取解压日志: {e}")
        
        # 验证目录存在
        if os.path.exists(connector_dir):
            # 验证目录内容
            files_in_dir = os.listdir(connector_dir)
            if files_in_dir:
                logger.info(f"连接器解压成功: {connector_dir}, 文件数: {len(files_in_dir)}")
                return connector_dir
            else:
                logger.error(f"连接器解压后目录为空: {connector_dir}")
                return ""
        else:
            # 尝试检查目录是否使用了不同的命名格式
            potential_dirs = [f for f in os.listdir(build_dir) if os.path.isdir(os.path.join(build_dir, f)) and 'modsecurity' in f.lower() and 'nginx' in f.lower()]
            
            if potential_dirs:
                alt_dir = os.path.join(build_dir, potential_dirs[0])
                logger.warning(f"找到替代目录: {alt_dir}，使用该目录代替预期的 {connector_dir}")
                return alt_dir
            else:
                logger.error(f"连接器解压后目录不存在: {connector_dir}")
                # 列出所有解压出的目录信息以便调试
                logger.info(f"build_dir中的内容: {os.listdir(build_dir)}")
                return ""
    except subprocess.CalledProcessError as e:
        logger.error(f"解压连接器失败: {e}")
        return ""
    except Exception as e:
        logger.error(f"处理连接器时发生未知错误: {e}")
        return ""

def get_nginx_compile_options(nginx_binary):
    """获取Nginx编译选项
    
    Args:
        nginx_binary (str): Nginx二进制文件路径
        
    Returns:
        dict: 编译选项字典
    """
    options = {}
    
    if not os.path.exists(nginx_binary):
        logger.error(f"Nginx二进制文件不存在: {nginx_binary}")
        return options
    
    try:
        # 获取Nginx版本和编译选项
        cmd = f"{nginx_binary} -V"
        process = subprocess.run(cmd, shell=True, check=True, 
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                              universal_newlines=True)
        
        # Nginx将版本信息输出到stderr
        output = process.stderr if process.stderr else process.stdout
        
        # 提取配置参数
        config_line = re.search(r'configure arguments:\s*(.*)', output)
        if config_line:
            config_args = config_line.group(1)
            
            # 解析参数
            for arg in config_args.split(' --'):
                arg = arg.strip()
                if not arg:
                    continue
                
                # 处理无值参数
                if '=' not in arg:
                    options[arg] = True
                    continue
                
                # 处理有值参数
                key, value = arg.split('=', 1)
                options[key] = value
            
            logger.info(f"成功提取Nginx编译选项: {len(options)}个选项")
            return options
        else:
            logger.warning("无法提取Nginx编译选项")
            return {}
    except subprocess.CalledProcessError as e:
        logger.error(f"获取Nginx编译选项失败: {e}")
        return {}

def build_nginx_module(build_dir, connector_dir, modsec_dir, verbose=False):
    """构建Nginx模块
    
    Args:
        build_dir (str): 构建目录
        connector_dir (str): 连接器目录
        modsec_dir (str): ModSecurity目录
        verbose (bool): 是否输出详细信息
        
    Returns:
        bool: 是否成功构建
    """
    # 检查Nginx安装
    is_installed, nginx_version, nginx_path = get_nginx_info()
    
    if not is_installed:
        logger.error("未检测到Nginx安装，无法构建模块")
        return False
    
    logger.info(f"检测到Nginx: 版本{nginx_version}, 路径{nginx_path}")
    
    # 获取Nginx编译选项
    options = get_nginx_compile_options(nginx_path)
    if not options:
        logger.error("获取Nginx编译选项失败，无法构建模块")
        return False
    
    # 检查是否为宝塔面板环境
    is_bt = detect_bt_panel()
    
    # 检查是否已经安装了动态模块支持
    has_dynamic_modules = 'with-compat' in options or is_bt
    
    # 如果没有动态模块支持，需要重新编译Nginx
    if not has_dynamic_modules:
        logger.warning("Nginx未编译支持动态模块，需要重新编译Nginx")
        logger.warning("请确保Nginx编译时包含了--with-compat选项")
        
        # 警告用户
        logger.warning("=== 注意 ===")
        logger.warning("当前Nginx不支持动态模块，需要重新编译。这可能会导致Nginx服务中断。")
        logger.warning("如果这是生产环境，建议先测试在开发环境中执行此操作。")
        logger.warning("建议在继续之前备份您的Nginx配置和二进制文件。")
        
        # 提示用户可能需要重新安装Nginx
        logger.info("您可以考虑卸载当前Nginx并重新安装带有动态模块支持的版本")
        logger.info("或者，您可以在不同目录编译一个支持动态模块的Nginx版本")
        
        return False
    
    # 获取Nginx源码
    nginx_src_dir = None
    
    # 对于宝塔面板，源码通常位于特定目录
    if is_bt:
        nginx_src_dir = "/www/server/nginx/src"
        if not os.path.exists(nginx_src_dir):
            logger.warning("宝塔面板Nginx源码目录不存在，尝试从官方网站下载")
            nginx_src_dir = None
    
    # 如果没有找到源码，尝试从官方网站下载
    if not nginx_src_dir:
        # 提取Nginx版本
        match = re.search(r'(\d+\.\d+\.\d+)', nginx_version)
        if not match:
            logger.error(f"无法解析Nginx版本: {nginx_version}")
            return False
        
        nginx_ver = match.group(1)
        nginx_src_name = f"nginx-{nginx_ver}"
        nginx_src_dir = os.path.join(build_dir, nginx_src_name)
        
        # 下载并解压Nginx源码
        if not os.path.exists(nginx_src_dir):
            nginx_src_url = f"http://nginx.org/download/{nginx_src_name}.tar.gz"
            nginx_src_tar = os.path.join(build_dir, f"{nginx_src_name}.tar.gz")
            
            logger.info(f"下载Nginx源码: {nginx_src_url}")
            try:
                cmd = f"curl -L --connect-timeout 30 --retry 3 -o {nginx_src_tar} {nginx_src_url}"
                subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                logger.info(f"解压Nginx源码到: {build_dir}")
                cmd = f"tar -xzf {nginx_src_tar} -C {build_dir}"
                subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                if not os.path.exists(nginx_src_dir):
                    logger.error(f"Nginx源码解压后目录不存在: {nginx_src_dir}")
                    return False
            except subprocess.CalledProcessError as e:
                logger.error(f"下载或解压Nginx源码失败: {e}")
                return False
    
    # 构建ModSecurity-Nginx模块
    try:
        logger.info("开始构建ModSecurity-Nginx模块...")
        
        # 切换到Nginx源码目录
        os.chdir(nginx_src_dir)
        
        # 准备编译命令
        configure_cmd = f"./configure --prefix={nginx_path}"
        
        # 添加Nginx原始编译选项
        # 特别处理 --add-dynamic-module 和 --add-module 选项，这些可能不应该出现在新的配置中
        for key, value in options.items():
            if key in ['add-dynamic-module', 'add-module']:
                continue
            if value is True:
                configure_cmd += f" --{key}"
            else:
                if key.startswith("--"):
                    configure_cmd += f" {key}={value}"
                else:
                    configure_cmd += f" --{key}={value}"
        
        # 添加ModSecurity模块
        configure_cmd += f" --add-dynamic-module={connector_dir}"
        
        # 执行配置
        logger.info(f"配置Nginx: {configure_cmd}")
        process = subprocess.run(configure_cmd, shell=True, check=True, 
                              stdout=subprocess.PIPE if not verbose else None, 
                              stderr=subprocess.PIPE if not verbose else None)
        
        # 编译模块
        logger.info("编译Nginx模块: make modules")
        make_cmd = "make modules"
        process = subprocess.run(make_cmd, shell=True, check=True, 
                              stdout=subprocess.PIPE if not verbose else None, 
                              stderr=subprocess.PIPE if not verbose else None)
        
        # 确定模块输出路径
        module_path = os.path.join(nginx_src_dir, "objs/ngx_http_modsecurity_module.so")
        if not os.path.exists(module_path):
            logger.error(f"编译后模块文件不存在: {module_path}")
            return False
        
        # 确定模块安装路径
        if is_bt:
            module_install_dir = "/www/server/nginx/modules"
        else:
            # 尝试查找标准模块路径
            module_install_dir = "/usr/lib64/nginx/modules"  # CentOS/RHEL
            if not os.path.exists(module_install_dir):
                module_install_dir = "/usr/lib/nginx/modules"  # Debian/Ubuntu
                if not os.path.exists(module_install_dir):
                    module_install_dir = "/usr/local/nginx/modules"  # 自编译
        
        # 创建模块目录
        os.makedirs(module_install_dir, exist_ok=True)
        
        # 复制模块到安装路径
        module_install_path = os.path.join(module_install_dir, "ngx_http_modsecurity_module.so")
        logger.info(f"安装模块到: {module_install_path}")
        shutil.copy2(module_path, module_install_path)
        
        logger.info("ModSecurity-Nginx模块构建并安装成功")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"构建ModSecurity-Nginx模块失败: {e}")
        logger.debug(f"错误输出: {e.stderr.decode() if e.stderr else 'None'}")
        return False
    except Exception as e:
        logger.error(f"构建ModSecurity-Nginx模块时发生未知错误: {e}")
        return False

def configure_nginx_modsecurity(modsec_dir):
    """配置Nginx使用ModSecurity
    
    Args:
        modsec_dir (str): ModSecurity目录
        
    Returns:
        bool: 是否成功配置
    """
    # 检查Nginx安装
    is_installed, _, _ = get_nginx_info()
    
    if not is_installed:
        logger.error("未检测到Nginx安装，无法配置")
        return False
    
    # 检查是否为宝塔面板环境
    is_bt = detect_bt_panel()
    
    # 确定Nginx配置路径
    if is_bt:
        nginx_conf_dir = "/www/server/nginx/conf"
    else:
        nginx_conf_dir = "/etc/nginx"
        if not os.path.exists(nginx_conf_dir):
            nginx_conf_dir = "/usr/local/nginx/conf"
    
    # 确定modules配置文件路径
    modules_conf_path = os.path.join(nginx_conf_dir, "modules/modsecurity.conf")
    os.makedirs(os.path.dirname(modules_conf_path), exist_ok=True)
    
    # 创建模块加载配置
    module_load_content = 'load_module modules/ngx_http_modsecurity_module.so;\n'
    
    # 将模块加载指令添加到动态模块配置中
    try:
        # 检查是否已存在
        modules_load_path = os.path.join(nginx_conf_dir, "modules.conf")
        if os.path.exists(modules_load_path):
            with open(modules_load_path, 'r') as f:
                content = f.read()
            
            if 'ngx_http_modsecurity_module.so' not in content:
                with open(modules_load_path, 'a') as f:
                    f.write(module_load_content)
        else:
            with open(modules_load_path, 'w') as f:
                f.write(module_load_content)
        
        logger.info(f"已将ModSecurity模块加载指令添加到: {modules_load_path}")
    except Exception as e:
        logger.error(f"添加模块加载指令失败: {e}")
        return False
    
    # 创建ModSecurity配置
    modsec_conf_content = '''# ModSecurity配置
modsecurity on;
modsecurity_rules_file /etc/nginx/modsec/main.conf;
'''
    
    try:
        with open(modules_conf_path, 'w') as f:
            f.write(modsec_conf_content)
        
        logger.info(f"已创建ModSecurity配置文件: {modules_conf_path}")
    except Exception as e:
        logger.error(f"创建ModSecurity配置文件失败: {e}")
        return False
    
    # 检查nginx.conf中是否包含模块配置
    nginx_conf_path = os.path.join(nginx_conf_dir, "nginx.conf")
    try:
        include_line = f'include {os.path.relpath(modules_load_path, nginx_conf_dir)};'
        modules_include_line = f'include {os.path.relpath(os.path.dirname(modules_conf_path), nginx_conf_dir)}/*.conf;'
        
        with open(nginx_conf_path, 'r') as f:
            content = f.read()
        
        # 检查是否已包含模块加载配置
        if f'include modules.conf' not in content and include_line not in content:
            # 将include语句添加到http块之前
            with open(nginx_conf_path, 'r') as f:
                lines = f.readlines()
            
            new_lines = []
            http_block_start = False
            
            for line in lines:
                if not http_block_start and 'http {' in line:
                    # 在http块之前添加include语句
                    new_lines.append(f'include modules.conf;\n')
                    http_block_start = True
                
                new_lines.append(line)
            
            with open(nginx_conf_path, 'w') as f:
                f.writelines(new_lines)
            
            logger.info(f"已将模块加载配置添加到: {nginx_conf_path}")
        
        # 检查是否已包含模块配置
        with open(nginx_conf_path, 'r') as f:
            content = f.read()
        
        if 'include modules/*.conf' not in content and modules_include_line not in content:
            # 将include语句添加到http块内
            with open(nginx_conf_path, 'r') as f:
                lines = f.readlines()
            
            new_lines = []
            http_block = False
            
            for line in lines:
                new_lines.append(line)
                
                if not http_block and 'http {' in line:
                    # 在http块内添加include语句
                    new_lines.append(f'    include modules/*.conf;\n')
                    http_block = True
            
            with open(nginx_conf_path, 'w') as f:
                f.writelines(new_lines)
            
            logger.info(f"已将模块配置添加到: {nginx_conf_path}")
        
        logger.info("Nginx ModSecurity配置完成")
        return True
    except Exception as e:
        logger.error(f"修改Nginx配置文件失败: {e}")
        return False

def install_nginx_modsecurity(build_dir, modsec_dir, verbose=False):
    """安装ModSecurity-Nginx模块
    
    Args:
        build_dir (str): 构建目录
        modsec_dir (str): ModSecurity目录
        verbose (bool): 是否输出详细信息
        
    Returns:
        bool: 是否成功安装
    """
    # 下载连接器
    connector_dir = download_connector(build_dir)
    if not connector_dir:
        logger.error("下载ModSecurity-Nginx连接器失败")
        return False
    
    # 构建模块
    if not build_nginx_module(build_dir, connector_dir, modsec_dir, verbose):
        logger.error("构建ModSecurity-Nginx模块失败")
        return False
    
    # 配置Nginx
    if not configure_nginx_modsecurity(modsec_dir):
        logger.error("配置Nginx使用ModSecurity失败")
        return False
    
    logger.info("ModSecurity-Nginx模块安装和配置完成")
    return True

# 如果直接运行此脚本，则执行测试
if __name__ == "__main__":
    import tempfile
    try:
        from modules.constants import setup_logger
    except ImportError as e:
        logging.error(f"导入模块时出错: {e}")
        sys.exit(1)
    
    # 设置日志
    logger = setup_logger()
    
    # 检查Nginx安装
    is_installed, nginx_version, nginx_path = get_nginx_info()
    
    if is_installed:
        logger.info(f"检测到Nginx: 版本{nginx_version}, 路径{nginx_path}")
        
        # 获取Nginx编译选项
        options = get_nginx_compile_options(nginx_path)
        
        # 输出选项
        for key, value in options.items():
            logger.info(f"  {key}: {value}")
        
        # 创建临时构建目录
        with tempfile.TemporaryDirectory() as temp_dir:
            logger.info(f"使用临时目录: {temp_dir}")
            
            # 测试安装
            modsec_dir = "/tmp/modsecurity"
            if install_nginx_modsecurity(temp_dir, modsec_dir, verbose=True):
                logger.info("ModSecurity-Nginx模块安装测试成功")
            else:
                logger.error("ModSecurity-Nginx模块安装测试失败")
    else:
        logger.error("未检测到Nginx安装，无法测试")
