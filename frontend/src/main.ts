import { createApp } from "vue";
import "./style.css";
import("./App.vue")
  .then(({ default: App }) => createApp(App).mount("#app"))
  .catch(() => {
    const root = document.getElementById("app");
    if (root) {
      root.setAttribute("role", "alert");
      root.textContent = "页面资源加载失败，请按 Ctrl+F5 刷新后重试。";
    }
  });
