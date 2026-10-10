<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { api, post, date, labels, type Entry, type Release } from "../api";
import { useApp } from "../context";
import Icon from "../components/Icon.vue";
import Modal from "../components/Modal.vue";
const { user, go, toast, refresh } = useApp();
const rows = ref<Release[]>([]),
  candidates = ref<Entry[]>([]),
  selected = ref<string[]>([]),
  busy = ref(false),
  publishOpen = ref(false),
  rollback = ref<Release | null>(null),
  name = ref(""),
  notes = ref("");
const admin = computed(() => user.value?.role === "admin");
let timer: ReturnType<typeof setInterval>;
async function load() {
  try {
    rows.value = await api("/releases");
    let result: Entry[] = [];
    for (let page = 1; page <= 20; page++) {
      const data = await api(`/entries?status=approved&limit=100&page=${page}`);
      result.push(...data.items);
      if (page * 100 >= data.total) break;
    }
    candidates.value = result.filter((e) => !e.published);
    selected.value = selected.value.filter((id) =>
      candidates.value.some((c) => c.id === id),
    );
  } catch (e) {
    toast((e as Error).message, true);
  }
}
function startPublish() {
  rollback.value = null;
  name.value = `知识库 · ${new Date().toLocaleDateString("zh-CN")}`;
  notes.value = "";
  publishOpen.value = true;
}
function startRollback(row: Release) {
  rollback.value = row;
  name.value = `回退至 ${row.name}`;
  notes.value = "";
  publishOpen.value = true;
}
async function publish() {
  busy.value = true;
  try {
    await post("/releases", {
      name: name.value,
      notes: notes.value,
      revision_ids: rollback.value ? [] : selected.value,
      rollback_id: rollback.value?.id || null,
    });
    publishOpen.value = false;
    selected.value = [];
    await load();
    await refresh();
    toast("发布任务已创建，正在生成并校验完整知识库");
  } catch (e) {
    toast((e as Error).message, true);
  } finally {
    busy.value = false;
  }
}
async function retry(id: string) {
  busy.value = true;
  try {
    await post("/jobs/" + id + "/retry");
    await load();
  } catch (e) {
    toast((e as Error).message, true);
  } finally {
    busy.value = false;
  }
}
onMounted(() => {
  load();
  timer = setInterval(() => {
    if (rows.value.some((r) => ["queued", "processing"].includes(r.status)))
      load();
  }, 2500);
});
onUnmounted(() => clearInterval(timer));
</script>
<template>
  <div class="page-heading">
    <div>
      <div class="eyebrow">发布中心</div>
      <h1>让审核通过的知识，进入正式版本。</h1>
      <p>每次发布都会保留未变更的正式知识，并生成可追溯的完整知识库包。</p>
    </div>
    <button class="button" @click="load">
      <Icon name="refresh" :size="17" />刷新
    </button>
  </div>
  <section v-if="admin" class="panel release-candidates">
    <div class="panel-heading">
      <div>
        <h2>
          待发布变更 <span class="count-chip">{{ candidates.length }}</span>
        </h2>
        <p>只有管理员已通过的最新版本可以加入本次发布。</p>
      </div>
      <button
        class="button primary"
        :disabled="!selected.length || busy"
        @click="startPublish"
      >
        <Icon name="plus" :size="17" />创建发布 · {{ selected.length }}
      </button>
    </div>
    <div v-if="candidates.length" class="content-pad">
      <label class="checkbox-label"
        ><input
          type="checkbox"
          :checked="selected.length === candidates.length"
          @change="
            selected = ($event.target as HTMLInputElement).checked
              ? candidates.map((c) => c.id)
              : []
          "
        />选择全部待发布变更</label
      >
      <div class="candidate-grid">
        <label v-for="item in candidates" :key="item.id" class="candidate-item"
          ><input v-model="selected" :value="item.id" type="checkbox" /><span
            ><strong>{{ item.title }}</strong
            ><small
              >{{ labels[item.category] }} · v{{ item.number
              }}<span v-if="item.group_id"> · 关联变更组</span></small
            ></span
          ><span
            class="badge"
            :class="item.operation === 'delete' ? 'rejected' : 'approved'"
            >{{ item.operation === "delete" ? "拟删除" : "已通过" }}</span
          ></label
        >
      </div>
    </div>
    <div v-else class="empty-small">
      暂无新的已通过变更。管理员完成裁决后，内容会出现在这里。
    </div>
  </section>
  <div class="section-heading">
    <h2>历史发布</h2>
    <span class="muted">{{ rows.length }} 个版本</span>
  </div>
  <div v-if="!rows.length" class="panel empty-state">
    <Icon name="download" :size="36" />
    <h3>还没有发布版本</h3>
    <p>首次发布将从已通过的知识开始建立正式版本。</p>
  </div>
  <article v-for="row in rows" :key="row.id" class="panel release-card">
    <div class="release-icon">
      <Icon :name="row.rollback_of ? 'refresh' : 'book'" :size="24" />
    </div>
    <div class="release-body">
      <div class="release-title">
        <h2>{{ row.name }}</h2>
        <span class="badge" :class="row.status">{{ labels[row.status] }}</span
        ><span v-if="row.current" class="tag current">当前正式版本</span>
      </div>
      <p>{{ row.notes || "未填写发布说明" }}</p>
      <div class="release-meta">
        <span>{{ date(row.created_at) }}</span
        ><span>{{ row.count }} 个知识记录</span
        ><span v-if="row.report.files">{{ row.report.files }} 个导出文件</span
        ><code>{{ row.id.slice(0, 8) }}</code>
      </div>
      <div v-if="row.report.errors?.length" class="form-error">
        <p v-for="error in row.report.errors" :key="error">{{ error }}</p>
      </div>
      <p v-if="row.report.native_import_requires_compat_tool" class="callout">
        此版本含保留旧节点的兼容修改。请通过专用导入工具应用知识库包；直接覆盖原生知识正文会触发重新归类。
      </p>
      <details v-if="row.report.warnings?.length" class="release-warnings">
        <summary>{{ row.report.warnings.length }} 项兼容提示</summary>
        <p v-for="warning in row.report.warnings" :key="warning">
          {{ warning }}
        </p>
      </details>
    </div>
    <div v-if="admin" class="release-actions">
      <template v-if="row.status === 'ready'"
        ><a
          class="button primary small"
          :href="'/api/releases/' + row.id + '/download'"
          ><Icon name="download" :size="15" />{{ row.report.native_import_requires_compat_tool ? '兼容知识库包' : '知识库包' }}</a
        ><a
          class="button small"
          :href="'/api/releases/' + row.id + '/download?archive=true'"
          >审核归档</a
        ><button
          v-if="!row.current"
          class="text-button"
          @click="startRollback(row)"
        >
          回退到此版本
        </button></template
      ><button
        v-else-if="row.status === 'failed'"
        class="button"
        :disabled="busy"
        @click="retry(row.job_id)"
      >
        重试生成</button
      ><span v-else class="muted">正在生成…</span>
    </div>
  </article>
  <Modal
    v-if="publishOpen"
    :title="rollback ? '回退正式知识库' : '创建发布版本'"
    @close="publishOpen = false"
    ><form @submit.prevent="publish">
      <div class="callout">
        {{
          rollback
            ? `将正式知识库恢复为「${rollback.name}」的完整内容，系统会生成新的发布记录。`
            : "本次变更将合入当前正式知识库，未变更的内容会保留。"
        }}
      </div>
      <label>版本名称<input v-model="name" required maxlength="120" /></label
      ><label
        >发布说明<textarea
          v-model="notes"
          :required="!!rollback"
          rows="3"
          :placeholder="rollback ? '说明此次回退的原因' : '概括本次知识变更'"
        ></textarea>
      </label>
      <ul v-if="!rollback" class="confirmation-list">
        <li
          v-for="item in candidates.filter((c) => selected.includes(c.id))"
          :key="item.id"
        >
          {{ item.path }}<span>v{{ item.number }}</span>
        </li>
      </ul>
      <div class="modal-actions">
        <button type="button" class="button" @click="publishOpen = false">
          取消</button
        ><button class="button primary" :disabled="busy">
          {{ rollback ? "确认回退并生成版本" : "确认并生成发布包" }}
        </button>
      </div>
    </form></Modal
  >
</template>
