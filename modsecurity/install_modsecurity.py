#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import shutil
import platform
import logging
import signal
from pathlib import Path
import tempfile
import argparse
import glob
import re

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('ModSecurity')

# 创建文件处理器
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modsecurity_install.log")
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

# 全局变量
BUILD_DIR = os.path.join(tempfile.gettempdir(), "modsecurity_build")

# 检测是否为宝塔环境
IS_BT_ENV = os.path.exists('/www/server/panel') or os.path.exists('/www/server/nginx')

# 根据环境设置Nginx路径
if IS_BT_ENV:
    NGINX_PATH = "/www/server/nginx"
    logger.info(f"检测到宝塔环境，设置Nginx路径为: {NGINX_PATH}")
else:
    NGINX_PATH = "/etc/nginx"
    logger.info(f"标准环境，设置Nginx路径为: {NGINX_PATH}")

# 信号处理函数，确保在脚本被中断时清理临时文件
def cleanup_handler(signum, frame):
    """在收到信号时清理临时文件"""
    logger.info(f"接收到信号 {signum}，正在清理临时文件...")
    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)
    logger.info("清理完成，退出")
    sys.exit(1)

# 注册信号处理函数
signal.signal(signal.SIGINT, cleanup_handler)  # Ctrl+C
signal.signal(signal.SIGTERM, cleanup_handler) # 终止信号

# 检测系统类型
def get_distro_family():
    """检测当前系统类型"""
    if os.path.exists('/etc/redhat-release') or os.path.exists('/etc/centos-release'):
        return 'rhel'
    elif os.path.exists('/etc/debian_version'):
        return 'debian'
    else:
        return 'unknown'

# 检测系统类型并缓存
DISTRO_FAMILY = get_distro_family()
logger.info(f"检测到系统类型: {DISTRO_FAMILY}")

# 安装系统依赖
def install_dependencies():
    """安装ModSecurity所需的系统依赖"""
    logger.info("安装系统依赖...")
    
    distro_family = DISTRO_FAMILY  # 使用全局缓存的系统类型
    
    # 检测是否为宝塔环境
    if IS_BT_ENV:
        logger.info("检测到宝塔面板环境，跳过Nginx安装")
    
    # 检测是否已安装Nginx
    nginx_installed = False
    try:
        # 尝试执行 nginx -v 命令检测是否已安装
        subprocess.run("nginx -v", shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        nginx_installed = True
        nginx_version_output = subprocess.check_output("nginx -v", shell=True, stderr=subprocess.STDOUT).decode()
        nginx_version = re.search(r'nginx/(\d+\.\d+\.\d+)', nginx_version_output).group(1)
        logger.info(f"检测到系统中已安装Nginx v{nginx_version}，跳过Nginx安装")
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.info("未检测到Nginx，将进行安装")
        nginx_installed = False
    
    if distro_family == 'rhel':
        # CentOS/RHEL系统
        dependencies = [
            "git", "gcc", "gcc-c++", "make", "automake", "autoconf", "libtool", 
            "pcre-devel", "libxml2-devel", "curl-devel", "openssl-devel", 
            "yajl-devel", "libmaxminddb-devel", "lua-devel",
            # 添加更多必要的开发包
            "zlib-devel", "gd-devel", "perl-devel", "perl-ExtUtils-Embed",
            "kernel-devel", "cmake", 
            # 添加GeoIP库的依赖，修复“the GeoIP module requires the GeoIP library”错误
            "GeoIP", "GeoIP-devel"
        ]
        # 如果未安装nginx且不是宝塔环境，添加nginx依赖
        if not nginx_installed and not IS_BT_ENV:
            dependencies.append("nginx")
            logger.info("将安装Nginx服务器")
        else:
            logger.info("跳过Nginx安装，使用现有Nginx")
        cmd = f"yum install -y {' '.join(dependencies)}"
    elif distro_family == 'debian':
        # Debian/Ubuntu系统
        dependencies = [
            "git", "build-essential", "automake", "autoconf", "libtool", 
            "libpcre3-dev", "libxml2-dev", "libcurl4-openssl-dev", "libssl-dev", 
            "libyajl-dev", "libmaxminddb-dev", "liblua5.3-dev",
            # 添加更多必要的开发包，特别是Ubuntu系统需要的
            "zlib1g-dev", "gcc", "g++", "make", "cmake", "pkg-config",
            # 添加GeoIP库的依赖，修复“the GeoIP module requires the GeoIP library”错误
            "libgeoip-dev", "libgeoip1"
        ]
        # 如果未安装nginx且不是宝塔环境，添加nginx依赖
        if not nginx_installed and not IS_BT_ENV:
            dependencies.append("nginx")
            logger.info("将安装Nginx服务器")
        else:
            logger.info("跳过Nginx安装，使用现有Nginx")
        cmd = f"apt update && apt install -y {' '.join(dependencies)}"
    else:
        logger.error("不支持的系统类型")
        sys.exit(1)
    
    try:
        subprocess.run(cmd, shell=True, check=True)
        logger.info("依赖安装完成")
    except subprocess.CalledProcessError:
        logger.error("依赖安装失败")
        sys.exit(1)

# 下载ModSecurity库
def download_modsecurity(force_update=False):
    """下载ModSecurity核心库
    
    Args:
        force_update (bool, optional): 强制重新编译ModSecurity模块，即使已存在也会更新。默认为False。
    """
    logger.info("下载ModSecurity...")
    os.chdir(BUILD_DIR)
    
    # 设置ModSecurity版本
    MODSEC_VERSION = "3.0.14"
    
    # 优先尝试从supine-win的Gitee镜像下载源码
    try:
        logger.info("尝试从supine-win的Gitee镜像下载ModSecurity源码...")
        subprocess.run("git clone https://gitee.com/supine-win/ModSecurity.git modsecurity", 
                     shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.info("从supine-win的Gitee镜像下载ModSecurity源码成功")
        download_success = True
    except subprocess.CalledProcessError:
        logger.warning("从supine-win的镜像下载失败，尝试官方Gitee镜像")
        download_success = False
    
    # 如果上一步失败，尝试官方Gitee镜像
    if not download_success:
        try:
            logger.info("尝试从Gitee官方镜像下载ModSecurity源码...")
            subprocess.run("git clone https://gitee.com/mirrors/ModSecurity.git modsecurity", 
                         shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.info("从Gitee官方镜像下载ModSecurity源码成功")
            download_success = True
        except subprocess.CalledProcessError:
            logger.warning("从Gitee镜像下载失败，尝试从GitHub下载")
            download_success = False
    
    # 如果上一步失败，作为最后尝试从GitHub下载源码
    if not download_success:
        try:
            logger.info("尝试从GitHub下载ModSecurity源码...")
            subprocess.run("git clone https://github.com/SpiderLabs/ModSecurity.git modsecurity", 
                         shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.info("从GitHub下载ModSecurity源码成功")
            download_success = True
        except subprocess.CalledProcessError:
            logger.error("无法下载ModSecurity源码，请检查网络连接")
            sys.exit(1)
    
    # 检查模块文件是否已存在
    modules_dir = os.path.join(NGINX_PATH, "modules")
    module_file = os.path.join(modules_dir, "ngx_http_modsecurity_module.so")
    module_exists = os.path.exists(module_file)

    # 编译并安装ModSecurity
    try:
        os.chdir(os.path.join(BUILD_DIR, "modsecurity"))
        
        # 初始化子模块
        logger.info("初始化子模块...")
        print("+++ 执行: git submodule init +++")
        subprocess.run("git submodule init", shell=True, check=True)
        print("+++ 执行: git submodule update +++")
        subprocess.run("git submodule update", shell=True, check=True)
        
        # 如果模块已存在且不是强制更新，跳过编译步骤
        if module_exists and not force_update:
            logger.info(f"检测到ModSecurity模块已存在: {module_file}")
            logger.info("跳过ModSecurity的编译和安装步骤")
            return
        
        # 如果强制更新模式且模块存在
        if module_exists and force_update:
            logger.info(f"强制更新模式: 将重新编译ModSecurity模块")
            
        # 构建和编译
        logger.info("开始编译ModSecurity...")
        print("+++ 执行: ./build.sh +++")
        subprocess.run("./build.sh", shell=True, check=True)
        print("+++ 执行: ./configure +++")
        subprocess.run("./configure", shell=True, check=True)
        print("+++ 执行: make +++")
        subprocess.run("make", shell=True, check=True)
        print("+++ 执行: make install +++")
        subprocess.run("make install", shell=True, check=True)
        
        logger.info("ModSecurity编译安装完成")
    except subprocess.CalledProcessError as e:
        logger.error(f"ModSecurity编译安装失败: {e}")
        sys.exit(1)
    


# 下载和安装ModSecurity-nginx连接器
def install_modsecurity_nginx(force_update=False):
    """下载和安装ModSecurity-nginx连接器
    
    Args:
        force_update (bool, optional): 强制重新编译ModSecurity模块，即使已存在也会更新。默认为False。
    """
    logger.info("下载ModSecurity-nginx连接器...")
    
    # 检查模块文件是否已存在
    modules_dir = os.path.join(NGINX_PATH, "modules")
    module_file = os.path.join(modules_dir, "ngx_http_modsecurity_module.so")
    if os.path.exists(module_file) and not force_update:
        logger.info(f"检测到ModSecurity模块已存在: {module_file}")
        logger.info("跳过ModSecurity-nginx模块编译和安装")
        return
        
    # 如果强制更新模式且模块存在
    if os.path.exists(module_file) and force_update:
        logger.info(f"强制更新模式: 将重新编译ModSecurity-nginx模块")
        # 移除现有模块文件以确保更新
        try:
            os.remove(module_file)
            logger.info(f"已移除现有模块文件: {module_file}")
        except Exception as e:
            logger.warning(f"无法移除现有模块文件: {e}")
        
    os.chdir(BUILD_DIR)

    # 优先尝试从supine-win的Gitee镜像下载源码
    download_success = False
    try:
        logger.info("尝试从supine-win的Gitee镜像下载ModSecurity-nginx源码...")
        subprocess.run("git clone https://gitee.com/supine-win/ModSecurity-nginx.git modsecurity-nginx", 
                     shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.info("从supine-win的Gitee镜像下载ModSecurity-nginx成功")
        download_success = True
    except subprocess.CalledProcessError:
        logger.warning("从supine-win的镜像下载失败，尝试官方Gitee镜像")
    
    # 如果上一步失败，尝试官方Gitee镜像
    if not download_success:
        try:
            logger.info("尝试从Gitee官方镜像下载ModSecurity-nginx源码...")
            subprocess.run("git clone https://gitee.com/mirrors/ModSecurity-nginx.git modsecurity-nginx", 
                         shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.info("从Gitee官方镜像下载ModSecurity-nginx源码成功")
            download_success = True
        except subprocess.CalledProcessError:
            logger.warning("从Gitee镜像下载失败，尝试从GitHub下载")
    
    # 如果上一步失败，作为最后尝试从GitHub下载源码
    if not download_success:
        try:
            logger.info("尝试从GitHub下载ModSecurity-nginx源码...")
            subprocess.run("git clone https://github.com/SpiderLabs/ModSecurity-nginx.git modsecurity-nginx", 
                         shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.info("从GitHub下载ModSecurity-nginx源码成功")
            download_success = True
        except subprocess.CalledProcessError:
            logger.error("无法下载ModSecurity-nginx源码，请检查网络连接")
            sys.exit(1)
    
    # 获取Nginx版本和源码
    try:
        # 获取Nginx版本和源码
        nginx_version_output = subprocess.check_output("nginx -v", shell=True, stderr=subprocess.STDOUT).decode()
        nginx_version = re.search(r'nginx/(\d+\.\d+\.\d+)', nginx_version_output).group(1)
        logger.info(f"检测到Nginx版本: {nginx_version}")
        
        # 下载Nginx源码
        logger.info(f"下载Nginx v{nginx_version} 源码...")
        os.chdir(BUILD_DIR)
        nginx_src_url = f"http://nginx.org/download/nginx-{nginx_version}.tar.gz"
        
        # 尝试不同的源下载Nginx
        try:
            # 尝试Gitee镜像
            gitee_nginx_url = f"https://gitee.com/mirrors/nginx/raw/master/nginx-{nginx_version}.tar.gz"
            subprocess.run(f"wget -q {gitee_nginx_url} -O nginx.tar.gz", shell=True, check=True)
            logger.info("从Gitee镜像下载Nginx源码成功")
        except subprocess.CalledProcessError:
            # 如果失败，使用原始链接
            logger.warning("从Gitee镜像下载Nginx失败，尝试官方源")
            subprocess.run(f"wget -q {nginx_src_url} -O nginx.tar.gz", shell=True, check=True)
            logger.info("从nginx.org下载Nginx源码成功")
        
        subprocess.run("tar -xzf nginx.tar.gz", shell=True, check=True)
        nginx_src_dir = f"nginx-{nginx_version}"
        
        # 编译Nginx模块
        logger.info("开始编译Nginx ModSecurity模块...")
        os.chdir(os.path.join(BUILD_DIR, nginx_src_dir))
        
        # 获取编译参数
        configure_args = subprocess.check_output("nginx -V", shell=True, stderr=subprocess.STDOUT).decode()
        configure_args = re.search(r'configure arguments: (.*)', configure_args).group(1)
        
        # 使用全局缓存的系统类型
        distro_family = DISTRO_FAMILY
        
        # 如果系统中没有libperl-dev包，移除perl模块选项减少编译问题
        if "--with-http_perl_module" in configure_args or "--with-http_perl_module=dynamic" in configure_args:
            # 尝试检查libperl-dev是否安装
            perl_dev_installed = False
            try:
                if distro_family == 'debian':
                    result = subprocess.run("dpkg -l | grep libperl-dev", shell=True, 
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    perl_dev_installed = result.returncode == 0
                elif distro_family == 'rhel':
                    result = subprocess.run("rpm -qa | grep perl-devel", shell=True, 
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    perl_dev_installed = result.returncode == 0
            except:
                pass
                
            if not perl_dev_installed:
                # 如果未安装，由于PERL模块常常导致问题，这里选择移除Perl模块
                logger.warning("检测到Nginx配置中含有Perl模块，但系统中没有完整的Perl开发环境")
                logger.warning("为确保成功编译，将从配置中移除Perl模块")
                # 从配置中移除Perl模块
                configure_args = re.sub(r'--with-http_perl_module[=\w]*', '', configure_args)
                logger.info("已禁用Perl模块，以确保编译成功")
        
        # 确保GeoIP库已安装，而不是移除GeoIP模块
        logger.info("确保安装GeoIP库以支持GeoIP模块...")
        
        # 确保安装GeoIP库
        try:
            if distro_family == 'debian':
                # 安装GeoIP相关库
                geoip_packages = ["libgeoip-dev", "libgeoip1", "geoip-bin"]
                print(f"+++ 执行: apt-get install -y {' '.join(geoip_packages)} +++")
                subprocess.run(["apt-get", "install", "-y"] + geoip_packages, check=True)
                
                # 安装Perl开发库，解决 "cannot find -lperl" 错误
                perl_packages = ["libperl-dev", "perl"]
                print(f"+++ 执行: apt-get install -y {' '.join(perl_packages)} +++")
                subprocess.run(["apt-get", "install", "-y"] + perl_packages, check=True)
                logger.info("已安装Debian/Ubuntu系统的GeoIP库")
            elif distro_family == 'rhel':
                # 安装GeoIP相关库
                geoip_packages = ["GeoIP", "GeoIP-devel", "geoipupdate"]
                print(f"+++ 执行: yum install -y {' '.join(geoip_packages)} +++")
                subprocess.run(["yum", "install", "-y"] + geoip_packages, check=True)
                
                # 安装Perl开发库，解决 "cannot find -lperl" 错误
                perl_packages = ["perl", "perl-devel", "perl-ExtUtils-Embed"]
                print(f"+++ 执行: yum install -y {' '.join(perl_packages)} +++")
                subprocess.run(["yum", "install", "-y"] + perl_packages, check=True)
                logger.info("已安装CentOS/RHEL系统的GeoIP库")
            else:
                logger.warning("无法识别系统类型，请手动安装GeoIP库")
                logger.warning("对于Debian/Ubuntu系统，使用: apt-get install -y libgeoip-dev libgeoip1 geoip-bin")
                logger.warning("对于CentOS/RHEL系统，使用: yum install -y GeoIP GeoIP-devel geoipupdate")
        except subprocess.CalledProcessError as e:
            logger.error(f"安装GeoIP库失败: {str(e)}")
            logger.warning("将尝试继续编译，但可能会遇到GeoIP相关错误")
        
        # 添加ModSecurity模块
        modsec_nginx_path = os.path.join(BUILD_DIR, "modsecurity-nginx")
        
        # 构建编译命令
        compile_cmd = f"./configure {configure_args} --add-dynamic-module={modsec_nginx_path}"
        print(f"+++ 执行: {compile_cmd} +++")
        try:
            # 捕获并保存所有输出，便于调试
            process = subprocess.Popen(compile_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate()
            
            # 显示所有输出
            if stdout:
                print("Configure 标准输出:")
                print(stdout)
                
            # 如果返回非零状态，显示错误并退出
            if process.returncode != 0:
                print("\n\nConfigure 错误输出:")
                print(stderr)
                # 检查常见的错误原因
                missing_deps = []
                if "not found" in stderr:
                    missing_deps.append("缺少依赖库")
                if "error: C" in stderr:
                    missing_deps.append("编译器错误")
                    
                error_msg = "编译配置失败"
                if missing_deps:
                    error_msg += ": " + ", ".join(missing_deps)
                
                logger.error(f"{error_msg}\n请检查编译环境并确保所有依赖项已安装")
                logger.error("请尝试手动安装以下开发包: build-essential libpcre3-dev libxml2-dev libcurl4-openssl-dev")
                sys.exit(1)
        
            print("+++ 执行: make modules +++")
            # 同样捕获make命令的输出
            process = subprocess.Popen("make modules", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate()
            
            if stdout:
                print("Make 标准输出:")
                print(stdout)
                
            if process.returncode != 0:
                print("\n\nMake 错误输出:")
                print(stderr)
                logger.error("模块编译失败\n请检查上述错误信息")
                sys.exit(1)
                
            logger.info("编译Nginx ModSecurity模块成功")
        except Exception as e:
            logger.error(f"编译过程出现异常: {str(e)}")
            logger.error("请确保安装了所有必要的开发包：build-essential libpcre3-dev libxml2-dev libcurl4-openssl-dev")
            sys.exit(1)
        
        # 创建模块目录并复制模块
        modules_dir = os.path.join(NGINX_PATH, "modules")
        os.makedirs(modules_dir, exist_ok=True)
        
        # 复制模块
        module_path = os.path.join(BUILD_DIR, nginx_src_dir, "objs/ngx_http_modsecurity_module.so")
        shutil.copy(module_path, modules_dir)
        
        logger.info("Nginx ModSecurity模块安装完成")
    except subprocess.CalledProcessError as e:
        logger.error(f"ModSecurity-nginx安装失败: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"获取Nginx版本或编译模块时出错: {e}")
        sys.exit(1)

# 下载OWASP ModSecurity核心规则集(CRS)
def download_owasp_crs():
    """下载OWASP ModSecurity核心规则集"""
    logger.info("下载OWASP ModSecurity核心规则集...")
    os.chdir(BUILD_DIR)
    
    # 创建CRS目录 - 根据环境选择路径
    if IS_BT_ENV:
        crs_dir = "/www/server/nginx/modsecurity-crs"
    else:
        crs_dir = "/etc/nginx/modsecurity-crs"
        
    logger.info(f"使用CRS规则目录: {crs_dir}")
    os.makedirs(crs_dir, exist_ok=True)
    
    # 优先尝试从supine-win的Gitee镜像下载
    try:
        subprocess.run("git clone https://gitee.com/supine-win/coreruleset.git", 
                     shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.info("从supine-win的Gitee镜像下载CRS成功")
        
        # 复制CRS文件
        src_dir = os.path.join(BUILD_DIR, "coreruleset")
        for item in os.listdir(src_dir):
            s = os.path.join(src_dir, item)
            d = os.path.join(crs_dir, item)
            if os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)
        logger.info(f"CRS文件已复制到{crs_dir}/")
    except subprocess.CalledProcessError:
        logger.warning("从supine-win的镜像下载失败，尝试官方Gitee镜像")
        try:
            subprocess.run("git clone https://gitee.com/mirrors/owasp-modsecurity-crs.git", 
                         shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.info("从Gitee镜像下载CRS成功")
            
            # 复制CRS文件
            src_dir = os.path.join(BUILD_DIR, "owasp-modsecurity-crs")
            for item in os.listdir(src_dir):
                s = os.path.join(src_dir, item)
                d = os.path.join(crs_dir, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)
            logger.info(f"从Gitee镜像下载的CRS文件已复制到{crs_dir}/")
        except subprocess.CalledProcessError:
            logger.warning("从Gitee镜像下载失败，尝试从GitHub下载")
            try:
                subprocess.run("git clone https://github.com/coreruleset/coreruleset.git", 
                             shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                logger.info("从GitHub下载CRS成功")
                
                # 复制CRS文件
                src_dir = os.path.join(BUILD_DIR, "coreruleset")
                for item in os.listdir(src_dir):
                    s = os.path.join(src_dir, item)
                    d = os.path.join(crs_dir, item)
                    if os.path.isdir(s):
                        shutil.copytree(s, d, dirs_exist_ok=True)
                    else:
                        shutil.copy2(s, d)
                logger.info(f"从GitHub下载的CRS文件已复制到{crs_dir}/")
            except subprocess.CalledProcessError:
                logger.error("下载CRS失败")
                sys.exit(1)
    
    # 创建并复制默认配置
    if os.path.exists(os.path.join(crs_dir, "crs-setup.conf.example")):
        shutil.copy(
            os.path.join(crs_dir, "crs-setup.conf.example"),
            os.path.join(crs_dir, "crs-setup.conf")
        )
        logger.info("CRS配置文件已创建")
    else:
        logger.warning("未找到CRS配置示例文件，将创建基本配置")
        with open(os.path.join(crs_dir, "crs-setup.conf"), 'w') as f:
            f.write("# 基本CRS配置\n")
    
    logger.info("OWASP CRS安装完成")

# 配置ModSecurity
def configure_modsecurity():
    """配置ModSecurity"""
    logger.info("配置ModSecurity...")
    
    # 创建ModSecurity配置目录
    if IS_BT_ENV:
        modsec_dir = "/www/server/nginx/modsecurity"
    else:
        modsec_dir = "/etc/nginx/modsecurity"
    
    logger.info(f"使用ModSecurity配置目录: {modsec_dir}")
    os.makedirs(modsec_dir, exist_ok=True)
    
    # 复制默认配置
    modsec_conf_src = os.path.join(BUILD_DIR, "modsecurity/modsecurity.conf-recommended")
    modsec_conf_dst = os.path.join(modsec_dir, "modsecurity.conf")
    shutil.copy(modsec_conf_src, modsec_conf_dst)
    
    # 复制unicode.mapping文件
    unicode_mapping_src = os.path.join(BUILD_DIR, "modsecurity/unicode.mapping")
    unicode_mapping_dst = os.path.join(modsec_dir, "unicode.mapping")
    if os.path.exists(unicode_mapping_src):
        logger.info(f"复制unicode.mapping文件到{modsec_dir}")
        shutil.copy(unicode_mapping_src, unicode_mapping_dst)
    else:
        logger.warning("未找到unicode.mapping文件，尝试从其他目录查找")
        # 尝试从可能的位置查找
        possible_paths = [
            # 已经在上面检查过的路径不需要再次添加: os.path.join(BUILD_DIR, "modsecurity/unicode.mapping")
            os.path.join(BUILD_DIR, "modsecurity-*/unicode.mapping"),
            "/usr/local/modsecurity/unicode.mapping",
            "/usr/share/modsecurity/unicode.mapping",
            "/usr/local/lib/modsecurity/unicode.mapping",
            "/opt/modsecurity/unicode.mapping"
        ]
        
        # 根据环境添加宝塔特定路径
        if IS_BT_ENV:
            possible_paths.append("/www/server/nginx/conf/modsecurity/unicode.mapping")
            possible_paths.append("/www/server/modsecurity/unicode.mapping")
        
        found = False
        for path_pattern in possible_paths:
            for path in glob.glob(path_pattern):
                if os.path.exists(path):
                    logger.info(f"在{path}找到unicode.mapping文件")
                    shutil.copy(path, unicode_mapping_dst)
                    found = True
                    break
            if found:
                break
                
        if not found:
            # 如果仍未找到，创建一个空文件并显示警告
            logger.error("无法找到unicode.mapping文件，请手动配置")
            with open(unicode_mapping_dst, 'w') as f:
                f.write("# This is a placeholder unicode.mapping file\n")
            logger.warning("创建了一个空的unicode.mapping文件，请手动配置")
    
    # 修改配置以启用ModSecurity并修正路径
    with open(modsec_conf_dst, 'r') as file:
        conf_content = file.read()
    
    # 启用ModSecurity
    conf_content = conf_content.replace('SecRuleEngine DetectionOnly', 'SecRuleEngine On')
    
    # 修正unicode.mapping文件路径为绝对路径
    unicode_map_file = os.path.join(modsec_dir, "unicode.mapping")
    
    # 通过正则表达式替换SecUnicodeMapFile指令的路径
    pattern = r'SecUnicodeMapFile\s+[^\n]+'
    replacement = f'SecUnicodeMapFile {unicode_map_file}'
    conf_content = re.sub(pattern, replacement, conf_content)
    
    logger.info(f"将unicode.mapping路径设置为绝对路径: {unicode_map_file}")
    
    with open(modsec_conf_dst, 'w') as file:
        file.write(conf_content)
    
    # 创建include.conf配置
    include_conf = os.path.join(modsec_dir, "include.conf")
    
    # 根据环境调整路径
    if IS_BT_ENV:
        crs_path = "/www/server/nginx/modsecurity-crs"
    else:
        crs_path = "/etc/nginx/modsecurity-crs"
    
    with open(include_conf, 'w') as file:
        file.write(f"""# ModSecurity配置
Include "{modsec_dir}/modsecurity.conf"
Include "{crs_path}/crs-setup.conf"
Include "{crs_path}/rules/*.conf"
""")
    
    # 创建Nginx ModSecurity配置 - 拆分为两个文件
    
    # 1. 创建加载模块的配置文件（必须在主配置文件的最顶层）
    if IS_BT_ENV:
        modsec_module_conf = "/www/server/nginx/modules-enabled/50-mod-http-modsecurity.conf"
    else:
        modsec_module_conf = "/etc/nginx/modules-enabled/50-mod-http-modsecurity.conf"
    
    logger.info(f"使用模块配置文件: {modsec_module_conf}")
    os.makedirs(os.path.dirname(modsec_module_conf), exist_ok=True)
    # 获取模块的绝对路径
    module_file = os.path.join(NGINX_PATH, "modules/ngx_http_modsecurity_module.so")
    
    with open(modsec_module_conf, 'w') as file:
        file.write(f"""# 加载ModSecurity模块 - 这必须放在主配置文件的顶层
load_module {module_file};
""")
    
    # 2. 创建实际启用ModSecurity的配置文件（在http块内包含）
    if IS_BT_ENV:
        modsec_nginx_conf = "/www/server/nginx/conf.d/modsecurity.conf"
    else:
        modsec_nginx_conf = "/etc/nginx/conf.d/modsecurity.conf"
        
    logger.info(f"使用Nginx配置文件: {modsec_nginx_conf}")
    os.makedirs(os.path.dirname(modsec_nginx_conf), exist_ok=True)
    
    with open(modsec_nginx_conf, 'w') as file:
        file.write(f"""# 在server块内启用ModSecurity
modsecurity on;
modsecurity_rules_file {modsec_dir}/include.conf;
""")
    
    logger.info("ModSecurity配置完成，请将以下内容添加到您的Nginx主配置文件的顶层:")
    logger.info(f"include {modsec_module_conf};")
    logger.info("并将以下内容添加到http块:")
    logger.info(f"include {modsec_nginx_conf};")
    
    # 重启Nginx - 兼容不同系统和环境
    logger.info("测试Nginx配置并重启服务...")
    try:
        # 首先测试配置是否正确
        subprocess.run("nginx -t", shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.info("Nginx配置测试成功")
        
        # 采用不同的重启策略
        restart_success = False
        
        # 1. 先尝试systemctl命令
        try:
            logger.info("尝试使用systemctl重启Nginx...")
            subprocess.run("systemctl restart nginx", shell=True, check=True, 
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            restart_success = True
            logger.info("使用systemctl重启Nginx成功")
        except subprocess.CalledProcessError:
            logger.warning("systemctl重启失败，尝试其他方法")
        
        # 2. 如果失败，尝试service命令
        if not restart_success:
            try:
                logger.info("尝试使用service重启Nginx...")
                subprocess.run("service nginx restart", shell=True, check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                restart_success = True
                logger.info("使用service重启Nginx成功")
            except subprocess.CalledProcessError:
                logger.warning("service重启失败，尝试其他方法")
        
        # 3. 如果在宝塔环境，尝试宝塔特定命令
        if not restart_success and IS_BT_ENV:
            try:
                logger.info("在宝塔环境中尝试重启Nginx...")
                subprocess.run("/etc/init.d/nginx restart", shell=True, check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                restart_success = True
                logger.info("使用宝塔方式重启Nginx成功")
            except subprocess.CalledProcessError:
                logger.warning("宝塔特定重启方式失败")
                
        # 4. 直接尝试nginx -s reload
        if not restart_success:
            try:
                logger.info("尝试使用nginx -s reload重新加载配置...")
                subprocess.run("nginx -s reload", shell=True, check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                restart_success = True
                logger.info("使用nginx -s reload重新加载成功")
            except subprocess.CalledProcessError:
                logger.warning("nginx -s reload 失败")
        
        if restart_success:
            logger.info("Nginx已重启，ModSecurity现已启用")
        else:
            logger.error("所有重启方法均失败，请手动重启Nginx：")
            logger.error("1. systemctl restart nginx")
            logger.error("2. service nginx restart")
            logger.error("3. /etc/init.d/nginx restart")
            logger.error("4. nginx -s reload")
    except subprocess.CalledProcessError:
        logger.error("Nginx配置测试失败，请手动检查配置")
        sys.exit(1)

# 主函数
def main(force_update=False):
    """主函数
    
    Args:
        force_update (bool, optional): 强制更新ModSecurity模块，即使已存在也会重新编译。默认为False。
    """
    try:
        # 检查是否为root用户
        if os.geteuid() != 0:
            logger.error("此脚本需要以root权限运行")
            sys.exit(1)
        
        # 创建构建目录
        os.makedirs(BUILD_DIR, exist_ok=True)
        
        # 安装依赖
        install_dependencies()
        
        # 下载和编译ModSecurity
        download_modsecurity(force_update)
        
        # 安装ModSecurity-nginx
        install_modsecurity_nginx(force_update)
        
        # 下载CRS规则
        download_owasp_crs()
        
        # 配置ModSecurity
        configure_modsecurity()
        
        logger.info("ModSecurity安装完成!")
        logger.info(f"详细日志请查看: {log_file}")
        
    except Exception as e:
        logger.error(f"安装过程中发生错误: {e}")
        sys.exit(1)
    finally:
        # 清理临时文件
        logger.info("清理临时文件...")
        if os.path.exists(BUILD_DIR):
            shutil.rmtree(BUILD_DIR)

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='ModSecurity安装脚本')
    parser.add_argument('-f', '--force', action='store_true', help='强制重新编译ModSecurity模块，即使已存在也会更新')
    parser.add_argument('-v', '--verbose', action='store_true', help='显示详细的安装过程信息')
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    # 如果指定了详细模式，设置日志级别为DEBUG
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        
    main(force_update=args.force)
