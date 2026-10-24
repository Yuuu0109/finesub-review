<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { Channel, invoke } from "@tauri-apps/api/core";
import { getVersion } from "@tauri-apps/api/app";
import { scopedDraftKey } from "../transport";
import Modal from "./Modal.vue";
import Icon from "./Icon.vue";
type UpdateInfo = { version: string; notes: string; prepared: boolean };
const version = ref(""), open = ref(false), checking = ref(false), downloading = ref(false), applying = ref(false), saving = ref(false);
const savedPath = ref(""), error = ref(""), checked = ref(false), downloaded = ref(0), total = ref<number | null>(null);
const update = ref<UpdateInfo | null>(null);
const busy = computed(() => downloading.value || applying.value || saving.value);
const percent = computed(() => total.value ? Math.min(100, Math.round(downloaded.value / total.value * 100)) : null);
function message(e: unknown) { return e instanceof Error ? e.message : String(e); }
async function check(visible = true) {
  if (visible) open.value = true;
  if (checking.value || busy.value) return;
  checking.value = true; savedPath.value = ""; error.value = ""; update.value = null; checked.value = false;
  try { update.value = await invoke("check_desktop_update"); checked.value = true; }
  catch (e) { error.value = message(e); }
  finally { checking.value = false; }
}
async function download() {
  if (!update.value || busy.value) return;
  downloading.value = true; error.value = ""; downloaded.value = 0; total.value = null;
  const onProgress = new Channel<{ downloaded: number; total: number | null }>();
  onProgress.onmessage = (p) => { downloaded.value = p.downloaded; total.value = p.total; };
  try {
    await invoke("download_desktop_update", { version: update.value.version, onProgress });
    update.value.prepared = true;
  } catch (e) { error.value = message(e); update.value = null; }
  finally { downloading.value = false; }
}
async function apply() {
  if (busy.value || !update.value?.prepared) return;
  applying.value = true; error.value = "";
  try {
    if (!window.dispatchEvent(new Event("desktop-before-update", { cancelable: true })))
      throw new Error("操作未完成或草稿未能保存，暂不能重启更新。");
    localStorage.setItem(scopedDraftKey("finesub-update-route"), location.hash);
    await invoke("apply_desktop_update");
  } catch (e) { error.value = message(e); applying.value = false; }
}
async function saveCopy() {
  if (busy.value) return;
  saving.value = true; error.value = "";
  try { savedPath.value = await invoke<string>("save_desktop_update"); }
  catch (e) { error.value = message(e); }
  finally { saving.value = false; }
}
onMounted(async () => {
  try { version.value = await getVersion(); await check(false); }
  catch (e) { error.value = message(e); }
});
</script>
<template>
  <button type="button" class="desktop-update-button" @click="update || busy || checking ? open = true : check()">v{{ version || '…' }} · {{ update?.prepared ? '重启更新' : update ? '有新版本' : checking ? '检查中' : '检查更新' }}</button>
  <Teleport to="body"><Modal v-if="open" title="应用更新" @close="!busy && (open = false)">
    <div class="desktop-update-body" aria-live="polite">
      <div class="update-version"><span class="update-icon"><Icon name="download" :size="24" /></span><div><strong>FineSub Review</strong><p>当前 v{{ version }} · 免安装版</p></div></div>
      <p v-if="checking">正在检查更新…</p>
      <p v-if="error" class="form-error" role="alert">{{ error }}</p>
      <template v-if="update">
        <h3>新版本 {{ update.version }}</h3>
        <p v-if="update.notes" class="desktop-release-notes">{{ update.notes }}</p>
        <p v-if="update.prepared" class="update-ready"><Icon name="shield" :size="17" />更新已通过签名校验</p>
      </template>
      <p v-else-if="checked && !error && !checking">已是最新版本。</p>
      <template v-if="downloading">
        <progress aria-label="新版下载进度" :value="percent ?? undefined" max="100"></progress>
        <p>{{ percent === 100 ? '正在校验签名…' : `正在下载 ${percent === null ? (downloaded / 1048576).toFixed(1) + ' MB' : percent + '%'}` }}</p>
      </template>
      <p v-if="applying" role="status">正在替换程序并重启…</p>
      <p v-if="savedPath" class="desktop-release-notes">已另存新版：{{ savedPath }}</p>
      <div class="modal-actions">
        <button class="button" :disabled="busy" @click="open = false">稍后</button>
        <template v-if="update?.prepared">
          <button class="button" :disabled="busy" @click="saveCopy">另存新版</button>
          <button class="button primary" :disabled="busy" @click="apply">重启更新</button>
        </template>
        <button v-else-if="update" class="button primary" :disabled="checking || busy" @click="download">下载更新</button>
        <button v-else class="button primary" :disabled="checking || busy" @click="check()">重新检查</button>
      </div>
    </div>
  </Modal></Teleport>
</template>
<style scoped>
.desktop-update-button { border: 0; background: transparent; color: var(--brand-600); font-size: var(--text-xs); white-space: nowrap; }
.desktop-update-body { display: grid; gap: 16px; }
.desktop-release-notes { white-space: pre-wrap; overflow-wrap: anywhere; max-height: 240px; overflow: auto; line-height: 1.8; }
.update-version { display: flex; align-items: center; gap: 14px; }
.update-version p { font-size: 12px; color: var(--ink-3); margin-top: 4px; }
.update-icon { display: grid; place-items: center; width: 48px; height: 48px; border: 1px solid var(--line-1); border-radius: 12px; background: var(--surface-2); color: var(--brand-600); }
.update-ready { display: flex; align-items: center; gap: 8px; color: var(--green-700); }
progress { width: 100%; accent-color: var(--brand-600); }
</style>
