# FineSub 审核桌面版

桌面端使用 Tauri 2 和现有 Vue 界面，连接统一审核服务器。客户端不携带 Python、数据库或知识库，不提供离线审核及同步。

## 云服务器

继续使用项目根目录的 Compose 部署 FastAPI、worker 和 PostgreSQL，并通过 HTTPS 域名访问。参见 [README](README.md#postgresql--docker-部署)。`COOKIE_SECURE=true`，数据库无需开放公网端口。服务器域名根路径须提供 `/api/*`，首版不支持子路径部署。

桌面版通过 Tauri HTTP 插件发起请求，沿用服务端会话 Cookie、管理员权限和 CSRF 校验。无需添加跨域白名单，也无需将 Cookie 改成 `SameSite=None`。Cookie 由原生插件管理，不通过前端读取；不要复制或发布应用缓存目录。客户端只能请求 HTTPS API（本机调试允许 HTTP 回环地址），禁止跟随 API 重定向。

## 使用

下载以 `-portable.exe` 结尾的文件，双击直接运行，不需要安装 FineSub。当前仅提供免安装程序。需要系统已具备 WebView2 Runtime；本机已有。设置与会话仍保存在系统应用数据目录，免安装不代表所有数据都随 EXE 移动。

1. 启动客户端，自动连接默认服务器 `https://49.234.185.63`，无需填写地址。
2. 输入原有访问口令。管理员继续通过现有管理员入口登录。
3. 导入、裁决、发布仍由云端执行。下载会打开系统保存对话框。
4. 顶部“更换服务器”返回连接页；切换前保存编辑内容。自定义服务器地址会保存在本机，下次启动自动重连。连接失败时可修改地址重试。

服务器地址不应包含 `/api`、用户名、密码、查询参数或片段。本地调试可以填写 `http://127.0.0.1:8765`；先启动本机后端与 worker。未退出的有效会话可能在重启后恢复，公共电脑使用完毕请点击“退出知识库”。网页与桌面端的会话相互独立。

## Windows 开发与打包

0.2.2 起使用美香主题图标。当前图标源文件为 `frontend/src-tauri/icons/mika-source.png`，使用 `pnpm tauri icon src-tauri/icons/mika-source.png`（在 frontend 目录）重新生成图标；原 `source.svg` 仅作为旧图标备份。

需要 Node.js 22.12+、pnpm 11、Rust stable（至少 1.90）、Visual Studio C++ Build Tools 和 WebView2。按 [Tauri 官方 Windows 前置要求](https://v2.tauri.app/start/prerequisites/#windows) 安装工具链。

在 `frontend` 目录运行：

```powershell
pnpm install --frozen-lockfile
pnpm test:desktop
pnpm desktop:dev
# 仅编译可直接运行的 Windows EXE：
pnpm desktop:build
```

EXE 输出到 `frontend/src-tauri/target/release/finesub-review-desktop.exe`。`desktop:build` 使用 `--no-bundle` 跳过安装器，Tauri 配置也关闭安装包生成。Node、Rust、C++ 工具仅用于开发和构建，最终用户无需安装这些工具；WebView2 Runtime 需要已就绪。更新签名用于校验下载文件，没有 Windows Authenticode 证书签名，两种签名用途不同。

仓库提供 `.github/workflows/desktop.yml`，推送相关分支或手动触发时在 Windows 上执行测试、构建、独立 EXE 签名和交付整理，结果保存为 Actions artifact，不自动发布 Release。PR 只运行测试，不读取签名密钥。仓库保留已验证的 `Cargo.lock`，CI 使用 `--locked` 检查完整依赖树。

## GitHub Releases 更新

更新源固定为 `https://github.com/Yuuu0109/finesub-review/releases/latest/download/latest.json`。启动时后台检查一次，也可点击“检查更新”，无需先连接审核服务器。更新清单仅提供 `windows-x86_64-portable`，支持 0.2.1 起的免安装更新通道；0.2.0 用户需手动下载免安装 EXE。点击“下载新版”后验证签名并保存到系统“下载”目录，关闭当前程序后双击新版 EXE 即可，不运行安装器、不覆盖原文件。只接受本仓库 HTTPS Release 下载地址，并使用 Tauri 内置公钥验证签名。相同或更低版本不会提示升级。无法访问 GitHub 时可继续使用客户端并稍后重试。

仓库及 Release 公开，客户端没有 GitHub 令牌。更新仅下载新版桌面程序，不迁移云端数据库，云服务器无需增加更新接口。

后续发布步骤：

1. 同步提升 `frontend/package.json`、`frontend/src-tauri/Cargo.toml`、`frontend/src-tauri/tauri.conf.json` 的版本，更新 `CHANGELOG.md`。
2. 推送到 `feat/desktop`，等待 Windows desktop build 成功，下载 `finesub-review-windows` artifact。交付目录仅包含四个文件：免安装 EXE、对应 `.sig`、`latest.json` 和 `SHA256SUMS.txt`。
3. 在 GitHub 创建对应 `v版本号` Release，目标使用该次成功构建的提交，上传全部四个文件。确认所有附件齐全后发布为正式最新版（非预发布）。不要覆盖已发布版本的文件。
4. 检查上述固定更新地址返回新版清单，并在上一版客户端执行检查、下载、签名验证与新版运行验收。

也可用 GitHub CLI 发布，以下路径和版本需替换为本次实际值：

```powershell
gh release create v0.2.3 --target 构建提交SHA --draft --title "FineSub Review 0.2.3 免安装版" --notes-file 发布说明文件
gh release upload v0.2.3 output/desktop-0.2.3/*
gh release edit v0.2.3 --draft=false --latest
```

签名私钥保存在本机项目 `.secrets/desktop-updater.key`，另存于 GitHub Actions 的 `TAURI_SIGNING_PRIVATE_KEY` Secret；公钥已内置客户端。必须安全备份私钥，不能提交、随包分发或重新生成替换，否则已安装客户端无法信任后续更新。本机构建需要设置 `TAURI_SIGNING_PRIVATE_KEY` 为私钥文件绝对路径，`TAURI_SIGNING_PRIVATE_KEY_PASSWORD` 为空字符串；不可将签名变量写入可提交的 `.env`。

## 验收

2026-10-12 免安装版 0.2.1：[构建 38156586017](https://github.com/Yuuu0109/finesub-review/actions/runs/38156586017) 原生测试、构建及独立 EXE 签名全部通过。[Release](https://github.com/Yuuu0109/finesub-review/releases/tag/v0.2.1) 已发布，`-portable.exe` 为 18,842,112 字节，SHA-256 为 `23a61b79216836ec9edf18b03dac210c7469dcb92b434d4862325a17b37f16d1`。本机直接启动交付 EXE，真实 IPC 返回 0.2.1；签名验证、篡改拒绝、匿名下载一致性检查通过。更新下载、错误重试与保存提示通过模拟 IPC 验证，原生测试确认不覆盖已有文件。本机原生 GitHub 检查遇到连接失败（公开清单与 EXE 手动下载正常）；尚未完成真实跨版本下载验收。

- 网页构建与原有登录流程正常。
- 桌面连接失败可重试，拒绝公网 HTTP 与非审核服务器。
- 访问口令、管理员登录/退出、会话过期与重新进入正常。
- 上传多文件/ZIP、预检、后台任务、审核与发布正常。
- 原始上传文件、知识库 ZIP、审核归档可保存；取消保存不报错。
- 重启客户端后会话行为符合服务端有效期，切换服务器不混用页面数据。
- 无开发环境的 Windows 机器完成安装、启动、卸载和再次安装。

前端测试和构建成功不等于原生安装包或云服务器验收成功。

2026-10-10 本地验证：前端类型检查/生产构建通过；桌面地址、API 路径、文件名与传输适配测试 4 项通过；后端访问权限和网页资源测试 10 项通过；Edge 无头浏览器完成连接、拒绝公网 HTTP、登录页、更换服务器、地址记忆和网页回退检查（模拟 IPC/API）。原生构建实际尝试因缺少 Cargo 失败，环境检查也缺少 MSVC；尚未生成安装包或完成真实云服务验收。

2026-10-11 0.2.0 验证：GitHub Actions [38125821222](https://github.com/Yuuu0109/finesub-review/actions/runs/38125821222) 原生测试、Windows 构建和签名成功，构建提交为 `5fa1a7091da3c26e65da55e14f3f7f3f031e5ec9`。[正式 Release](https://github.com/Yuuu0109/finesub-review/releases/tag/v0.2.0) 已发布。安装包 4,288,892 字节；SHA-256 为 `070a2773706d0465ad4b6d5c162a6dc219470194c4444668851910621a056379`。

本机验证了同次构建的原生程序启动、真实 Tauri 版本 IPC、访问公开 GitHub 更新源并显示“已是最新版本”。安装包签名和 SHA-256 校验通过，修改一个字节后签名验证失败；匿名下载的清单与安装包和本机产物一致。前端测试 4 项、后端回归 10 项通过，更新提示、确认下载、进度、错误重试及后台检查中打开窗口通过浏览器模拟 IPC 验证。尚未执行真实跨版本覆盖安装、卸载或云端业务验收。

实现依据：[HTTP 插件](https://v2.tauri.app/plugin/http-client/)、[文件对话框](https://v2.tauri.app/plugin/dialog/)、[文件系统权限](https://v2.tauri.app/plugin/file-system/)、[Windows 安装包](https://v2.tauri.app/distribute/windows-installer/)、[更新插件](https://v2.tauri.app/plugin/updater/)、[GitHub 构建分发](https://v2.tauri.app/distribute/pipelines/github/)。
