#!/bin/bash
# PHP Security Scanner 安装脚本
# 使用方法: curl -sSL https://raw.githubusercontent.com/supine-win/php_security_scan/main/install.sh | sh

set -e

echo "正在安装 PHP Security Scanner..."

# 创建安装目录
INSTALL_DIR="$HOME/.php_security_scan"
mkdir -p "$INSTALL_DIR"

# 下载主脚本文件
echo "正在下载脚本文件..."

# 尝试不同的备选下载源
download_success=false

# 尝试主要下载源
echo "尝试下载源 1/3: GitHub..."
curl -m 30 -sSL https://raw.githubusercontent.com/supine-win/php_security_scan/main/main.py -o "$INSTALL_DIR/main.py" && download_success=true

# 如果失败，尝试备用镜像
if [ "$download_success" != "true" ]; then
    echo "下载失败，尝试备用源 2/3..."
    curl -m 30 -sSL https://cdn.jsdelivr.net/gh/supine-win/php_security_scan@main/main.py -o "$INSTALL_DIR/main.py" && download_success=true
fi

# 如果仍然失败，尝试Gitee镜像
if [ "$download_success" != "true" ]; then
    echo "下载失败，尝试备用源 3/3..."
    curl -m 30 -sSL https://gitee.com/supine-win/php_security_scan/raw/main/main.py -o "$INSTALL_DIR/main.py" && download_success=true
fi

# 检查下载是否成功
if [ "$download_success" != "true" ]; then
    echo "错误: 无法下载扫描脚本。请检查您的网络连接或手动下载脚本。"
    echo "您可以直接访问 https://github.com/supine-win/php_security_scan 下载完整代码。"
    rm -rf "$INSTALL_DIR"
    exit 1
fi

# 设置执行权限
chmod +x "$INSTALL_DIR/main.py"

# 创建可执行的命令行工具
BIN_DIR="$HOME/bin"
mkdir -p "$BIN_DIR"

# 写入启动器脚本
cat > "$BIN_DIR/php-security-scan" <<EOF
#!/bin/bash
python3 "$INSTALL_DIR/main.py" "\$@"
EOF

# 设置启动器脚本权限
chmod +x "$BIN_DIR/php-security-scan"

# 检查 PATH 中是否包含 ~/bin
if [[ ":$PATH:" != *":$HOME/bin:"* ]]; then
    echo "请将 $HOME/bin 添加到您的 PATH 中，方法是在 ~/.bashrc 或 ~/.zshrc 中添加以下行:"
    echo "export PATH=\"\$HOME/bin:\$PATH\""
    echo "然后运行: source ~/.bashrc 或 source ~/.zshrc"
else
    echo "安装完成！您现在可以使用 'php-security-scan' 命令运行扫描工具。"
fi

echo ""
echo "使用方法:"
echo "php-security-scan /path/to/php/directory"
echo ""
echo "示例:"
echo "php-security-scan /var/www/html"
echo ""
echo "可选参数:"
echo "php-security-scan /var/www/html -o my_scan_results.csv"
