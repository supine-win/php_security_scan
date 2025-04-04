# PHP安全工具集

这是一个集成了多个PHP安全工具的项目，目前包含两个主要组件：PHP安全扫描器和ModSecurity安装辅助工具。

## 代码仓库

- GitHub: [https://github.com/supine-win/php_security_scan](https://github.com/supine-win/php_security_scan)
- Gitee（国内镜像）: [https://gitee.com/supine-win/php_security_scan](https://gitee.com/supine-win/php_security_scan)

## 项目结构

本项目分为两个主要模块，每个模块都有独立的功能和使用方法：

1. **[PHP安全扫描器](php_scanner/)** - 扫描PHP文件中的安全漏洞和被篡改的迹象
2. **[ModSecurity安装工具](modsecurity/)** - 在宝塔环境下安装和配置ModSecurity Web应用防火墙

请根据您的需求点击相应的模块查看详细信息。

## 各模块功能简介

### PHP安全扫描器

PHP安全扫描器可以递归扫描指定目录中的所有PHP文件，检测多种安全漏洞和篡改特征，包括：

- 编码后的命令执行（如base64_decode后执行）
- 命令注入漏洞
- SQL注入漏洞
- 可疑的文件操作
- 远程文件包含
- 隐藏的后门代码
- 多种编码混淆技术
- 更多高级威胁检测规则

详细使用方法请查看 [PHP安全扫描器文档](php_scanner/README.md)。

### ModSecurity安装工具

ModSecurity安装工具可以在安装了宝塔面板和Nginx的Linux服务器上自动安装和配置ModSecurity Web应用防火墙，特点包括：

- **模块化设计**：完全重构的架构，提供更好的可维护性和扩展性
- **多平台支持**：兼容CentOS 7/8/9、Ubuntu 20.04/22.04、Debian 10/11等多种系统
- **CentOS 7 EOL特别支持**：自动处理软件源问题，使用vault归档镜像
- **增强Git仓库管理**：智能文件复制和子模块状态检测机制
- **多源下载机制**：优先使用Gitee镜像源，失败时自动切换到GitHub
- **流程容错**：完善的错误处理和故障恢复机制
- **智能缓存系统**：减少重复下载，增强工作效率

最近更新：优化了ModSecurity-Nginx连接器的下载机制，实现了URL故障转移，并增强了不同源解压目录的兼容性处理。

详细使用方法请查看 [ModSecurity安装工具文档](modsecurity/README.md)。

## 贡献代码

欢迎通过以下方式参与项目：

1. Fork本仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建Pull Request

## 许可证

本项目基于MIT许可证 - 详情请查看 [LICENSE](LICENSE) 文件
