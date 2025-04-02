#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import shutil
import platform
import logging
from pathlib import Path
import tempfile

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
NGINX_PATH = "/etc/nginx"

# 检测系统类型
def get_distro_family():
    """检测当前系统类型"""
    if os.path.exists('/etc/redhat-release') or os.path.exists('/etc/centos-release'):
        return 'rhel'
    elif os.path.exists('/etc/debian_version'):
        return 'debian'
    else:
        return 'unknown'

# 安装系统依赖
def install_dependencies():
    """安装ModSecurity所需的系统依赖"""
    logger.info("安装系统依赖...")
    
    distro_family = get_distro_family()
    
    # 检测是否为宝塔环境
    is_bt_env = os.path.exists('/www/server/panel') or os.path.exists('/www/server/nginx')
    if is_bt_env:
        logger.info("检测到宝塔面板环境，跳过Nginx安装")
    
    if distro_family == 'rhel':
        # CentOS/RHEL系统
        dependencies = [
            "git", "gcc", "gcc-c++", "make", "automake", "autoconf", "libtool", 
            "pcre-devel", "libxml2-devel", "curl-devel", "openssl-devel", 
            "yajl-devel", "libmaxminddb-devel", "lua-devel"
        ]
        # 如果不是宝塔环境，添加nginx依赖
        if not is_bt_env:
            dependencies.append("nginx")
        cmd = f"yum install -y {' '.join(dependencies)}"
    elif distro_family == 'debian':
        # Debian/Ubuntu系统
        dependencies = [
            "git", "build-essential", "automake", "autoconf", "libtool", 
            "libpcre3-dev", "libxml2-dev", "libcurl4-openssl-dev", "libssl-dev", 
            "libyajl-dev", "libmaxminddb-dev", "liblua5.3-dev"
        ]
        # 如果不是宝塔环境，添加nginx依赖
        if not is_bt_env:
            dependencies.append("nginx")
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
def download_modsecurity():
    """下载ModSecurity核心库"""
    logger.info("下载ModSecurity...")
    os.chdir(BUILD_DIR)
    
    # 设置ModSecurity版本
    MODSEC_VERSION = "3.0.14"
    
    # 创建下载目录
    modsec_dir = os.path.join(BUILD_DIR, "modsecurity")
    os.makedirs(modsec_dir, exist_ok=True)
    os.chdir(modsec_dir)
    
    # 下载预编译的版本
    download_success = False
    
    # 如果下载失败，尝试从GitHub下载
    if not download_success:
        try:
            logger.info(f"尝试从GitHub下载ModSecurity v{MODSEC_VERSION}...")
            download_url = f"https://github.com/SpiderLabs/ModSecurity/releases/download/v{MODSEC_VERSION}/modsecurity-v{MODSEC_VERSION}.tar.gz"
            subprocess.run(f"wget -q {download_url} -O modsecurity.tar.gz", shell=True, check=True)
            download_success = True
            logger.info("从GitHub下载ModSecurity成功")
        except subprocess.CalledProcessError:
            logger.error("无法下载ModSecurity发布版本")

    # 尝试从supine-win的Gitee仓库下载预编译版本
    try:
        logger.info(f"尝试从supine-win的Gitee镜像下载ModSecurity v{MODSEC_VERSION}...")
        download_url = f"https://gitee.com/supine-win/ModSecurity/releases/download/v{MODSEC_VERSION}/modsecurity-v{MODSEC_VERSION}-linux-x64.tar.gz"
        subprocess.run(f"wget -q {download_url} -O modsecurity.tar.gz", shell=True, check=True)
        download_success = True
        logger.info("从supine-win的Gitee镜像下载ModSecurity预编译版本成功")
    except subprocess.CalledProcessError:
        logger.warning("从supine-win的Gitee镜像下载预编译版本失败，尝试GitHub官方发布版本")
        sys.exit(1)
    
    # 解压安装ModSecurity
    try:
        logger.info("正在解压安装ModSecurity...")
        subprocess.run("tar -xzf modsecurity.tar.gz --strip-components=1", shell=True, check=True)
        
        # 安装依赖
        if get_distro_family() == 'rhel':
            subprocess.run("yum install -y libxml2-devel curl-devel pcre-devel", shell=True, check=True)
        else:  # debian
            subprocess.run("apt-get update && apt-get install -y libxml2-dev libcurl4-openssl-dev libpcre3-dev", shell=True, check=True)
        
        # 运行配置和安装
        subprocess.run("./configure", shell=True, check=True)
        subprocess.run("make", shell=True, check=True)
        subprocess.run("make install", shell=True, check=True)
        
        logger.info("ModSecurity安装完成")
    except subprocess.CalledProcessError as e:
        logger.error(f"ModSecurity安装失败: {e}")
        sys.exit(1)

# 下载和安装ModSecurity-nginx连接器
def install_modsecurity_nginx():
    """下载和安装ModSecurity-nginx连接器"""
    logger.info("下载ModSecurity-nginx连接器...")
    os.chdir(BUILD_DIR)
    
    # 设置ModSecurity-nginx版本
    MODSEC_NGINX_VERSION = "1.0.3"
    
    # 创建下载目录
    modsec_nginx_dir = os.path.join(BUILD_DIR, "modsecurity-nginx")
    os.makedirs(modsec_nginx_dir, exist_ok=True)
    os.chdir(modsec_nginx_dir)
    
    # 下载预编译的版本
    download_success = False
    
    # 尝试从supine-win的Gitee仓库下载预编译版本
    try:
        logger.info(f"尝试从supine-win的Gitee镜像下载ModSecurity-nginx v{MODSEC_NGINX_VERSION}...")
        download_url = f"https://gitee.com/supine-win/ModSecurity-nginx/releases/download/v{MODSEC_NGINX_VERSION}/modsecurity-nginx-v{MODSEC_NGINX_VERSION}.tar.gz"
        subprocess.run(f"wget -q {download_url} -O modsecurity-nginx.tar.gz", shell=True, check=True)
        download_success = True
        logger.info("从supine-win的Gitee镜像下载ModSecurity-nginx预编译版本成功")
    except subprocess.CalledProcessError:
        logger.warning("从supine-win的Gitee镜像下载预编译版本失败，尝试GitHub官方发布版本")
    
    # 如果不能下载预编译版本，尝试从GitHub下载源码包
    if not download_success:
        try:
            logger.info(f"尝试从GitHub下载ModSecurity-nginx v{MODSEC_NGINX_VERSION}...")
            download_url = f"https://github.com/owasp-modsecurity/ModSecurity-nginx/archive/refs/tags/v{MODSEC_NGINX_VERSION}.tar.gz"
            subprocess.run(f"wget -q {download_url} -O modsecurity-nginx.tar.gz", shell=True, check=True)
            download_success = True
            logger.info("从GitHub下载ModSecurity-nginx成功")
        except subprocess.CalledProcessError:
            logger.error("无法下载ModSecurity-nginx发布版本")
            sys.exit(1)
    
    # 解压ModSecurity-nginx源码
    try:
        logger.info("正在解压ModSecurity-nginx...")
        subprocess.run("tar -xzf modsecurity-nginx.tar.gz --strip-components=1", shell=True, check=True)
        logger.info("解压ModSecurity-nginx成功")
        
        # 获取Nginx版本和源码
        nginx_version_output = subprocess.check_output("nginx -v", shell=True, stderr=subprocess.STDOUT).decode()
        import re
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
        
        # 添加ModSecurity模块
        modsec_nginx_path = os.path.join(BUILD_DIR, "modsecurity-nginx")
        
        # 构建编译命令
        compile_cmd = f"./configure {configure_args} --add-dynamic-module={modsec_nginx_path}"
        subprocess.run(compile_cmd, shell=True, check=True)
        subprocess.run("make modules", shell=True, check=True)
        logger.info("编译Nginx ModSecurity模块成功")
        
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
    
    # 创建CRS目录
    crs_dir = "/etc/nginx/modsecurity-crs"
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
        logger.info("CRS文件已复制到/etc/nginx/modsecurity-crs/")
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
            logger.info("从Gitee镜像下载的CRS文件已复制到/etc/nginx/modsecurity-crs/")
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
                logger.info("从GitHub下载的CRS文件已复制到/etc/nginx/modsecurity-crs/")
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
    modsec_dir = "/etc/nginx/modsecurity"
    os.makedirs(modsec_dir, exist_ok=True)
    
    # 复制默认配置
    modsec_conf_src = os.path.join(BUILD_DIR, "modsecurity/modsecurity.conf-recommended")
    modsec_conf_dst = os.path.join(modsec_dir, "modsecurity.conf")
    shutil.copy(modsec_conf_src, modsec_conf_dst)
    
    # 修改配置以启用ModSecurity
    with open(modsec_conf_dst, 'r') as file:
        conf_content = file.read()
    
    # 启用ModSecurity
    conf_content = conf_content.replace('SecRuleEngine DetectionOnly', 'SecRuleEngine On')
    
    with open(modsec_conf_dst, 'w') as file:
        file.write(conf_content)
    
    # 创建include.conf配置
    include_conf = os.path.join(modsec_dir, "include.conf")
    with open(include_conf, 'w') as file:
        file.write("""# ModSecurity配置
Include "/etc/nginx/modsecurity/modsecurity.conf"
Include "/etc/nginx/modsecurity-crs/crs-setup.conf"
Include "/etc/nginx/modsecurity-crs/rules/*.conf"
""")
    
    # 创建Nginx ModSecurity配置
    modsec_nginx_conf = "/etc/nginx/conf.d/modsecurity.conf"
    with open(modsec_nginx_conf, 'w') as file:
        file.write("""# 在http块内加载ModSecurity模块
load_module modules/ngx_http_modsecurity_module.so;

# 在server块内启用ModSecurity
modsecurity on;
modsecurity_rules_file /etc/nginx/modsecurity/include.conf;
""")
    
    logger.info("ModSecurity配置完成，请将以下内容添加到您的Nginx配置中的http块:")
    logger.info("include /etc/nginx/conf.d/modsecurity.conf;")
    
    # 重启Nginx
    try:
        subprocess.run("nginx -t", shell=True, check=True)
        subprocess.run("systemctl restart nginx", shell=True, check=True)
        logger.info("Nginx已重启，ModSecurity现已启用")
    except subprocess.CalledProcessError:
        logger.error("Nginx配置测试失败，请手动检查配置")
        sys.exit(1)

# 主函数
def main():
    """主函数"""
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
        download_modsecurity()
        
        # 安装ModSecurity-nginx
        install_modsecurity_nginx()
        
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

if __name__ == "__main__":
    main()
