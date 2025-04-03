#!/bin/bash
# ModSecurity 一键安装脚本 - 模块化版本
# 使用方法: curl -sSL https://gitee.com/supine-win/php_security_scan/raw/main/modsecurity/install_modsecurity.sh | sudo sh

set -e

echo "ModSecurity - 模块化一键安装版"

# 检查权限
if [ "$(id -u)" != "0" ]; then
    echo "错误: 此脚本需要root权限运行"
    echo "请使用 'sudo sh' 或 'sudo bash' 执行此脚本"
    exit 1
fi

# 创建临时目录
INSTALL_DIR=$(mktemp -d)
trap 'rm -rf "$INSTALL_DIR"' EXIT

echo "使用临时目录: $INSTALL_DIR"

# 创建模块目录结构
mkdir -p "$INSTALL_DIR/modules"

# 下载主脚本和模块
echo "正在下载安装脚本和模块..."

# 定义文件列表
FILES=(
    "install.py"
    "modules/__init__.py"
    "modules/constants.py"
    "modules/system_detector.py"
    "modules/repo_manager.py"
    "modules/repo_manager_ext.py"
    "modules/dependency_installer.py"
    "modules/modsecurity_compiler.py"
    "modules/nginx_integrator.py"
    "modules/config_manager.py"
)

# 下载源选项
DOWNLOAD_SOURCES=(
    "https://gitee.com/supine-win/php_security_scan/raw/main/modsecurity" # Gitee (国内速度快)
    "https://cdn.jsdelivr.net/gh/supine-win/php_security_scan@main/modsecurity" # JSDelivr CDN
    "https://raw.githubusercontent.com/supine-win/php_security_scan/main/modsecurity" # GitHub
)

download_file() {
    local file=$1
    local success=false
    
    for source in "${DOWNLOAD_SOURCES[@]}"; do
        echo "尝试从 $source 下载 $file..."
        local target_dir=$(dirname "$INSTALL_DIR/$file")
        mkdir -p "$target_dir"
        
        if curl -m 30 -sSL "$source/$file" -o "$INSTALL_DIR/$file" 2>/dev/null; then
            echo "✅ 成功下载: $file"
            success=true
            break
        else
            echo "❌ 从 $source 下载 $file 失败"
        fi
    done
    
    return $([ "$success" = true ] && echo 0 || echo 1)
}

# 下载所有文件
download_failed=false

for file in "${FILES[@]}"; do
    if ! download_file "$file"; then
        download_failed=true
        echo "⚠️ 警告: 无法下载 $file"
    fi
done

# 检查关键文件是否下载成功
if [ ! -f "$INSTALL_DIR/install.py" ] || [ ! -f "$INSTALL_DIR/modules/constants.py" ]; then
    echo "错误: 无法下载关键安装文件。请检查您的网络连接或手动下载。"
    echo "您可以直接访问 https://gitee.com/supine-win/php_security_scan 或 https://github.com/supine-win/php_security_scan 下载完整代码。"
    exit 1
fi

# 设置执行权限
chmod +x "$INSTALL_DIR/install.py"

# 检查Python3是否安装
if ! command -v python3 &> /dev/null; then
    echo "检测到系统中没有Python 3，正在尝试安装..."
    
    # 尝试安装Python 3
    if command -v apt-get &> /dev/null; then
        apt-get update && apt-get install -y python3
    elif command -v yum &> /dev/null; then
        yum install -y python3
    elif command -v dnf &> /dev/null; then
        dnf install -y python3
    else
        echo "错误: 无法自动安装Python 3。请手动安装后重试。"
        exit 1
    fi
    
    # 再次检查安装结果
    if ! command -v python3 &> /dev/null; then
        echo "错误: Python 3安装失败。请手动安装后重试。"
        exit 1
    fi
fi

# 检查必要的其他依赖
# 检查Git
if ! command -v git &> /dev/null; then
    echo "检测到系统中没有Git，正在尝试安装..."
    
    if command -v apt-get &> /dev/null; then
        apt-get update && apt-get install -y git
    elif command -v yum &> /dev/null; then
        yum install -y git
    elif command -v dnf &> /dev/null; then
        dnf install -y git
    else
        echo "警告: 无法自动安装Git。脚本可能会失败。"
    fi
fi

# 检查其他基本工具
if ! command -v curl &> /dev/null; then
    echo "检测到系统中没有curl，正在尝试安装..."
    
    if command -v apt-get &> /dev/null; then
        apt-get update && apt-get install -y curl
    elif command -v yum &> /dev/null; then
        yum install -y curl
    elif command -v dnf &> /dev/null; then
        dnf install -y curl
    else
        echo "警告: 无法自动安装curl。脚本可能会失败。"
    fi
fi

# 创建日志目录
LOG_DIR="/var/log/modsecurity_installer"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/install_$(date +%Y%m%d%H%M%S).log"

# 开始安装
echo "开始安装ModSecurity..."
echo "日志文件将保存在: $LOG_FILE"

# 执行Python脚本
echo "开始执行安装..."

# 将命令行参数传递给Python脚本
echo "命令行参数: $@"
cd "$INSTALL_DIR"
python3 "$INSTALL_DIR/install.py" --log-file="$LOG_FILE" "$@"

# 检查执行结果
if [ $? -eq 0 ]; then
    echo "✅ ModSecurity安装完成!"
    echo "详细日志文件: $LOG_FILE"
    echo "
您可能需要重新启动Nginx服务器以应用更改:"
    echo "  systemctl restart nginx"
    echo "
或者检查您的Nginx配置:"
    echo "  nginx -t"
    echo "
默认规则已配置，包括:"
    echo "- SQL注入防护"
    echo "- XSS防护"
    echo "- 命令注入防护"
    echo "- 文件包含防护"
    echo "- PHP安全规则"
    echo "
配置文件位置:"
    echo "- 主配置: /etc/nginx/modsec/main.conf"
    echo "- 规则目录: /etc/nginx/modsec/rules/"
    echo "
宝塔面板环境配置文件位置:"
    echo "- 主配置: /www/server/nginx/conf/modsec/main.conf"
    echo "- 规则目录: /www/server/nginx/conf/modsec/rules/"
else
    echo "⚠️ ModSecurity安装过程中出现错误。"
    echo "请查看日志文件: $LOG_FILE"
    echo "或者访问 https://gitee.com/supine-win/php_security_scan 获取帮助。"
    exit 1
fi

exit 0
