<script setup lang="ts">
import { onMounted, ref } from "vue";
import App from "./App.vue";
import Icon from "./components/Icon.vue";
import { probeServer, savedServer, selectServer } from "./transport";
import { normalizeServer } from "./server";
import DesktopUpdate from "./components/DesktopUpdate.vue";
import WelcomePanel from "./components/WelcomePanel.vue";
const address = ref(savedServer());
const connected = ref(false),
  busy = ref(false),
  error = ref("");
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
    error.value =
      e instanceof Error ? e.message : "连接失败，请检查服务器地址和网络";
  } finally {
    busy.value = false;
  }
}
function switchServer() {
  if (window.confirm("返回服务器设置？请先保存当前编辑内容。"))
    location.reload();
}
// Always show the connection screen, so an unavailable server can be changed.
onMounted(() => (document.title = "FineSub 知识库审核"));
</script>
<template>
  <div v-if="connected" class="desktop-connected">
    <div class="desktop-bar">
      <span class="desktop-bar-brand">FineSub Review</span>
      <div class="desktop-bar-actions">
        <span class="server-status"><span></span>已连接</span>
        <button
          class="server-switch"
          type="button"
          :title="address"
          @click="switchServer"
        >
          <span>{{ address }}</span
          ><Icon name="settings" :size="14" />更换服务器
        </button>
        <DesktopUpdate />
      </div>
    </div>
    <App />
  </div>
  <main v-else class="entry-screen desktop-connect">
    <div class="entry-layout">
      <WelcomePanel />
      <section class="entry-form desktop-card">
        <div class="entry-form-content">
          <span class="entry-symbol"><Icon name="link" :size="24" /></span>
          <h2>连接审核服务器</h2>
          <form @submit.prevent="connect">
            <label for="server-address">服务器地址</label>
            <div class="entry-input">
              <Icon name="link" :size="18" /><input
                id="server-address"
                v-model="address"
                type="url"
                required
                autofocus
                :disabled="busy"
                placeholder="https://review.example.com"
                autocomplete="url"
                spellcheck="false"
                aria-describedby="server-hint"
              />
            </div>
            <p id="server-hint" class="input-hint">使用团队提供的 HTTPS 地址</p>
            <p v-if="error" class="form-error" role="alert">{{ error }}</p>
            <button class="button primary full" :disabled="busy">
              <span v-if="busy" class="spinner"></span
              >{{ busy ? "正在连接…" : "连接"
              }}<Icon v-if="!busy" name="arrow" :size="18" />
            </button>
          </form>
          <div class="entry-note">
            <Icon name="shield" :size="15" /><span
              >安全连接 · 服务器地址保存在本机</span
            >
          </div>
        </div>
        <div class="entry-form-footer">
          <span>桌面客户端</span><DesktopUpdate />
        </div>
      </section>
    </div>
  </main>
</template>
