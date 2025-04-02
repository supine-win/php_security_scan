# ModSecurity安装脚本

这个脚本用于在安装了宝塔面板和Nginx的Linux服务器上自动安装和配置ModSecurity Web应用防火墙。脚本优先使用Gitee镜像源，适合国内服务器环境。

## 支持的操作系统

- CentOS 7/8/9
- Rocky Linux 8/9
- AlmaLinux 8/9
- Ubuntu 20.04/22.04
- Debian 10/11

## 脚本特点

- 自动检测服务器系统及宝塔环境
- 优先使用Gitee镜像源，适合国内服务器
- 自动安装OWASP ModSecurity核心规则集(CRS)
- 配置Nginx使用ModSecurity防火墙
- 防范常见Web攻击：SQL注入、XSS、CSRF、文件包含等
- 提供彩色输出和详细安装日志
- 安装完成后自动重启Nginx服务

## 使用方法

只需要一行命令，就可以从远程仓库下载并运行安装脚本：

```bash
# 使用Gitee源（推荐国内服务器）
curl -sSL https://gitee.com/supine-win/php_security_scan/raw/main/modsecurity/install_modsecurity.sh | bash

# 或者使用GitHub源
curl -sSL https://raw.githubusercontent.com/supine-win/php_security_scan/main/modsecurity/install_modsecurity.sh | bash
```

您也可以手动下载并运行脚本：

```bash
# 下载脚本
wget https://gitee.com/supine-win/php_security_scan/raw/main/modsecurity/install_modsecurity.sh

# 添加执行权限
chmod +x install_modsecurity.sh

# 执行安装
./install_modsecurity.sh
```

## 命令行参数

脚本支持以下命令行参数：

```bash
# 强制重新编译ModSecurity模块，即使已存在也会更新
python3 install_modsecurity.py -f
# 或者
python3 install_modsecurity.py --force

# 显示详细的安装日志信息
python3 install_modsecurity.py -v
# 或者
python3 install_modsecurity.py --verbose

# 跳过依赖安装，适用于系统无法连接到网络的情况
python3 install_modsecurity.py -s
# 或者
python3 install_modsecurity.py --skip-deps

# 可以组合使用多个参数
python3 install_modsecurity.py -f -v -s
```

如果使用一键安装脚本，您可以如下传递参数：

```bash
# 强制更新模式
curl -sSL https://gitee.com/supine-win/php_security_scan/raw/main/modsecurity/install_modsecurity.sh | bash -s -- -f

# 详细模式
curl -sSL https://gitee.com/supine-win/php_security_scan/raw/main/modsecurity/install_modsecurity.sh | bash -s -- -v

# 跳过依赖安装，适用于无法连接到网络或DNS解析失败的服务器
curl -sSL https://gitee.com/supine-win/php_security_scan/raw/main/modsecurity/install_modsecurity.sh | bash -s -- -s

# 同时启用强制更新和详细模式
curl -sSL https://gitee.com/supine-win/php_security_scan/raw/main/modsecurity/install_modsecurity.sh | bash -s -- -f -v

# 组合所有选项
curl -sSL https://gitee.com/supine-win/php_security_scan/raw/main/modsecurity/install_modsecurity.sh | bash -s -- -f -v -s
```

## 安装后验证

安装完成后，可以使用以下命令验证ModSecurity是否正常工作：

```bash
# 测试XSS防护 (使用URL编码的参数避免curl自动转义)
curl -I "http://localhost/?param=%3Cscript%3E"

# 如果返回403状态码，表示ModSecurity成功拦截攻击
```

## 安装细节

脚本安装的组件包括：
- ModSecurity核心库
- ModSecurity-nginx连接器
- OWASP ModSecurity核心规则集(CRS)
- Nginx集成配置

安装位置：
- ModSecurity模块：标准环境为`/etc/nginx/modules/ngx_http_modsecurity_module.so`，宝塔环境为`/www/server/nginx/modules/ngx_http_modsecurity_module.so`
- 规则配置目录：`/etc/nginx/modsecurity/`
- OWASP CRS规则：`/etc/nginx/modsecurity-crs/`
- Nginx配置：`/etc/nginx/conf.d/modsecurity.conf`

## 调整和故障排除

如需调整规则，请编辑：`/etc/nginx/modsecurity/modsecurity.conf`
详细安装日志会在安装完成时显示其完整路径，通常在临时目录中
