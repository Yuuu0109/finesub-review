# FineSub 审核桌面版

桌面端使用 Tauri 2 和现有 Vue 界面，连接统一审核服务器。客户端不携带 Python、数据库或知识库，不提供离线审核及同步。

## 云服务器

继续使用项目根目录的 Compose 部署 FastAPI、worker 和 PostgreSQL，并通过 HTTPS 域名访问。参见 [README](README.md#postgresql--docker-部署)。`COOKIE_SECURE=true`，数据库无需开放公网端口。服务器域名根路径须提供 `/api/*`，首版不支持子路径部署。

桌面版通过 Tauri HTTP 插件发起请求，沿用服务端会话 Cookie、管理员权限和 CSRF 校验。无需添加跨域白名单，也无需将 Cookie 改成 `SameSite=None`。Cookie 由原生插件管理，不通过前端读取；不要复制或发布应用缓存目录。客户端只能请求 HTTPS API（本机调试允许 HTTP 回环地址），禁止跟随 API 重定向。

## 使用

1. 启动客户端，填写服务器地址，如 `https://review.example.com`，点击“连接”。
2. 输入原有访问口令。管理员继续通过现有管理员入口登录。
3. 导入、裁决、发布仍由云端执行。下载会打开系统保存对话框。
4. 顶部“更换服务器”返回连接页；切换前保存编辑内容。服务器地址会保存在本机，下次启动可直接点击连接。连接失败时可修改地址重试。

服务器地址不应包含 `/api`、用户名、密码、查询参数或片段。本地调试可以填写 `http://127.0.0.1:8765`；先启动本机后端与 worker。未退出的有效会话可能在重启后恢复，公共电脑使用完毕请点击“退出知识库”。网页与桌面端的会话相互独立。

## Windows 开发与打包

需要 Node.js 22.12+、pnpm 11、Rust stable（至少 1.90）、Visual Studio C++ Build Tools 和 WebView2。按 [Tauri 官方 Windows 前置要求](https://v2.tauri.app/start/prerequisites/#windows) 安装工具链。

在 `frontend` 目录运行：

```powershell
pnpm install --frozen-lockfile
pnpm test:desktop
pnpm desktop:dev
# 生成当前用户安装的 Windows NSIS 安装包：
pnpm desktop:build
```

安装包输出到 `frontend/src-tauri/target/release/bundle/nsis/`。Node、Rust、C++ 工具仅用于开发和构建，最终用户不需要安装。安装程序会检查 WebView2，缺少时联网下载安装。0.2.0 提供签名校验更新，但没有 Windows Authenticode 证书签名，两种签名用途不同。

仓库提供 `.github/workflows/desktop.yml`，推送相关分支或手动触发时在 Windows 上执行测试、构建和签名，安装包保存为 Actions artifact，不自动发布 Release。PR 只运行测试，不读取签名密钥。第一次 Rust 构建会生成 `Cargo.lock`，应保留它以固定完整依赖树。

## 0.2.0 更新服务部署

更新源使用所连接审核服务器的 `/api/desktop/updates/latest.json`，必须为 HTTPS。同源下载地址及更新包签名均通过后才安装。成功连接后后台检查一次，也可点击“检查更新”；下载和安装始终需要用户点击确认。更新仅替换桌面程序，不迁移云端审核数据库。

源码仓库保持私有，客户端没有 GitHub 令牌。更新接口公开的只有桌面安装包、版本和更新说明，不包含审核数据。暂未部署更新包时会明确提示检查失败，不冒充“已是最新版本”。

在云服务器部署本分支的后端代码（`feat/desktop`），更新 `.env`：

```dotenv
REVIEW_PUBLIC_URL=https://你的审核域名
COOKIE_SECURE=true
```

下载 GitHub Actions 的 `finesub-review-windows` artifact，解压到服务器临时目录。以下命令在项目根目录执行，将 `解压目录` 替换为实际路径：

```bash
python3 scripts/deploy_desktop_update.py --source 解压目录 --destination desktop-updates
docker compose up -d --build
curl --fail https://你的审核域名/api/desktop/updates/latest.json
```

使用已有 Caddy HTTPS 配置时，Compose 命令保留 `-f compose.yml -f compose.https.yml`。反向代理需允许更新接口和安装包下载。`desktop-updates` 以只读方式挂载到 API 容器。发布脚本检查 SHA-256，先放安装包，再原子替换版本清单，旧安装包保留以支持正在进行的下载。

后续更新：同步提升 `frontend/package.json`、`frontend/src-tauri/Cargo.toml` 和 `tauri.conf.json` 的桌面版本，更新 `CHANGELOG.md`，推送构建。将新的 artifact 用同一命令部署到 `desktop-updates`，无需重启 API（首次增加接口需部署后端）。相同或更低版本不会提示升级。

签名私钥保存在本机项目 `.secrets/desktop-updater.key`，另存于 GitHub Actions 的 `TAURI_SIGNING_PRIVATE_KEY` Secret；公钥已内置客户端。必须安全备份私钥，不能提交、随包分发或重新生成替换，否则已安装客户端无法信任后续更新。本机构建需要设置 `TAURI_SIGNING_PRIVATE_KEY` 为私钥文件绝对路径，`TAURI_SIGNING_PRIVATE_KEY_PASSWORD` 为空字符串；不可将签名变量写入可提交的 `.env`。

## 验收

- 网页构建与原有登录流程正常。
- 桌面连接失败可重试，拒绝公网 HTTP 与非审核服务器。
- 访问口令、管理员登录/退出、会话过期与重新进入正常。
- 上传多文件/ZIP、预检、后台任务、审核与发布正常。
- 原始上传文件、知识库 ZIP、审核归档可保存；取消保存不报错。
- 重启客户端后会话行为符合服务端有效期，切换服务器不混用页面数据。
- 无开发环境的 Windows 机器完成安装、启动、卸载和再次安装。

前端测试和构建成功不等于原生安装包或云服务器验收成功。

2026-10-10 本地验证：前端类型检查/生产构建通过；桌面地址、API 路径、文件名与传输适配测试 4 项通过；后端访问权限和网页资源测试 10 项通过；Edge 无头浏览器完成连接、拒绝公网 HTTP、登录页、更换服务器、地址记忆和网页回退检查（模拟 IPC/API）。原生构建实际尝试因缺少 Cargo 失败，环境检查也缺少 MSVC；尚未生成安装包或完成真实云服务验收。

实现依据：[HTTP 插件](https://v2.tauri.app/plugin/http-client/)、[文件对话框](https://v2.tauri.app/plugin/dialog/)、[文件系统权限](https://v2.tauri.app/plugin/file-system/)、[Windows 安装包](https://v2.tauri.app/distribute/windows-installer/)。
