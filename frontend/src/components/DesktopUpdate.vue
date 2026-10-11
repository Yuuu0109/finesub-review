<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { Channel, invoke } from "@tauri-apps/api/core";
import { getVersion } from "@tauri-apps/api/app";
import Modal from "./Modal.vue";
const version = ref(""), open = ref(false), checking = ref(false), installing = ref(false);
const error = ref(""), checked = ref(false), downloaded = ref(0), total = ref<number | null>(null);
const update = ref<{ version: string; notes: string } | null>(null);
const percent = computed(() => total.value ? Math.min(100, Math.round(downloaded.value / total.value * 100)) : null);
async function check(visible = true) {
  if (checking.value || installing.value) return;
  if (visible) open.value = true;
  checking.value = true;
  error.value = "";
  update.value = null;
  checked.value = false;
  try {
    update.value = await invoke("check_desktop_update");
    checked.value = true;
  } catch (e) { error.value = String(e instanceof Error ? e.message : e); }
  finally { checking.value = false; }
}
async function install() {
  if (!update.value || installing.value) return;
  installing.value = true;
  error.value = "";
  downloaded.value = 0;
  total.value = null;
  const onProgress = new Channel<{ downloaded: number; total: number | null }>();
  onProgress.onmessage = (progress) => { downloaded.value = progress.downloaded; total.value = progress.total; };
  try { await invoke("install_desktop_update", { version: update.value.version, onProgress }); }
  catch (e) { error.value = String(e instanceof Error ? e.message : e); update.value = null; }
  finally { installing.value = false; }
}
onMounted(async () => {
  version.value = await getVersion();
  void check(false);
});
</script>
<template>
  <button type="button" class="desktop-update-button" @click="update ? open = true : check()">v{{ version }} · {{ update ? '有新版本' : '检查更新' }}</button>
  <Modal v-if="open" title="应用更新" @close="!installing && (open = false)">
    <div class="desktop-update-body" aria-live="polite">
      <p>当前版本 {{ version }}</p>
      <p v-if="checking">正在检查更新…</p>
      <p v-else-if="error" class="form-error" role="alert">{{ error }}</p>
      <template v-else-if="update">
        <h3>新版本 {{ update.version }}</h3>
        <p class="desktop-release-notes">{{ update.notes || '修复问题并改善使用体验。' }}</p>
        <p class="muted">安装会关闭并重新启动应用，请先保存编辑内容。</p>
      </template>
      <p v-else-if="checked">已是最新版本。</p>
      <template v-if="installing">
        <progress :value="percent ?? undefined" max="100"></progress>
        <p>{{ percent === 100 ? '正在校验并安装…' : `正在下载 ${percent === null ? (downloaded / 1048576).toFixed(1) + ' MB' : percent + '%'}` }}</p>
      </template>
      <div class="modal-actions">
        <button class="button" :disabled="installing" @click="open = false">稍后</button>
        <button v-if="update" class="button primary" :disabled="checking || installing" @click="install">下载并安装</button>
        <button v-else class="button primary" :disabled="checking || installing" @click="check()">重新检查</button>
      </div>
    </div>
  </Modal>
</template>
<style scoped>
.desktop-update-button { border: 0; background: transparent; color: var(--brand-600); font-size: var(--text-xs); white-space: nowrap; }
.desktop-update-body { display: grid; gap: 16px; }
.desktop-release-notes { white-space: pre-wrap; max-height: 240px; overflow: auto; }
progress { width: 100%; accent-color: var(--brand-600); }
</style>
