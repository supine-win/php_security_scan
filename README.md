# PHP Security Scanner

这个Python脚本用于扫描PHP文件中可能存在的安全威胁或被篡改的迹象。支持一键安装和一键运行。

## 代码仓库

- GitHub: [https://github.com/supine-win/php_security_scan](https://github.com/supine-win/php_security_scan)
- Gitee（国内镇像）: [https://gitee.com/supine-win/php_security_scan](https://gitee.com/supine-win/php_security_scan)

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
  - **编码内容输出**（如echo base64_decode形式的隐藏输出）
  - **多层编码链**（嵌套的编码/解码操作）
- 提供自动安装ModSecurity的脚本，增强服务器安全性
  - **可疑函数**（包含编码解码操作的自定义函数）
  - **间接编码输出**（变量赋值后输出的隐藏方式）
  - **远程代码执行组合**（eval+file_get_contents+base64_decode组合）
  - **错误隐藏与代码执行**（禁用错误显示后执行可疑代码）
- 将扫描结果输出到控制台和CSV文件
- 结果详细列出文件路径、行号、问题类型和问题代码内容

## 使用方法

### 用法一：直接运行下载的源代码

```bash
# 基本用法（交互式选择要检测的特征）
python main.py /path/to/php/directory

# 指定输出文件
python main.py /path/to/php/directory -o output_results.csv

# 使用特定特征ID进行扫描（如只检测1号、3号和5号特征）
python main.py /path/to/php/directory -p 1,3,5

# 非交互模式，使用默认特征（适用于自动化脚本）
python main.py /path/to/php/directory --non-interactive

# 使用上次保存的特征选择
python main.py /path/to/php/directory --load
```

### 用法二：一键安装（永久安装）

在任何有Python 3的Linux服务器上，使用以下命令一键安装：

```bash
# 使用Gitee源安装（推荐，尤其适合国内用户）
curl -sSL https://gitee.com/supine-win/php_security_scan/raw/main/install.sh | sh

# 或者使用GitHub源
curl -sSL https://raw.githubusercontent.com/supine-win/php_security_scan/main/install.sh | sh
```

安装后，您可以使用以下命令运行扫描：

```bash
# 基本用法（交互式选择要检测的特征）
php-security-scan /path/to/php/directory

# 指定输出文件
php-security-scan /path/to/php/directory -o my_results.csv

# 使用特定特征ID进行扫描
php-security-scan /path/to/php/directory -p 1,3,5

# 非交互模式，使用默认特征
php-security-scan /path/to/php/directory --non-interactive
```

### 用法三：一键运行（临时使用）

如果您只需要运行一次扫描，可以使用以下命令直接从云端获取脚本并执行：

> **注意：** 通过curl管道方式运行脚本时，工具会自动使用非交互模式(默认只启用编码后命令执行特征)。您可以使用以下两种方式启用交互式特征选择：
> 1. 添加`--force-interactive`参数强制交互模式（请注意部分终端可能无法正常输入）
> 2. 先下载脚本到本地，然后运行（推荐方式）
>
> **方法二：两步下载和运行（最可靠）：**
> ```bash
> # 步骤1：下载脚本到本地
> curl -sSL https://gitee.com/supine-win/php_security_scan/raw/main/run.sh -o scan.sh
> chmod +x scan.sh
> 
> # 步骤2：交互式运行
> ./scan.sh /path/to/php/directory
> ```

```bash
# Gitee源(推荐) - 基本用法（默认只启用第一个特征）
curl -sSL https://gitee.com/supine-win/php_security_scan/raw/main/run.sh | sh -s -- /path/to/php/directory

# Gitee源 - 指定输出文件
curl -sSL https://gitee.com/supine-win/php_security_scan/raw/main/run.sh | sh -s -- /path/to/php/directory -o my_results.csv

# Gitee源 - 使用特定特征ID进行扫描（推荐方式）
curl -sSL https://gitee.com/supine-win/php_security_scan/raw/main/run.sh | sh -s -- /path/to/php/directory -p 1,3,5

# Gitee源 - 强制交互式特征选择
curl -sSL https://gitee.com/supine-win/php_security_scan/raw/main/run.sh | sh -s -- /path/to/php/directory --force-interactive

# GitHub源 - 基本用法
curl -sSL https://raw.githubusercontent.com/supine-win/php_security_scan/main/run.sh | sh -s -- /path/to/php/directory
```

## 新特性

### 1. 交互式特征选择

现在您可以选择要检测的PHP安全漏洞特征。默认情况下，只启用“编码后的命令执行”特征，以减少误报。

```
请选择要检测的PHP安全漏洞特征：
--------------------------------------------------
[X]  1. Encoded Command Execution - Potential execution of encoded/obfuscated code
[ ]  2. Command Injection - Direct execution of user-controlled input
[ ]  3. Suspicious File Operation - File operations with user input
...
--------------------------------------------------
请输入要选择的特征ID（用逗号分隔），直接回车使用默认选择，输入'all'选择全部：
> 1,3,5

已选择 3 个特征进行检测
  1. Encoded Command Execution
  3. Suspicious File Operation
  5. SQL Injection Vulnerability
```

### 2. 代码片段展示

扫描结果现在包含代码片段，显示问题代码的上下文（>符号标记问题行）：

```
序号  文件路径                                           行号     类型                  

### 3. 新增高级后门检测规则

本工具新增了多种高级后门检测规则，可检测更隐蔽的PHP恶意代码：

1. **编码内容输出检测**（ID: 17）
   - 检测如`echo base64_decode(...)`形式的隐藏输出
   - 这种形式常用于输出恶意的JavaScript或HTML代码
   - 比传统的`eval(base64_decode(...))`更难被检测

2. **多层解码检测**（ID: 18）
   - 可检测如`base64_decode(gzinflate(base64_decode(...)))`的嵌套解码
   - 这种多层解码是常见的隐藏技术

3. **可疑函数内部检测**（ID: 19）
   - 可检测通过函数封装的解码操作
   - 检测函数体中包含的编码/解码操作

4. **间接解码输出检测**（ID: 20）
   - 检测先解码到变量后输出的隐藏形式
   - 例如`$x = base64_decode(...); echo $x;`

5. **远程代码执行组合检测**（ID: 21）
   - 可检测`eval('>' . file_get_contents(base64_decode(...)))`形式
   - 这种模式从远程服务器加载并执行代码
   - 属于高危隐藏后门

6. **错误隐藏检测**（ID: 22）
   - 检测先禁用错误显示后执行可疑代码的模式
   - 如`ini_set("display_errors", "off"); eval(...)`
   - 这是攻击者隐藏其恶意代码的常见手法

这些新增规则默认均已启用，可显著提高对复杂难检的隐藏后门的检测能力。

```
序号  文件路径                                           行号     类型                  
------------------------------------------------------------------------------------------
1     /path/to/php/directory/file1.php                  15       Command Injection     

代码片段:
  13:   // 处理用户输入
  14:   $command = $_GET['cmd'];
> 15:   system($command); // 危险：直接执行用户输入
  16:   echo "命令已执行";
  17:   

------------------------------------------------------------------------------------------
```

## 输出示例

扫描会在控制台显示详细结果：

```
开始扫描目录: /path/to/php/directory
使用 3 个特征进行检测
扫描完成，共处理42个PHP文件

发现 5 处疑似问题:

序号  文件路径                                           行号     类型                  
------------------------------------------------------------------------------------------
1     /path/to/php/directory/file1.php                  15       Command Injection     

代码片段:
  13:   // 处理用户输入
  14:   $command = $_GET['cmd'];
> 15:   system($command); // 危险：直接执行用户输入
  16:   echo "命令已执行";
  17:   

------------------------------------------------------------------------------------------
2     /path/to/php/directory/admin/file2.php            27       SQL Injection Vulnerability

代码片段:
  25:   // 从用户输入获取ID
  26:   $id = $_GET['id'];
> 27:   $query = "SELECT * FROM users WHERE id = $id"; // SQL注入漏洞
  28:   $result = mysqli_query($conn, $query);
  29:   

------------------------------------------------------------------------------------------
...

详细结果已保存到: php_security_scan_20250329_210746.csv
```

CSV文件包含完整的详细结果，包括：
- 序号
- 疑似文件路径
- 行号
- 问题类型
- 问题代码内容
- 代码片段（问题代码的上下文代码）

## 要求

- Python 3.x
- 无需外部依赖，使用Python标准库

## 注意事项

- 本工具仅检测可能存在的安全漏洞或篡改迹象，结果可能包含误报
- 建议结合其他安全工具和代码审计一起使用，以获得更全面的安全评估

## 网络连接问题解决方案

如果您使用一键安装或一键运行脚本时遇到网络连接问题（如下载超时或无法访问 GitHub），我们提供了一些解决方案：

1. **使用Gitee源**：对于国内用户，强烈推荐使用Gitee源，速度更快，更稳定

2. **使用镜像源**：脚本已经集成了多个备用下载源，会自动尝试备用镜像

3. **手动下载**：如果所有自动方式均失败，您可以：

   ```bash
   # 从 GitHub 手动下载
   git clone https://github.com/supine-win/php_security_scan.git
   ```

## ModSecurity安装脚本

本项目提供了一个用于安装和配置ModSecurity Web应用防火墙的脚本，专门针对已安装宝塔面板和Nginx的Linux服务器。

### 支持的操作系统

- CentOS 7/8/9
- Rocky Linux 8/9
- AlmaLinux 8/9
- Ubuntu 20.04/22.04
- Debian 10/11

### 脚本特点

- 自动检测服务器系统及宝塔环境
- 优先使用Gitee镜像源，适合国内服务器
- 自动安装OWASP ModSecurity核心规则集(CRS)
- 配置Nginx使用ModSecurity防火墙
- 防范常见Web攻击：SQL注入、XSS、CSRF、文件包含等

### 使用方法

只需要一行命令，就可以从远程仓库下载并运行安装脚本：

```bash
# 使用Gitee源（推荐国内服务器）
 curl -sSL https://gitee.com/supine-win/php_security_scan/raw/main/install_modsecurity.sh | bash

# 或者使用GitHub源
 curl -sSL https://raw.githubusercontent.com/supine-win/php_security_scan/main/install_modsecurity.sh | bash
```

您也可以手动下载并运行脚本：

```bash
# 下载脚本
 wget https://gitee.com/supine-win/php_security_scan/raw/main/install_modsecurity.sh

# 添加执行权限
 chmod +x install_modsecurity.sh

# 执行安装
 ./install_modsecurity.sh
```

### 安装后验证

安装完成后，可以使用以下命令验证ModSecurity是否正常工作：

```bash
# 测试XSS防护
 curl -I "http://localhost/?param=<script>"

# 如果返回403状态码，表示ModSecurity成功拦截攻击
```
   cd php_security_scan
   python main.py /path/to/php/directory
   
   # 或者从 Gitee 手动下载(国内推荐)
   git clone https://gitee.com/supine-win/php_security_scan.git
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

4. **直接使用Gitee**: 我们已在Gitee上提供了完整的项目镜像，国内用户可直接访问 [https://gitee.com/supine-win/php_security_scan](https://gitee.com/supine-win/php_security_scan)
