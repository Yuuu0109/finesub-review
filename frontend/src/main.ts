import { createApp } from "vue";
import "./style.css";
import { desktop } from "./transport";
if (desktop) {
  document.addEventListener("click", (event) => {
    const link = (event.target as Element).closest<HTMLAnchorElement>("a[href]");
    if (!link || event.defaultPrevented) return;
    const url = new URL(link.href);
    if (url.origin === location.origin) return;
    event.preventDefault();
    if (["https:", "http:"].includes(url.protocol)) {
      void import("@tauri-apps/plugin-opener")
        .then(({ openUrl }) => openUrl(url.href))
        .catch(() => window.alert("无法打开链接，请复制地址到浏览器。"));
    }
  });
}
(desktop ? import("./DesktopRoot.vue") : import("./App.vue"))
  .then(({ default: App }) => createApp(App).mount("#app"))
  .catch(() => {
    const root = document.getElementById("app");
    if (root) {
      root.setAttribute("role", "alert");
      root.textContent = "页面资源加载失败，请按 Ctrl+F5 刷新后重试。";
    }
  });
