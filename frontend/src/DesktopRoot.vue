<script setup lang="ts">
import { onMounted, ref } from "vue";
import App from "./App.vue";
import Icon from "./components/Icon.vue";
import { probeServer, savedServer, selectServer } from "./transport";
import { normalizeServer } from "./server";
import DesktopUpdate from "./components/DesktopUpdate.vue";
const address = ref(savedServer());
const connected = ref(false), busy = ref(false), error = ref("");
async function connect() {
  busy.value = true;
  error.value = "";
  try {
    const value = normalizeServer(address.value);
    await probeServer(value);
    selectServer(value);
    address.value = value;
    connected.value = true;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "连接失败，请检查服务器地址和网络";
  } finally {
    busy.value = false;
  }
}
function switchServer() {
  if (window.confirm("返回服务器设置？请先保存当前编辑内容。")) location.reload();
}
// Always show the connection screen, so an unavailable server can be changed.
onMounted(() => document.title = "FineSub 知识库审核");
</script>
<template>
  <div v-if="connected" class="desktop-connected">
    <div class="desktop-bar">
      <span>FineSub 知识库审核</span>
      <DesktopUpdate />
      <button type="button" @click="switchServer">{{ address }} · 更换服务器</button>
    </div>
    <App />
  </div>
  <main v-else class="desktop-connect">
    <section class="desktop-card">
      <div class="brand"><span class="brand-mark"><Icon name="book" :size="26" /></span><span>FineSub<small>知识库审核</small></span></div>
      <h1>连接审核服务器</h1>
      <form @submit.prevent="connect">
        <label>服务器地址<input v-model="address" type="url" required autofocus :disabled="busy" placeholder="https://review.example.com" autocomplete="url" /></label>
        <p v-if="error" class="form-error" role="alert">{{ error }}</p>
        <button class="button primary full" :disabled="busy">{{ busy ? "正在连接…" : "连接" }}<Icon name="arrow" :size="18" /></button>
      </form>
      <div class="desktop-update-entry"><DesktopUpdate /></div>
    </section>
  </main>
</template>
<style>
.desktop-connect { min-height: 100vh; display: grid; place-items: center; padding: 32px; }
.desktop-card { width: min(100%, 440px); padding: 36px; background: var(--surface-1); border: 1px solid var(--line-1); border-radius: var(--r-lg); box-shadow: var(--shadow-sm); }
.desktop-card h1 { margin: 36px 0 24px; }
.desktop-card form { display: grid; gap: 20px; }
.desktop-card .brand { justify-content: flex-start; }
.desktop-update-entry { margin-top: 20px; text-align: right; }
.desktop-bar { height: 40px; position: sticky; top: 0; z-index: 45; display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 0 20px; border-bottom: 1px solid var(--line-1); background: var(--surface-2); font-size: var(--text-xs); }
.desktop-bar button { border: 0; background: transparent; color: var(--ink-3); max-width: 65%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.desktop-connected .sidebar { top: 40px; }
.desktop-connected .topbar { top: 40px; }
.desktop-connected .app-shell, .desktop-connected .login-screen { min-height: calc(100vh - 40px); }
</style>
