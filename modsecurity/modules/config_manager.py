#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ModSecurity配置管理模块
负责创建和配置ModSecurity规则
"""

import os
import re
import shutil
import subprocess
import logging
import glob
from pathlib import Path

# 导入相关模块
from modules.constants import CLAMAV_CONFIG, MODSEC_DEFAULT_CONFIG
from modules.system_detector import detect_bt_panel

logger = logging.getLogger('modsecurity_installer')

def create_modsec_dirs():
    """创建ModSecurity配置目录
    
    Returns:
        tuple: (主配置目录, 规则目录)
    """
    # 检查是否为宝塔面板环境
    is_bt = detect_bt_panel()
    
    # 确定配置目录
    if is_bt:
        modsec_conf_dir = "/www/server/nginx/conf/modsec"
        modsec_rules_dir = "/www/server/nginx/conf/modsec/rules"
    else:
        modsec_conf_dir = "/etc/nginx/modsec"
        modsec_rules_dir = "/etc/nginx/modsec/rules"
    
    # 创建目录
    os.makedirs(modsec_conf_dir, exist_ok=True)
    os.makedirs(modsec_rules_dir, exist_ok=True)
    
    logger.info(f"已创建ModSecurity配置目录: {modsec_conf_dir}")
    logger.info(f"已创建ModSecurity规则目录: {modsec_rules_dir}")
    
    return modsec_conf_dir, modsec_rules_dir

def create_default_config(config_dir, rules_dir):
    """创建ModSecurity默认配置
    
    Args:
        config_dir (str): 配置目录
        rules_dir (str): 规则目录
        
    Returns:
        bool: 是否成功创建配置
    """
    try:
        # 创建主配置文件
        main_conf_path = os.path.join(config_dir, "main.conf")
        main_conf_content = f"""# ModSecurity主配置
Include {config_dir}/modsecurity.conf
Include {config_dir}/crs-setup.conf
Include {rules_dir}/*.conf
"""
        
        with open(main_conf_path, 'w') as f:
            f.write(main_conf_content)
        
        logger.info(f"已创建主配置文件: {main_conf_path}")
        
        # 创建ModSecurity配置文件
        modsec_conf_path = os.path.join(config_dir, "modsecurity.conf")
        with open(modsec_conf_path, 'w') as f:
            f.write(MODSEC_DEFAULT_CONFIG)
        
        logger.info(f"已创建ModSecurity配置文件: {modsec_conf_path}")
        
        # 创建CRS配置文件
        crs_conf_path = os.path.join(config_dir, "crs-setup.conf")
        crs_conf_content = """# OWASP ModSecurity核心规则集配置

# 设置参数
SecRuleEngine On
SecRequestBodyAccess On
SecResponseBodyAccess On
SecResponseBodyMimeType text/plain text/html text/xml application/json
SecResponseBodyLimit 524288

# 请求体限制
SecRequestBodyLimit 13107200
SecRequestBodyNoFilesLimit 131072

# 调试级别
SecDebugLog /var/log/modsec_debug.log
SecDebugLogLevel 0

# 审计日志
SecAuditEngine RelevantOnly
SecAuditLogRelevantStatus "^(?:5|4(?!04))"
SecAuditLogParts ABIJDEFHZ
SecAuditLogType Serial
SecAuditLog /var/log/modsec_audit.log

# 自定义规则
SecRule REQUEST_HEADERS:Content-Type "application/json" "id:1000,phase:1,t:none,nolog,pass,ctl:requestBodyProcessor=JSON"
"""
        
        with open(crs_conf_path, 'w') as f:
            f.write(crs_conf_content)
        
        logger.info(f"已创建CRS配置文件: {crs_conf_path}")
        
        return True
    except Exception as e:
        logger.error(f"创建ModSecurity默认配置失败: {e}")
        return False

def create_basic_rules(rules_dir):
    """创建基本的ModSecurity规则
    
    Args:
        rules_dir (str): 规则目录
        
    Returns:
        bool: 是否成功创建规则
    """
    try:
        # 创建SQL注入防护规则
        sql_rules_path = os.path.join(rules_dir, "01_sql_injection.conf")
        sql_rules_content = """# SQL注入防护规则
SecRule REQUEST_COOKIES|REQUEST_COOKIES_NAMES|REQUEST_FILENAME|REQUEST_HEADERS|REQUEST_HEADERS_NAMES|REQUEST_BODY|REQUEST_BODY_NAMES|REQUEST_LINE|ARGS|ARGS_NAMES "@rx (?i:(?:select|;|\)|\s+having|\s+union\s+all|\)|\s+and|\s+or|\s+order))" \
    "id:1001,\
    phase:2,\
    block,\
    capture,\
    t:none,t:urlDecodeUni,\
    msg:'SQL Injection Attack',\
    logdata:'Matched Data: %{TX.0} found within %{MATCHED_VAR_NAME}: %{MATCHED_VAR}',\
    severity:'CRITICAL',\
    tag:'application-multi',\
    tag:'language-multi',\
    tag:'platform-multi',\
    tag:'attack-sqli',\
    setvar:'tx.sql_injection_score=+%{tx.critical_anomaly_score}',\
    setvar:'tx.anomaly_score=+%{tx.critical_anomaly_score}'"
"""
        
        with open(sql_rules_path, 'w') as f:
            f.write(sql_rules_content)
        
        logger.info(f"已创建SQL注入防护规则: {sql_rules_path}")
        
        # 创建XSS防护规则
        xss_rules_path = os.path.join(rules_dir, "02_xss.conf")
        xss_rules_content = """# XSS防护规则
SecRule REQUEST_COOKIES|REQUEST_COOKIES_NAMES|REQUEST_HEADERS|REQUEST_HEADERS_NAMES|REQUEST_BODY|REQUEST_BODY_NAMES|ARGS|ARGS_NAMES "@rx (?i:<script|<img|alert\\(|onerror\\=|javascript:|\\\\u|\\\\x|document\\.cookie)" \
    "id:1002,\
    phase:2,\
    block,\
    capture,\
    t:none,t:urlDecodeUni,\
    msg:'XSS Attack',\
    logdata:'Matched Data: %{TX.0} found within %{MATCHED_VAR_NAME}: %{MATCHED_VAR}',\
    severity:'CRITICAL',\
    tag:'application-multi',\
    tag:'language-multi',\
    tag:'platform-multi',\
    tag:'attack-xss',\
    setvar:'tx.xss_score=+%{tx.critical_anomaly_score}',\
    setvar:'tx.anomaly_score=+%{tx.critical_anomaly_score}'"
"""
        
        with open(xss_rules_path, 'w') as f:
            f.write(xss_rules_content)
        
        logger.info(f"已创建XSS防护规则: {xss_rules_path}")
        
        # 创建命令注入防护规则
        cmd_rules_path = os.path.join(rules_dir, "03_command_injection.conf")
        cmd_rules_content = """# 命令注入防护规则
SecRule REQUEST_COOKIES|REQUEST_COOKIES_NAMES|REQUEST_HEADERS|REQUEST_HEADERS_NAMES|REQUEST_BODY|REQUEST_BODY_NAMES|ARGS|ARGS_NAMES "@rx (?i:(?:;|\\||\\`|\\$\\(|\\$\\{|\\n|\\r|%0A|%0D))" \
    "id:1003,\
    phase:2,\
    block,\
    capture,\
    t:none,t:urlDecodeUni,\
    msg:'Command Injection Attack',\
    logdata:'Matched Data: %{TX.0} found within %{MATCHED_VAR_NAME}: %{MATCHED_VAR}',\
    severity:'CRITICAL',\
    tag:'application-multi',\
    tag:'language-multi',\
    tag:'platform-multi',\
    tag:'attack-rce',\
    setvar:'tx.rce_score=+%{tx.critical_anomaly_score}',\
    setvar:'tx.anomaly_score=+%{tx.critical_anomaly_score}'"
"""
        
        with open(cmd_rules_path, 'w') as f:
            f.write(cmd_rules_content)
        
        logger.info(f"已创建命令注入防护规则: {cmd_rules_path}")
        
        # 创建文件包含防护规则
        lfi_rules_path = os.path.join(rules_dir, "04_lfi.conf")
        lfi_rules_content = """# 文件包含防护规则
SecRule REQUEST_COOKIES|REQUEST_COOKIES_NAMES|REQUEST_HEADERS|REQUEST_HEADERS_NAMES|REQUEST_BODY|REQUEST_BODY_NAMES|ARGS|ARGS_NAMES "@rx (?i:(?:\\.\\.|etc/passwd|shadow|htpasswd|bin/bash|bin/sh))" \
    "id:1004,\
    phase:2,\
    block,\
    capture,\
    t:none,t:urlDecodeUni,\
    msg:'File Inclusion Attack',\
    logdata:'Matched Data: %{TX.0} found within %{MATCHED_VAR_NAME}: %{MATCHED_VAR}',\
    severity:'CRITICAL',\
    tag:'application-multi',\
    tag:'language-multi',\
    tag:'platform-multi',\
    tag:'attack-lfi',\
    setvar:'tx.lfi_score=+%{tx.critical_anomaly_score}',\
    setvar:'tx.anomaly_score=+%{tx.critical_anomaly_score}'"
"""
        
        with open(lfi_rules_path, 'w') as f:
            f.write(lfi_rules_content)
        
        logger.info(f"已创建文件包含防护规则: {lfi_rules_path}")
        
        # 创建PHP安全规则
        php_rules_path = os.path.join(rules_dir, "05_php_security.conf")
        php_rules_content = """# PHP安全规则
SecRule REQUEST_COOKIES|REQUEST_COOKIES_NAMES|REQUEST_HEADERS|REQUEST_HEADERS_NAMES|REQUEST_BODY|REQUEST_BODY_NAMES|ARGS|ARGS_NAMES "@rx (?i:(?:eval\\(|exec\\(|passthru|system\\(|shell_exec|phpinfo\\(|base64_decode|fopen|fwrite|file_put_contents))" \
    "id:1005,\
    phase:2,\
    block,\
    capture,\
    t:none,t:urlDecodeUni,\
    msg:'PHP Code Injection',\
    logdata:'Matched Data: %{TX.0} found within %{MATCHED_VAR_NAME}: %{MATCHED_VAR}',\
    severity:'CRITICAL',\
    tag:'application-multi',\
    tag:'language-php',\
    tag:'platform-multi',\
    tag:'attack-injection',\
    setvar:'tx.php_injection_score=+%{tx.critical_anomaly_score}',\
    setvar:'tx.anomaly_score=+%{tx.critical_anomaly_score}'"
"""
        
        with open(php_rules_path, 'w') as f:
            f.write(php_rules_content)
        
        logger.info(f"已创建PHP安全规则: {php_rules_path}")
        
        # 病毒扫描整合规则
        av_rules_path = os.path.join(rules_dir, "06_clamav.conf")
        with open(av_rules_path, 'w') as f:
            f.write(CLAMAV_CONFIG)
        
        logger.info(f"已创建ClamAV整合规则: {av_rules_path}")
        
        return True
    except Exception as e:
        logger.error(f"创建ModSecurity基本规则失败: {e}")
        return False

def configure_modsecurity(build_dir):
    """配置ModSecurity
    
    Args:
        build_dir (str): 构建目录
        
    Returns:
        bool: 是否成功配置
    """
    # 创建配置目录
    config_dir, rules_dir = create_modsec_dirs()
    
    # 创建默认配置
    if not create_default_config(config_dir, rules_dir):
        logger.error("创建ModSecurity默认配置失败")
        return False
    
    # 创建基本规则
    if not create_basic_rules(rules_dir):
        logger.error("创建ModSecurity基本规则失败")
        return False
    
    # 配置Nginx以使用ModSecurity
    # 这一步在nginx_integrator模块中已完成
    
    # 测试Nginx配置
    try:
        # 检查是否为宝塔面板环境
        is_bt = detect_bt_panel()
        
        if is_bt:
            nginx_bin = "/www/server/nginx/sbin/nginx"
        else:
            # 尝试查找nginx可执行文件
            try:
                nginx_bin = subprocess.check_output("which nginx", shell=True, universal_newlines=True).strip()
            except subprocess.CalledProcessError:
                nginx_bin = "/usr/sbin/nginx"  # 默认值
        
        logger.info(f"测试Nginx配置: {nginx_bin} -t")
        process = subprocess.run(f"{nginx_bin} -t", shell=True, 
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                              universal_newlines=True)
        
        # Nginx将配置测试信息输出到stderr
        if process.returncode == 0:
            logger.info("Nginx配置测试成功")
            return True
        else:
            logger.error(f"Nginx配置测试失败: {process.stderr}")
            return False
    except Exception as e:
        logger.error(f"测试Nginx配置时发生错误: {e}")
        return False

# 如果直接运行此脚本，则执行测试
if __name__ == "__main__":
    from modules.constants import setup_logger
    
    # 设置日志
    logger = setup_logger()
    
    # 配置ModSecurity
    if configure_modsecurity("/tmp"):
        logger.info("ModSecurity配置成功")
    else:
        logger.error("ModSecurity配置失败")
