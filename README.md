# PHP Security Scanner

这个Python脚本用于扫描PHP文件中可能存在的安全威胁或被篡改的迹象。支持一键安装和一键运行。

## 功能特点

- 递归扫描指定目录中的所有PHP文件
- 检测多种常见PHP安全漏洞和篡改特征：
  - 编码后的命令执行（如base64_decode后执行）
  - 命令注入（exec, system等接收用户输入）
  - 可疑的文件操作
  - 动态函数创建
  - SQL注入漏洞
  - 命令执行（通过反引号）
  - 代码执行（如preg_replace的/e修饰符）
  - 代码混淆（可疑的变量命名和赋值）
  - 恶意内容（如iframe插入）
  - 远程文件包含
  - 直接代码注入
  - 变量操作（如unsafe extract）
  - 不安全的文件上传
  - 可疑的隐藏输入
  - 文件头部注入
  - 大块编码数据
- 将扫描结果输出到控制台和CSV文件
- 结果详细列出文件路径、行号、问题类型和问题代码内容

## 使用方法

### 用法一：直接运行下载的源代码

```bash
# 基本用法
python main.py /path/to/php/directory

# 指定输出文件
python main.py /path/to/php/directory -o output_results.csv
```

### 用法二：一键安装（永久安装）

在任何有Python 3的Linux服务器上，使用以下命令一键安装：

```bash
curl -sSL https://raw.githubusercontent.com/supine-win/php_security_scan/main/install.sh | sh
```

安装后，您可以使用以下命令运行扫描：

```bash
php-security-scan /path/to/php/directory

# 指定输出文件
php-security-scan /path/to/php/directory -o my_results.csv
```

### 用法三：一键运行（临时使用）

如果您只需要运行一次扫描，可以使用以下命令直接从云端获取脚本并执行：

```bash
# 基本用法
curl -sSL https://raw.githubusercontent.com/supine-win/php_security_scan/main/run.sh | sh -s -- /path/to/php/directory

# 指定输出文件
curl -sSL https://raw.githubusercontent.com/supine-win/php_security_scan/main/run.sh | sh -s -- /path/to/php/directory -o my_results.csv
```

## 输出示例

扫描会在控制台显示简要结果：

```
开始扫描目录: /path/to/php/directory
扫描完成，共处理42个PHP文件

发现 5 处疑似问题:

序号  文件路径                                           行号     类型                  
------------------------------------------------------------------------------------------
1     /path/to/php/directory/file1.php                  15       Command Injection     
2     /path/to/php/directory/admin/file2.php            27       SQL Injection Vulnerability
...

详细结果已保存到: php_security_scan_20250329_210746.csv
```

CSV文件包含完整的详细结果，包括：
- 序号
- 疑似文件路径
- 行号
- 问题类型
- 问题代码内容

## 要求

- Python 3.x
- 无需外部依赖，使用Python标准库

## 注意事项

- 本工具仅检测可能存在的安全漏洞或篡改迹象，结果可能包含误报
- 建议结合其他安全工具和代码审计一起使用，以获得更全面的安全评估

## 网络连接问题解决方案

如果您使用一键安装或一键运行脚本时遇到网络连接问题（如下载超时或无法访问 GitHub），我们提供了一些解决方案：

1. **使用镜像源**：脚本已经集成了多个备用下载源，会自动尝试备用镜像

2. **手动下载**：如果所有自动方式均失败，您可以：

   ```bash
   # 手动下载脚本文件
   git clone https://github.com/supine-win/php_security_scan.git
   cd php_security_scan
   python main.py /path/to/php/directory
   ```

3. **设置代理**：如果您在网络受限的环境中，可以设置代理：

   ```bash
   # 设置 HTTP 代理
   export http_proxy=http://your-proxy:port
   export https_proxy=http://your-proxy:port
   
   # 然后运行脚本
   curl -sSL https://raw.githubusercontent.com/supine-win/php_security_scan/main/run.sh | sh -s -- /path/to/php/directory
   ```

4. **使用镜像网站**：如果 GitHub 访问受限，可以尝试 Gitee 等镜像网站
