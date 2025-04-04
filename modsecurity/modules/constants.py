#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
常量和全局配置模块
定义所有ModSecurity安装脚本使用的常量和默认配置
"""

import os
import sys
import logging

# 版本信息
MODSEC_VERSION = "3.0.14"
MODSEC_CONNECTOR_VERSION = "1.0.3"
NGINX_VERSION = "1.24.0"  # 默认Nginx版本
OWASP_CRS_VERSION = "4.13.0"

# 目录设置
DEFAULT_BUILD_DIR = "/tmp/modsecurity_build"
DEFAULT_LOG_FILE = "modsecurity_install.log"

# 缓存设置
DEFAULT_CACHE_DIR = os.path.expanduser("~/.modsecurity_cache")
CACHE_GIT_DIR = os.path.join(DEFAULT_CACHE_DIR, "git")  # Git仓库缓存目录
CACHE_FILE_DIR = os.path.join(DEFAULT_CACHE_DIR, "files")  # 文件缓存目录

# 宝塔面板路径
BT_NGINX_PATH = "/www/server/nginx"
BT_VHOST_PATH = "/www/server/panel/vhost/nginx"

# 标准Nginx路径
STD_NGINX_PATH = "/usr/local/nginx"
STD_CONF_PATH = "/etc/nginx/conf.d"

# 下载链接
MODSEC_DOWNLOAD_URL = f"https://github.com/SpiderLabs/ModSecurity/releases/download/v{MODSEC_VERSION}/modsecurity-v{MODSEC_VERSION}.tar.gz"
# 提供两个连接器下载链接，中国服务器建议使用Gitee
# Gitee镜像版本
MODSEC_CONNECTOR_GITEE_URL = f"https://gitee.com/supine-win/ModSecurity-nginx/archive/refs/tags/modsecurity-nginx-v{MODSEC_CONNECTOR_VERSION}.tar.gz"
# GitHub原始版本
MODSEC_CONNECTOR_GITHUB_URL = f"https://github.com/SpiderLabs/ModSecurity-nginx/releases/download/v{MODSEC_CONNECTOR_VERSION}/modsecurity-nginx-v{MODSEC_CONNECTOR_VERSION}.tar.gz"
# 默认使用Gitee版本
MODSEC_CONNECTOR_URL = MODSEC_CONNECTOR_GITEE_URL
OWASP_CRS_URL = f"https://github.com/coreruleset/coreruleset/archive/v{OWASP_CRS_VERSION}.tar.gz"
NGINX_DOWNLOAD_URL = f"https://nginx.org/download/nginx-{NGINX_VERSION}.tar.gz"

# Git仓库链接
GIT_REPOS = {
    "github": {
        "modsecurity": "https://github.com/SpiderLabs/ModSecurity.git",
        "connector": "https://github.com/owasp-modsecurity/ModSecurity-nginx.git",
        "crs": "https://github.com/coreruleset/coreruleset.git"
    },
    "gitee": {
        "modsecurity": "https://gitee.com/supine-win/ModSecurity.git",
        "connector": "https://gitee.com/supine-win/ModSecurity-nginx.git",
        "crs": "https://gitee.com/supine-win/coreruleset.git"
    }
}

# 工作目录
WORK_DIR = "/tmp/modsecurity_build"

# 镜像源配置
MIRRORS = {
    "aliyun": {
        "name": "阿里云",
        "centos": "https://mirrors.aliyun.com/centos",
        "centos_vault": "https://mirrors.aliyun.com/centos-vault",
        "epel": "https://mirrors.aliyun.com/epel"
    },
    "tsinghua": {
        "name": "清华大学",
        "centos": "https://mirrors.tuna.tsinghua.edu.cn/centos",
        "centos_vault": "https://mirrors.tuna.tsinghua.edu.cn/centos-vault",
        "epel": "https://mirrors.tuna.tsinghua.edu.cn/epel"
    }
}

# CentOS EOL版本配置
CENTOS_EOL_VERSIONS = {
    "7": "7.9.2009",  # CentOS 7最终版本
    "8": "8.5.2111"   # CentOS 8最终版本
}

# 依赖包列表
DEPENDENCIES = {
    "rhel": [
        "git", "gcc", "gcc-c++", "make", "automake", "autoconf", "libtool",
        "pcre-devel", "pcre2-devel", "libxml2-devel", "curl-devel", "zlib-devel",
        "GeoIP-devel", "yajl-devel", "doxygen", "lmdb-devel"
    ],
    "debian": [
        "git", "build-essential", "libpcre3-dev", "libpcre2-dev", "libxml2-dev", "libcurl4-openssl-dev",
        "zlib1g-dev", "libyajl-dev", "doxygen", "liblmdb-dev", "liblua5.2-dev"
    ]
}

# 日志配置
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
LOG_LEVEL = logging.INFO

# ModSecurity默认配置
MODSEC_DEFAULT_CONFIG = """# ModSecurity配置

# -- 规则引擎模式 --
# 启用ModSecurity，使用检测模式
# 可选值: On, Off, DetectionOnly
SecRuleEngine On

# -- 请求体处理 --
# 允许ModSecurity检查请求体
SecRequestBodyAccess On

# 限制请求体大小
SecRequestBodyLimit 13107200
SecRequestBodyNoFilesLimit 131072

# 请求体MIME类型
SecRequestBodyLimitAction Reject
SecRequestBodyJsonDepthLimit 512

# -- 响应体处理 --
# 启用响应体访问
SecResponseBodyAccess On
SecResponseBodyMimeType text/plain text/html text/xml application/json application/xml

# 限制响应体大小
SecResponseBodyLimit 1048576
SecResponseBodyLimitAction ProcessPartial

# -- 调试日志 --
SecDebugLog /var/log/modsec_debug.log
SecDebugLogLevel 0

# -- 审计日志 --
SecAuditEngine RelevantOnly
SecAuditLogRelevantStatus "^(?:5|4(?!04))"
SecAuditLogParts ABIJDEFHZ
SecAuditLogType Serial
SecAuditLog /var/log/modsec_audit.log

# -- 数据文件 --
SecTmpDir /tmp
SecDataDir /tmp

# -- 规则配置 --
SecRulePriority 1 40000
SecRulePriority 2 30000
SecRulePriority 3 20000
SecRulePriority 4 10000
SecRulePriority 5 0

# -- 其他设置 --
SecArgumentSeparator &
SecCookieFormat 0
SecUnicodeMapFile unicode.mapping 20127

# -- 默认动作 --
SecDefaultAction "phase:1,log,auditlog,pass"
SecDefaultAction "phase:2,log,auditlog,pass"

# -- 请求体解析器 --
SecRule REQUEST_HEADERS:Content-Type "^(?:application(?:/soap\\+|/)|text/)xml" \
     "id:200000,phase:1,t:none,t:lowercase,pass,nolog,ctl:requestBodyProcessor=XML"

SecRule REQUEST_HEADERS:Content-Type "^application/json" \
     "id:200001,phase:1,t:none,t:lowercase,pass,nolog,ctl:requestBodyProcessor=JSON"

SecRule REQUEST_HEADERS:Content-Type "^application/x-www-form-urlencoded" \
     "id:200002,phase:1,t:none,t:lowercase,pass,nolog,ctl:requestBodyProcessor=URLENCODED"
"""

# ClamAV集成配置
CLAMAV_CONFIG = """# ClamAV防病毒扫描集成
SecRule FILES_TMPNAMES "@inspectFile /usr/bin/clamdscan" \
    "id:1010,phase:2,t:none,block,msg:'已检测到恶意软件/病毒',tag:'VIRUS',severity:'2'"
"""

# 初始化日志记录器
def setup_logger(log_file=None, verbose=False):
    """
    设置日志记录器
    
    Args:
        log_file (str): 日志文件路径
        verbose (bool): 是否输出详细日志
    
    Returns:
        logging.Logger: 配置好的日志记录器
    """
    level = logging.DEBUG if verbose else LOG_LEVEL
    
    # 创建日志记录器
    logger = logging.getLogger('modsecurity_installer')
    logger.setLevel(level)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_formatter = logging.Formatter(LOG_FORMAT)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # 如果提供了日志文件，添加文件处理器
    if log_file:
        # 确保日志目录存在
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_formatter = logging.Formatter(LOG_FORMAT)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger
