# ModSecurity安装脚本

这个模块化脚本用于在Linux服务器上自动安装和配置ModSecurity Web应用防火墙，支持同时安装在宝塔面板和标准Nginx环境。脚本采用模块化设计，优先使用国内镜像源，特别优化了对CentOS 7 EOL环境的支持。

## 前提条件

- 注册gitee.com
- 服务器git设置你的用户名和邮箱
```bash
git config --global user.name "Your Name"
git config --global user.email "your_email@example.com"
```
- 设置git存储
```bash
git config --global credential.helper store
```
> **脚本执行期间可能会多次提示输入GitHub/Gitee的用户名和密码**，请直接输入, 若想静默建议使用SSH密钥或GitHub/Gitee的个人访问令牌（PAT）进行身份验证。

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
- **增强的错误处理与容错**：
  - 所有模块导入使用try-except结构，确保安装流程不会因单个模块问题中断
  - Git仓库递归克隆，同时获取所有子模块
  - 针对浅克隆仓库的优化，使缓存更可靠
- **全面安全功能**：
  - 自动安装OWASP ModSecurity核心规则集(CRS)
  - 防范SQL注入、XSS、CSRF、文件包含等攻击
  - 可选的ClamAV防病毒集成
- **用户友好**：
  - 提供彩色输出和详细安装日志
  - 智能错误处理和问题诊断
  - 安装完成后自动重启Nginx服务

## 缓存系统

脚本集成了智能缓存系统，可显著提高安装速度并降低网络负载：

- **缓存结构**：所有下载文件按类型/版本/文件名目录结构存储
- **递归Git仓库缓存**：
  - 使用`--recursive`模式自动克隆主仓库及全部子模块
  - 使用适当的浅历史深度，减少内存占用且不影响功能
  - 防止浅克隆导致的缓存问题
- **智能文件缓存**：Nginx源码包等文件下载后自动缓存，支持断点续传
- **容错设计**：缓存出错时会自动回退到直接下载模式
- **默认安全**：缓存在`~/.modsecurity_cache`目录，不影响系统文件
- **智能校验**：基于版本缓存，自动检测更新

特别适合以下场景：

1. **网络不稳定环境**：网络经常中断的服务器可以利用缓存系统减少重复下载
2. **低速网络**：网络带宽受限的环境只需要下载一次即可
3. **批量部署**：需要在多台服务器上部署ModSecurity时，可先预热缓存或复用缓存目录
4. **产品环境**：在无法直接连接外网的服务器上，可以预先准备缓存文件

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

# 指定自定义缓存目录（默认为~/.modsecurity_cache）
./install_modsecurity.sh --cache-dir=/path/to/cache

# 禁用缓存功能，始终从源站下载
./install_modsecurity.sh --no-cache

# 清除缓存目录并重新下载所有文件
./install_modsecurity.sh --clear-cache

# 可以组合使用多个参数
./install_modsecurity.sh -f -v -r --cache-dir=/data/modsec_cache
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
    ├── downloader.py         # 文件下载模块
    ├── archive_handler.py    # 归档文件处理模块
    ├── git_manager.py        # Git仓库管理模块（递归克隆支持）
    ├── modsecurity_builder.py # ModSecurity构建模块
    ├── modules_manager.py    # 模块管理模块
    ├── nginx_integrator.py   # Nginx集成模块
    └── config_manager.py     # 配置管理模块
```

### 关键技术改进

1. **增强的错误处理机制**
   - 所有模块导入使用try-except结构，确保脚本健壮性
   - 关键模块导入失败时会提供明确的错误信息并优雅退出
   - 各组件间松耦合设计，降低单点故障风险

2. **Git仓库管理增强**
   - 使用`--recursive`参数一次性克隆主仓库及所有子模块
   - 浅克隆深度从1调整为2，平衡网络传输效率和功能完整性
   - 智能文件复制替代本地克隆，解决浅克隆仓库不支持`--local`参数的问题
   - 更智能化的子模块管理，自动检测子模块状态避免重复初始化
   - 主动将已初始化子模块的仓库备份到缓存，提高缓存效率

3. **网络资源获取增强**
   - ModSecurity-Nginx连接器下载支持多源切换，首选Gitee源
   - 实现URL故障转移机制，当主源失败自动切换到备用源
   - 增强的归档文件完整性验证，自动处理损坏文件
   - 智能目录检测，自动识别不同源解压的目录结构差异

4. **简化的安装流程**
   - 模块化设计降低维护难度，每个模块可独立测试
   - 错误处理更加完善，安装过程更可靠
   - 递归克隆减少了多步操作，提高效率

## 特殊环境支持

### CentOS 7 EOL 环境

本脚本特别优化了对CentOS 7 EOL环境的支持：

- **主动预检查机制**
  - 在安装前主动检测软件源配置状态
  - 自动检测"Could not retrieve mirrorlist"和"Cannot find a valid baseurl"等错误
  - 当检测到软件源问题时直接修复，无需等待安装失败

- **专用归档镜像配置**
  - 使用centos-vault归档镜像替代已经无法访问的常规镜像
  - 硬编码使用7.9.2009版本的归档镜像，这是CentOS 7的最终版本
  - 针对阿里云和清华大学等国内镜像源进行了优化配置

- **强化的错误处理**
  - 完善的备份/恢复机制，确保软件源配置文件的安全
  - 添加了EPEL仓库配置，确保关键依赖如GeoIP的安装
  - 实现了两阶段安装：先尝试官方源，失败后直接尝试国内镜像源

### 网络受限环境

针对网络受限环境的优化：

- 软件源预检查机制，检测并主动修复软件源问题
- 阿里云和清华大学镜像源自动切换
- 提供跳过依赖安装的选项，适用于无法访问外部网络的环境

### 宝塔面板兼容性

同时支持宝塔面板和标准Nginx环境：

- 自动检测宝塔面板并使用正确的配置路径
- 兼容宝塔面板的Nginx配置结构
