#!/bin/bash
# PHP Security Scanner 一键运行脚本
# 使用方法: curl -sSL https://raw.githubusercontent.com/supine-win/php_security_scan/main/run.sh | sh -s -- /path/to/php/directory

set -e

# 检查参数
if [ $# -lt 1 ]; then
    echo "使用方法: curl -sSL https://gitee.com/supine-win/php_security_scan/raw/main/run.sh | sh -s -- /path/to/php/directory [options]"
    echo "请提供要扫描的PHP目录路径"
    exit 1
fi

SCAN_DIR="$1"
shift  # 移除第一个参数，剩余的作为选项传递

echo "PHP Security Scanner - 一键运行版"
echo "扫描目录: $SCAN_DIR"

# 创建临时目录
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

# 下载脚本
echo "正在下载扫描脚本..."

# 尝试不同的备选下载源
download_success=false

# 尝试主要下载源（Gitee - 国内速度更快）
echo "尝试下载源 1/3: Gitee..."
curl -m 30 -sSL https://gitee.com/supine-win/php_security_scan/raw/main/main.py -o "$TEMP_DIR/main.py" && download_success=true

# 如果失败，尝试JSDelivr CDN
if [ "$download_success" != "true" ]; then
    echo "下载失败，尝试备用源 2/3: JSDelivr CDN..."
    curl -m 30 -sSL https://cdn.jsdelivr.net/gh/supine-win/php_security_scan@main/main.py -o "$TEMP_DIR/main.py" && download_success=true
fi

# 如果仍然失败，尝试GitHub源
if [ "$download_success" != "true" ]; then
    echo "下载失败，尝试备用源 3/3: GitHub..."
    curl -m 30 -sSL https://raw.githubusercontent.com/supine-win/php_security_scan/main/main.py -o "$TEMP_DIR/main.py" && download_success=true
fi

# 检查下载是否成功
if [ "$download_success" != "true" ]; then
    echo "错误: 无法下载扫描脚本。请检查您的网络连接或手动下载脚本。"
    echo "您可以直接访问 https://gitee.com/supine-win/php_security_scan 或 https://github.com/supine-win/php_security_scan 下载完整代码。"
    exit 1
fi

chmod +x "$TEMP_DIR/main.py"

# 检查是否运行在交互式终端
is_tty=false
if [ -t 0 ]; then
    is_tty=true
fi

# 执行扫描
echo "开始扫描..."

# 如果不是交互式终端且没有指定--non-interactive参数
if [ "$is_tty" = false ] && [[ ! " $* " =~ " --non-interactive " ]]; then
    echo "[注意] 在非交互式环境中运行，自动添加--non-interactive选项，使用默认特征。"
    echo "[提示] 如需指定特征，请使用-p参数，如: -p 1,3,5"
    python3 "$TEMP_DIR/main.py" "$SCAN_DIR" --non-interactive "$@"
else
    python3 "$TEMP_DIR/main.py" "$SCAN_DIR" "$@"
fi

echo "扫描完成!"
