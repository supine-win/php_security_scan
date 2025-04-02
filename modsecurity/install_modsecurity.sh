#!/bin/bash
# 宝塔环境ModSecurity安装与配置脚本
# 支持CentOS 7/8/9和Ubuntu 20/22
# 优先使用Gitee镜像源
# 作者: supine-win
# 版本: 1.0.0

# 颜色设置
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # 无颜色

# 日志文件
LOG_FILE="/tmp/modsecurity_install.log"

# 清理之前的日志
rm -f $LOG_FILE
touch $LOG_FILE

# 输出信息到控制台和日志文件
log() {
    echo -e "${GREEN}[INFO]${NC} $1" | tee -a $LOG_FILE
}

# 输出警告信息
warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" | tee -a $LOG_FILE
}

# 输出错误信息
error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a $LOG_FILE
}

# 输出调试信息（仅写入日志）
debug() {
    echo -e "[DEBUG] $1" >> $LOG_FILE
}

# 检查命令是否存在
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 检查是否为root用户
check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "此脚本必须以root用户运行"
        exit 1
    fi
}

# 检测Linux发行版
detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        DISTRO=$ID
        VERSION_ID=$VERSION_ID
    elif [ -f /etc/lsb-release ]; then
        . /etc/lsb-release
        DISTRO=$DISTRIB_ID
        VERSION_ID=$DISTRIB_RELEASE
    else
        if [ -f /etc/centos-release ]; then
            DISTRO="centos"
            VERSION_ID=$(cat /etc/centos-release | tr -dc '0-9.' | cut -d \. -f1)
        else
            error "无法检测操作系统类型"
            exit 1
        fi
    fi

    DISTRO=$(echo "$DISTRO" | tr '[:upper:]' '[:lower:]')
    
    # 检测 RHEL 系列
    if [[ "$DISTRO" == "centos" ]] || [[ "$DISTRO" == "rhel" ]] || [[ "$DISTRO" == "rocky" ]] || [[ "$DISTRO" == "almalinux" ]]; then
        DISTRO_FAMILY="rhel"
    # 检测 Debian 系列
    elif [[ "$DISTRO" == "ubuntu" ]] || [[ "$DISTRO" == "debian" ]]; then
        DISTRO_FAMILY="debian"
    else
        error "不支持的操作系统: $DISTRO"
        exit 1
    fi

    log "检测到操作系统: $DISTRO $VERSION_ID"
    debug "发行版系列: $DISTRO_FAMILY"
}

# 检查宝塔面板是否安装
check_bt_panel() {
    if [ -f "/www/server/panel/BTPanel/static/favicon.ico" ]; then
        BT_INSTALLED=true
        log "检测到宝塔面板已安装"
    else
        warn "未检测到宝塔面板，尝试继续安装"
        BT_INSTALLED=false
    fi
}

# 检查Nginx是否安装
check_nginx() {
    if command_exists nginx; then
        NGINX_INSTALLED=true
        
        # 检查Nginx安装路径
        if [ -d "/www/server/nginx" ]; then
            NGINX_PATH="/www/server/nginx"
            log "检测到宝塔安装的Nginx: $NGINX_PATH"
        else
            NGINX_PATH=$(dirname $(dirname $(which nginx)))
            log "检测到系统安装的Nginx: $NGINX_PATH"
        fi
        
        # 获取Nginx版本
        NGINX_VERSION=$(nginx -v 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
        log "Nginx版本: $NGINX_VERSION"
        
        # 检测是否已安装ModSecurity
        if [ -f "$NGINX_PATH/modules/ngx_http_modsecurity_module.so" ]; then
            warn "ModSecurity模块已存在，将尝试重新安装"
        fi
    else
        error "未检测到Nginx，请先安装Nginx"
        exit 1
    fi
}

# 安装依赖
install_dependencies() {
    log "开始安装依赖..."
    
    if [ "$DISTRO_FAMILY" == "rhel" ]; then
        # 安装epel源
        if ! command_exists yum-config-manager; then
            yum install -y yum-utils >> $LOG_FILE 2>&1
        fi
        
        # 对于CentOS 8+，检查是否需要配置PowerTools或CodeReady库
        if [[ "$VERSION_ID" -ge 8 ]]; then
            if [[ "$DISTRO" == "centos" ]]; then
                # CentOS 8启用PowerTools, CentOS Stream 8和9启用crb
                if dnf repolist | grep -q "PowerTools"; then
                    dnf config-manager --set-enabled PowerTools >> $LOG_FILE 2>&1
                elif dnf repolist | grep -q "powertools"; then
                    dnf config-manager --set-enabled powertools >> $LOG_FILE 2>&1
                elif dnf repolist | grep -q "crb"; then
                    dnf config-manager --set-enabled crb >> $LOG_FILE 2>&1
                else
                    warn "无法找到PowerTools或CodeReady库，某些依赖可能无法安装"
                fi
            elif [[ "$DISTRO" == "rocky" ]] || [[ "$DISTRO" == "almalinux" ]]; then
                # Rocky Linux和AlmaLinux启用crb
                dnf config-manager --set-enabled crb >> $LOG_FILE 2>&1
            fi
        fi

        yum install -y epel-release >> $LOG_FILE 2>&1
        yum install -y git make gcc gcc-c++ flex bison yajl yajl-devel curl-devel curl \
            zlib-devel pcre-devel autoconf automake libxml2-devel libtool wget \
            openssl-devel geoip-devel doxygen >> $LOG_FILE 2>&1
    elif [ "$DISTRO_FAMILY" == "debian" ]; then
        apt update >> $LOG_FILE 2>&1
        apt install -y git build-essential libpcre3-dev libxml2-dev libyajl-dev \
            liblmdb-dev libcurl4-openssl-dev libgeoip-dev libtool doxygen \
            autoconf automake pkgconf libssl-dev zlib1g-dev libpcre3-dev >> $LOG_FILE 2>&1
    else
        error "不支持的操作系统家族: $DISTRO_FAMILY"
        exit 1
    fi
    
    if [ $? -ne 0 ]; then
        error "安装依赖失败，请检查网络连接或手动安装依赖"
        exit 1
    fi
    
    log "依赖安装完成"
}

# 创建临时编译目录
create_build_dir() {
    BUILD_DIR="/tmp/modsecurity_build"
    mkdir -p $BUILD_DIR
    cd $BUILD_DIR
    log "创建编译目录: $BUILD_DIR"
}

# 下载ModSecurity
download_modsecurity() {
    log "开始下载ModSecurity..."
    cd $BUILD_DIR
    
    # 优先尝试从Gitee下载
    if git clone https://gitee.com/mirrors/ModSecurity.git modsecurity >> $LOG_FILE 2>&1; then
        log "从Gitee镜像下载ModSecurity成功"
    else
        warn "从Gitee镜像下载失败，尝试从GitHub下载"
        if git clone https://github.com/SpiderLabs/ModSecurity.git modsecurity >> $LOG_FILE 2>&1; then
            log "从GitHub下载ModSecurity成功"
        else
            error "下载ModSecurity失败"
            exit 1
        fi
    fi
    
    cd modsecurity
    
    log "获取ModSecurity子模块..."
    git submodule init >> $LOG_FILE 2>&1
    git submodule update >> $LOG_FILE 2>&1
    
    if [ $? -ne 0 ]; then
        warn "获取子模块可能失败，尝试继续编译"
    fi
}

# 编译ModSecurity
compile_modsecurity() {
    log "开始编译ModSecurity..."
    cd $BUILD_DIR/modsecurity
    
    # 生成配置文件
    log "运行buildconf脚本..."
    ./build/configure.py --help >> $LOG_FILE 2>&1 || true  # 只是为了生成帮助信息，可能会失败但不重要
    
    log "运行autogen.sh脚本..."
    ./autogen.sh >> $LOG_FILE 2>&1
    
    if [ $? -ne 0 ]; then
        error "运行autogen.sh失败"
        exit 1
    fi
    
    log "配置ModSecurity..."
    ./configure --disable-doxygen-doc --disable-examples --disable-dependency-tracking >> $LOG_FILE 2>&1
    
    if [ $? -ne 0 ]; then
        error "配置ModSecurity失败"
        exit 1
    fi
    
    log "编译ModSecurity..."
    make -j$(nproc) >> $LOG_FILE 2>&1
    
    if [ $? -ne 0 ]; then
        error "编译ModSecurity失败"
        exit 1
    fi
    
    log "安装ModSecurity..."
    make install >> $LOG_FILE 2>&1
    
    if [ $? -ne 0 ]; then
        error "安装ModSecurity失败"
        exit 1
    fi
    
    log "ModSecurity编译安装完成"
}

# 下载和安装ModSecurity-nginx连接器
install_modsecurity_nginx() {
    log "下载ModSecurity-nginx连接器..."
    cd $BUILD_DIR
    
    # 优先尝试从Gitee下载
    if git clone https://gitee.com/mirrors/ModSecurity-nginx.git modsecurity-nginx >> $LOG_FILE 2>&1; then
        log "从Gitee镜像下载ModSecurity-nginx成功"
    else
        warn "从Gitee镜像下载失败，尝试从GitHub下载"
        if git clone https://github.com/SpiderLabs/ModSecurity-nginx.git modsecurity-nginx >> $LOG_FILE 2>&1; then
            log "从GitHub下载ModSecurity-nginx成功"
        else
            error "下载ModSecurity-nginx失败"
            exit 1
        fi
    fi
    
    # 下载与当前Nginx相同版本的源码
    log "下载Nginx源码(版本: $NGINX_VERSION)..."
    wget -q http://nginx.org/download/nginx-$NGINX_VERSION.tar.gz -O nginx.tar.gz >> $LOG_FILE 2>&1
    
    if [ $? -ne 0 ]; then
        error "下载Nginx源码失败"
        exit 1
    fi
    
    tar -xzf nginx.tar.gz
    
    # 编译Nginx模块
    log "编译Nginx ModSecurity模块..."
    cd nginx-$NGINX_VERSION
    
    # 获取Nginx编译参数
    NGINX_CONFIGURE_ARGS=$(nginx -V 2>&1 | grep "configure arguments:" | cut -d: -f2-)
    debug "Nginx编译参数: $NGINX_CONFIGURE_ARGS"
    
    # 添加ModSecurity模块
    ./configure $NGINX_CONFIGURE_ARGS --add-dynamic-module=../modsecurity-nginx >> $LOG_FILE 2>&1
    
    if [ $? -ne 0 ]; then
        error "配置Nginx ModSecurity模块失败"
        exit 1
    fi
    
    # 只编译模块
    make modules >> $LOG_FILE 2>&1
    
    if [ $? -ne 0 ]; then
        error "编译Nginx ModSecurity模块失败"
        exit 1
    fi
    
    # 创建模块目录
    mkdir -p $NGINX_PATH/modules/
    
    # 复制模块
    cp objs/ngx_http_modsecurity_module.so $NGINX_PATH/modules/
    
    log "Nginx ModSecurity模块安装完成"
}

# 下载OWASP ModSecurity核心规则集(CRS)
download_owasp_crs() {
    log "下载OWASP ModSecurity核心规则集..."
    cd $BUILD_DIR
    
    # 下载最新的CRS
    CRS_VERSION="3.3.4"
    
    if [ ! -d "/etc/nginx/modsecurity-crs" ]; then
        mkdir -p /etc/nginx/modsecurity-crs
    fi
    
    # 优先尝试从Gitee下载
    if wget -q https://gitee.com/mirrors/owasp-modsecurity-crs/repository/archive/v$CRS_VERSION.zip -O crs.zip >> $LOG_FILE 2>&1; then
        log "从Gitee镜像下载CRS成功"
    else
        warn "从Gitee镜像下载失败，尝试从GitHub下载"
        if wget -q https://github.com/coreruleset/coreruleset/archive/v$CRS_VERSION.tar.gz -O crs.tar.gz >> $LOG_FILE 2>&1; then
            log "从GitHub下载CRS成功"
            # 解压CRS
            tar -xzf crs.tar.gz >> $LOG_FILE 2>&1
            
            if [ $? -ne 0 ]; then
                error "解压CRS失败"
                exit 1
            fi
            
            # 复制CRS文件
            cp -r coreruleset-$CRS_VERSION/* /etc/nginx/modsecurity-crs/
        else
            error "下载CRS失败"
            exit 1
        fi
    fi
    
    # 如果从Gitee下载成功，解压ZIP文件
    if [ -f "crs.zip" ]; then
        if command_exists unzip; then
            unzip -q crs.zip >> $LOG_FILE 2>&1
        else
            if [ "$DISTRO_FAMILY" == "rhel" ]; then
                yum install -y unzip >> $LOG_FILE 2>&1
            else
                apt install -y unzip >> $LOG_FILE 2>&1
            fi
            unzip -q crs.zip >> $LOG_FILE 2>&1
        fi
        
        if [ $? -ne 0 ]; then
            error "解压CRS失败"
            exit 1
        fi
        
        # 根据Gitee的存档格式找到正确的目录
        CRS_DIR=$(find . -name "*owasp-modsecurity-crs*" -type d | head -n 1)
        cp -r $CRS_DIR/* /etc/nginx/modsecurity-crs/
    fi
    
    # 创建并复制默认配置
    if [ -f "/etc/nginx/modsecurity-crs/crs-setup.conf.example" ]; then
        cp /etc/nginx/modsecurity-crs/crs-setup.conf.example /etc/nginx/modsecurity-crs/crs-setup.conf
        log "CRS配置文件已创建"
    else
        warn "未找到CRS配置示例文件，将创建基本配置"
        echo "# 基本CRS配置" > /etc/nginx/modsecurity-crs/crs-setup.conf
    fi
    
    log "OWASP CRS安装完成"
}

# 配置ModSecurity
configure_modsecurity() {
    log "配置ModSecurity..."
    
    # 创建ModSecurity配置目录
    mkdir -p /etc/nginx/modsecurity
    
    # 复制默认配置
    cp $BUILD_DIR/modsecurity/modsecurity.conf-recommended /etc/nginx/modsecurity/modsecurity.conf
    
    # 修改配置以启用ModSecurity
    sed -i 's/SecRuleEngine DetectionOnly/SecRuleEngine On/' /etc/nginx/modsecurity/modsecurity.conf
    
    # 创建启用的规则集
    cat > /etc/nginx/modsecurity/main.conf << EOF
# ModSecurity配置
Include /etc/nginx/modsecurity/modsecurity.conf

# OWASP CRS配置
Include /etc/nginx/modsecurity-crs/crs-setup.conf
Include /etc/nginx/modsecurity-crs/rules/*.conf
EOF

    # 创建unicode.mapping文件
    cp $BUILD_DIR/modsecurity/unicode.mapping /etc/nginx/modsecurity/
    
    log "ModSecurity配置完成"
}

# 配置Nginx使用ModSecurity
configure_nginx() {
    log "配置Nginx使用ModSecurity..."
    
    # 创建ModSecurity的Nginx配置
    cat > /etc/nginx/conf.d/modsecurity.conf << EOF
# 加载ModSecurity模块
load_module modules/ngx_http_modsecurity_module.so;

# ModSecurity全局配置
modsecurity on;
modsecurity_rules_file /etc/nginx/modsecurity/main.conf;
EOF

    # 检查Nginx配置
    log "验证Nginx配置..."
    nginx -t >> $LOG_FILE 2>&1
    
    if [ $? -ne 0 ]; then
        error "Nginx配置验证失败，请检查配置文件"
        warn "已创建ModSecurity配置，但需要手动修复Nginx配置"
        cat $LOG_FILE | grep -i "error"
        exit 1
    fi
    
    # 重新加载Nginx配置
    log "重新加载Nginx配置..."
    if [ "$BT_INSTALLED" = true ]; then
        # 使用宝塔命令重启Nginx
        if command_exists bt; then
            bt restart nginx >> $LOG_FILE 2>&1
        else
            /etc/init.d/nginx restart >> $LOG_FILE 2>&1
        fi
    else
        # 使用系统命令重启Nginx
        if command_exists systemctl; then
            systemctl restart nginx >> $LOG_FILE 2>&1
        else
            service nginx restart >> $LOG_FILE 2>&1
        fi
    fi
    
    if [ $? -ne 0 ]; then
        error "Nginx重启失败，请手动检查并重启Nginx"
        exit 1
    fi
    
    log "Nginx配置完成并已重启"
}

# 清理临时文件
cleanup() {
    log "清理临时文件..."
    rm -rf $BUILD_DIR
    log "清理完成"
}

# 显示安装成功信息
show_success() {
    echo ""
    echo -e "${GREEN}============================================================${NC}"
    echo -e "${GREEN}ModSecurity安装成功！${NC}"
    echo -e "${GREEN}============================================================${NC}"
    echo ""
    echo -e "ModSecurity已安装并配置为提供基本Web应用防火墙功能"
    echo -e "安装信息:"
    echo -e "- ModSecurity模块: ${BLUE}$NGINX_PATH/modules/ngx_http_modsecurity_module.so${NC}"
    echo -e "- 规则配置目录: ${BLUE}/etc/nginx/modsecurity/${NC}"
    echo -e "- OWASP CRS规则: ${BLUE}/etc/nginx/modsecurity-crs/${NC}"
    echo -e "- Nginx配置: ${BLUE}/etc/nginx/conf.d/modsecurity.conf${NC}"
    echo ""
    echo -e "您可以通过以下命令验证ModSecurity是否正常工作:"
    echo -e "${BLUE}curl -I \"http://localhost/?param=<script>\"${NC}"
    echo -e "如果返回403错误，表示ModSecurity正在阻止XSS攻击尝试"
    echo ""
    echo -e "如需调整规则，请编辑: ${BLUE}/etc/nginx/modsecurity/modsecurity.conf${NC}"
    echo -e "详细安装日志位于: ${BLUE}$LOG_FILE${NC}"
    echo ""
}

# 主函数
main() {
    echo -e "${BLUE}============================================================${NC}"
    echo -e "${BLUE}宝塔环境ModSecurity安装脚本${NC}"
    echo -e "${BLUE}============================================================${NC}"
    echo ""
    
    check_root
    detect_distro
    check_bt_panel
    check_nginx
    install_dependencies
    create_build_dir
    download_modsecurity
    compile_modsecurity
    install_modsecurity_nginx
    download_owasp_crs
    configure_modsecurity
    configure_nginx
    cleanup
    show_success
}

# 运行主函数
main
