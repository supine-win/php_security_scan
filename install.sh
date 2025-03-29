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
curl -sSL https://raw.githubusercontent.com/supine-win/php_security_scan/main/main.py -o "$INSTALL_DIR/main.py"

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
