#!/bin/bash
# PHP Security Scanner 一键运行脚本
# 使用方法: curl -sSL https://raw.githubusercontent.com/supine-win/php_security_scan/main/run.sh | sh -s -- /path/to/php/directory

set -e

# 检查参数
if [ $# -lt 1 ]; then
    echo "使用方法: curl -sSL https://raw.githubusercontent.com/supine-win/php_security_scan/main/run.sh | sh -s -- /path/to/php/directory [options]"
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
curl -sSL https://raw.githubusercontent.com/supine-win/php_security_scan/main/main.py -o "$TEMP_DIR/main.py"
chmod +x "$TEMP_DIR/main.py"

# 执行扫描
echo "开始扫描..."
python3 "$TEMP_DIR/main.py" "$SCAN_DIR" "$@"

echo "扫描完成!"
