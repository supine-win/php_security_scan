# ModSecurity安装脚本

这个模块化脚本用于在Linux服务器上自动安装和配置ModSecurity Web应用防火墙，支持同时安装在宝塔面板和标准Nginx环境。脚本采用模块化设计，优先使用国内镜像源，特别优化了对CentOS 7 EOL环境的支持。

## 支持的操作系统

- CentOS 7/8/9
- Rocky Linux 8/9
- AlmaLinux 8/9
- Ubuntu 20.04/22.04
- Debian 10/11

## 脚本特点

- **模块化架构**：采用Python模块化设计，易于维护和扩展
- **增强的系统兼容性**：
  - 自动检测服务器系统类型及版本
  - 特别优化的CentOS 7 EOL环境支持
  - 兼容标准Nginx和宝塔面板环境
- **智能镜像源管理**：
  - 自动检测并修复软件源配置问题
  - 针对CentOS EOL版本使用vault归档镜像
  - 在网络问题时自动切换到国内镜像源
- **全面安全功能**：
  - 自动安装OWASP ModSecurity核心规则集(CRS)
  - 防范SQL注入、XSS、CSRF、文件包含等攻击
  - 可选的ClamAV防病毒集成
- **用户友好**：
  - 提供彩色输出和详细安装日志
  - 智能错误处理和问题诊断
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
./install_modsecurity.sh --force
# 或者简写形式
./install_modsecurity.sh -f

# 显示详细的安装日志信息
./install_modsecurity.sh --verbose
# 或者简写形式
./install_modsecurity.sh -v

# 跳过依赖安装，适用于系统无法连接到网络的情况
./install_modsecurity.sh --skip-deps
# 或者简写形式
./install_modsecurity.sh -s

# 不重启Nginx服务
./install_modsecurity.sh --no-restart
# 或者简写形式
./install_modsecurity.sh -n

# 自动修复软件源问题（针对CentOS EOL版本）
./install_modsecurity.sh --fix-repo
# 或者简写形式
./install_modsecurity.sh -r

# 可以组合使用多个参数
./install_modsecurity.sh -f -v -r
```

如果使用一键安装脚本，您可以如下传递参数：

```bash
# 强制更新模式
curl -sSL https://gitee.com/supine-win/php_security_scan/raw/main/modsecurity/install_modsecurity.sh | bash -s -- -f

# 详细模式
curl -sSL https://gitee.com/supine-win/php_security_scan/raw/main/modsecurity/install_modsecurity.sh | bash -s -- -v

# 在CentOS 7 EOL环境中自动修复仓库
curl -sSL https://gitee.com/supine-win/php_security_scan/raw/main/modsecurity/install_modsecurity.sh | bash -s -- -r

# 同时启用强制更新和详细模式
curl -sSL https://gitee.com/supine-win/php_security_scan/raw/main/modsecurity/install_modsecurity.sh | bash -s -- -f -v

# 在网络问题环境中使用
curl -sSL https://gitee.com/supine-win/php_security_scan/raw/main/modsecurity/install_modsecurity.sh | bash -s -- -r -v
```

## 安装后验证

安装完成后，可以使用以下命令验证ModSecurity是否正常工作：

```bash
# 测试XSS防护 (使用URL编码的参数避免curl自动转义)
curl -I "http://localhost/?param=%3Cscript%3E"

# 如果返回403状态码，表示ModSecurity成功拦截攻击
```

## 模块化架构

新版本采用模块化设计，由以下组件组成：

```
modsecurity/
├── install.py                # 主安装脚本 
├── install_modsecurity.sh    # Shell入口脚本
└── modules/
    ├── __init__.py           # 模块包初始化
    ├── constants.py          # 全局常量和配置
    ├── system_detector.py    # 系统检测模块
    ├── repo_manager.py       # 软件源管理基础模块
    ├── repo_manager_ext.py   # 软件源管理扩展模块（CentOS EOL支持）
    ├── dependency_installer.py # 依赖安装模块
    ├── modsecurity_compiler.py # ModSecurity编译模块
    ├── nginx_integrator.py   # Nginx集成模块
    └── config_manager.py     # 配置管理模块
```

## 特殊环境支持

### CentOS 7 EOL 环境

本脚本特别优化了对CentOS 7 EOL环境的支持：

- 自动检测CentOS 7 EOL状态
- 使用centos-vault归档镜像替代常规镜像
- 自动修复"Could not retrieve mirrorlist"和"Cannot find a valid baseurl"错误
- 支持多个国内镜像源，确保依赖安装稳定性

### 网络受限环境

针对网络受限环境的优化：

- 软件源预检查机制，检测并主动修复软件源问题
- 阿里云和清华大学镜像源自动切换
- 提供跳过依赖安装的选项，适用于无法访问外部网络的环境

### 宝塔面板兼容性

同时支持宝塔面板和标准Nginx环境：

- 自动检测宝塔面板并使用正确的配置路径
- 兼容宝塔面板的Nginx配置结构
- 支持同时安装在多环境中

## 安装细节

脚本安装的组件包括：
- ModSecurity核心库 v3.0.8
- ModSecurity-nginx连接器 v1.0.3
- OWASP ModSecurity核心规则集(CRS) v3.3.4
- Nginx集成配置

安装位置：
- ModSecurity模块：标准环境为`/etc/nginx/modules/ngx_http_modsecurity_module.so`，宝塔环境为`/www/server/nginx/modules/ngx_http_modsecurity_module.so`
- 规则配置目录：`/etc/nginx/modsecurity/`（标准环境）或`/www/server/nginx/conf/modsecurity/`（宝塔环境）
- OWASP CRS规则：`/etc/nginx/modsecurity-crs/`（标准环境）或`/www/server/nginx/conf/modsecurity-crs/`（宝塔环境）
- Nginx配置：`/etc/nginx/conf.d/modsecurity.conf`（标准环境）或`/www/server/panel/vhost/nginx/modsecurity.conf`（宝塔环境）

## 调整和故障排除

### 常规调整

如需调整规则，请编辑：`/etc/nginx/modsecurity/modsecurity.conf`或宝塔环境下的对应文件

详细安装日志位于：`/var/log/modsecurity_install.log`

### 软件源问题

如果在CentOS系统遇到软件源问题，可以尝试以下命令：

```bash
./install_modsecurity.sh --fix-repo --verbose
```

### 依赖问题

如果特定依赖无法安装，可以查看日志确定缺失的依赖，然后手动安装：

```bash
# CentOS系统
yum install -y <依赖包名>

# Debian/Ubuntu系统
apt-get install -y <依赖包名>
```

然后使用`--skip-deps`选项继续安装：

```bash
./install_modsecurity.sh --skip-deps
```
