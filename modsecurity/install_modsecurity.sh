#!/bin/bash
# ModSecurity 一键安装脚本
# 使用方法: curl -sSL https://gitee.com/supine-win/php_security_scan/raw/main/modsecurity/install_modsecurity.sh | sudo sh

set -e

echo "ModSecurity - 一键安装版"

# 检查权限
if [ "$(id -u)" != "0" ]; then
    echo "错误: 此脚本需要root权限运行"
    echo "请使用 'sudo sh' 或 'sudo bash' 执行此脚本"
    exit 1
fi

# 创建临时目录
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

# 下载脚本
echo "正在下载安装脚本..."

# 尝试不同的备选下载源
download_success=false

# 尝试主要下载源（Gitee - 国内速度更快）
echo "尝试下载源 1/3: Gitee..."
curl -m 30 -sSL https://gitee.com/supine-win/php_security_scan/raw/main/modsecurity/install_modsecurity.py -o "$TEMP_DIR/install_modsecurity.py" && download_success=true

# 如果失败，尝试JSDelivr CDN
if [ "$download_success" != "true" ]; then
    echo "下载失败，尝试备用源 2/3: JSDelivr CDN..."
    curl -m 30 -sSL https://cdn.jsdelivr.net/gh/supine-win/php_security_scan@main/modsecurity/install_modsecurity.py -o "$TEMP_DIR/install_modsecurity.py" && download_success=true
fi

# 如果仍然失败，尝试GitHub源
if [ "$download_success" != "true" ]; then
    echo "下载失败，尝试备用源 3/3: GitHub..."
    curl -m 30 -sSL https://raw.githubusercontent.com/supine-win/php_security_scan/main/modsecurity/install_modsecurity.py -o "$TEMP_DIR/install_modsecurity.py" && download_success=true
fi

# 检查下载是否成功
if [ "$download_success" != "true" ]; then
    echo "错误: 无法下载安装脚本。请检查您的网络连接或手动下载脚本。"
    echo "您可以直接访问 https://gitee.com/supine-win/php_security_scan 或 https://github.com/supine-win/php_security_scan 下载完整代码。"
    exit 1
fi

chmod +x "$TEMP_DIR/install_modsecurity.py"

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

# 开始安装
echo "开始安装ModSecurity..."

# 检查必要的其他依赖包
echo "检查并安装必要的依赖包..."

# 执行Python脚本
echo "开始执行安装..."

# 将命令行参数传递给Python脚本
echo "命令行参数: $@"
python3 "$TEMP_DIR/install_modsecurity.py" "$@"

# 检查执行结果
if [ $? -eq 0 ]; then
    echo "✅ ModSecurity安装完成!"
    echo "请查看 $TEMP_DIR/modsecurity_install.log 了解详细日志信息。"
    echo "
您可能需要重新启动Nginx服务器以应用更改:"
    echo "  systemctl restart nginx"
    echo "
或者检查您的Nginx配置:"
    echo "  nginx -t"
else
    echo "⚠️ ModSecurity安装过程中出现错误。"
    echo "请查看 $TEMP_DIR/modsecurity_install.log 了解详细日志信息。"
    echo "或者访问 https://gitee.com/supine-win/php_security_scan 获取帮助。"
    exit 1
fi

exit 0
