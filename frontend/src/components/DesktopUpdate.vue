<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { Channel, invoke } from "@tauri-apps/api/core";
import { getVersion } from "@tauri-apps/api/app";
import Modal from "./Modal.vue";
const version = ref(""), open = ref(false), checking = ref(false), downloading = ref(false);
const savedPath = ref("");
const error = ref(""), checked = ref(false), downloaded = ref(0), total = ref<number | null>(null);
const update = ref<{ version: string; notes: string } | null>(null);
const percent = computed(() => total.value ? Math.min(100, Math.round(downloaded.value / total.value * 100)) : null);
async function check(visible = true) {
  if (visible) open.value = true;
  if (checking.value || downloading.value) return;
  checking.value = true;
  savedPath.value = "";
  error.value = "";
  update.value = null;
  checked.value = false;
  try {
    update.value = await invoke("check_desktop_update");
    checked.value = true;
  } catch (e) { error.value = String(e instanceof Error ? e.message : e); }
  finally { checking.value = false; }
}
async function download() {
  if (!update.value || downloading.value) return;
  downloading.value = true;
  error.value = "";
  downloaded.value = 0;
  total.value = null;
  const onProgress = new Channel<{ downloaded: number; total: number | null }>();
  onProgress.onmessage = (progress) => { downloaded.value = progress.downloaded; total.value = progress.total; };
  try { savedPath.value = await invoke("download_desktop_update", { version: update.value.version, onProgress }); update.value = null; }
  catch (e) { error.value = String(e instanceof Error ? e.message : e); update.value = null; }
  finally { downloading.value = false; }
}
onMounted(async () => {
  version.value = await getVersion();
  void check(false);
});
</script>
<template>
  <button type="button" class="desktop-update-button" @click="update ? open = true : check()">v{{ version }} · {{ update ? '有新版本' : '检查更新' }}</button>
  <Modal v-if="open" title="应用更新" @close="!downloading && (open = false)">
    <div class="desktop-update-body" aria-live="polite">
      <p>当前版本 {{ version }}</p>
      <p v-if="checking">正在检查更新…</p>
      <p v-else-if="error" class="form-error" role="alert">{{ error }}</p>
      <template v-else-if="savedPath">
        <p>已下载并通过签名校验。关闭当前程序后，双击新版文件运行。</p>
        <p class="desktop-release-notes">{{ savedPath }}</p>
      </template>
      <template v-else-if="update">
        <h3>新版本 {{ update.version }}</h3>
        <p class="desktop-release-notes">{{ update.notes || '修复问题并改善使用体验。' }}</p>
        <p class="muted">新版保存到“下载”文件夹，无需安装。</p>
      </template>
      <p v-else-if="checked">已是最新版本。</p>
      <template v-if="downloading">
        <progress :value="percent ?? undefined" max="100"></progress>
        <p>{{ percent === 100 ? '正在校验并保存…' : `正在下载 ${percent === null ? (downloaded / 1048576).toFixed(1) + ' MB' : percent + '%'}` }}</p>
      </template>
      <div class="modal-actions">
        <button class="button" :disabled="downloading" @click="open = false">稍后</button>
        <button v-if="update" class="button primary" :disabled="checking || downloading" @click="download">下载新版</button>
        <button v-else class="button primary" :disabled="checking || downloading" @click="check()">重新检查</button>
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
