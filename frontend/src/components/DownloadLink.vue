<script setup lang="ts">
import { ref } from "vue";
import { desktop } from "../transport";
import { apiResponse } from "../api";
import { downloadFilename } from "../server";
import { useApp } from "../context";
const props = defineProps<{ path: string; filename?: string }>();
const busy = ref(false);
const { toast } = useApp();
async function download(event: MouseEvent) {
  if (!desktop) return;
  event.preventDefault();
  if (busy.value) return;
  busy.value = true;
  try {
    const response = await apiResponse(props.path);
    const { save } = await import("@tauri-apps/plugin-dialog");
    const { writeFile } = await import("@tauri-apps/plugin-fs");
    const bytes = new Uint8Array(await response.arrayBuffer());
    const path = await save({ defaultPath: downloadFilename(response.headers.get("content-disposition"), props.filename || "download.zip") });
    if (path) {
      await writeFile(path, bytes);
      toast("文件已保存");
    }
  } catch (e) {
    toast(e instanceof Error ? e.message : String(e), true);
  } finally {
    busy.value = false;
  }
}
</script>
<template><a :href="'/api' + path" :aria-disabled="busy" @click="download"><slot />{{ busy ? " · 正在下载…" : "" }}</a></template>
