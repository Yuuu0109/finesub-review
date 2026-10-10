<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { api, post, date, labels, type Detail, type RecordItem } from "../api";
import { useApp } from "../context";
import Icon from "../components/Icon.vue";
import Markdown from "../components/Markdown.vue";
import Diff from "../components/Diff.vue";
import Modal from "../components/Modal.vue";
const props = defineProps<{ entryId: string }>();
const { user, people, go, toast, refresh } = useApp();
const detail = ref<Detail | null>(null),
  loading = ref(true),
  busy = ref(false),
  tab = ref("read"),
  showHistory = ref(false);
const form = ref({
    verdict: "changes",
    body: "",
    quote: "",
    suggestion: "",
    evidence: "",
  }),
  decisionOpen = ref(false),
  decisionStatus = ref("approved"),
  decisionReason = ref("");
const editContent = ref(""),
  editBaseRevision = ref(""),
  editSource = ref(""),
  deleteEntry = ref(false),
  replyTo = ref<RecordItem | null>(null),
  replyText = ref("");
const resolveTarget = ref<RecordItem | null>(null),
  resolution = ref("accepted"),
  resolutionNote = ref("");
const admin = computed(() => user.value?.role === "admin"),
  isCurrent = computed(
    () => detail.value?.entry.id === detail.value?.entry.current_revision,
  );
const visibleRecords = computed(
  () =>
    detail.value?.reviews.filter(
      (r) => showHistory.value || r.revision_id === detail.value?.entry.id,
    ) || [],
);
const roots = computed(() => visibleRecords.value.filter((r) => !r.parent_id));
const currentRecords = computed(
  () =>
    detail.value?.reviews.filter(
      (r) => r.revision_id === detail.value?.entry.id && r.verdict !== "reply",
    ) || [],
);
const latestDecision = computed(() =>
  detail.value?.decisions.find((d) => d.revision_id === detail.value?.entry.id),
);
const draftKey = computed(
  () => `finesub-draft:${user.value?.id}:${detail.value?.entry.id}`,
);
const editDraftKey = computed(
  () => `finesub-edit:${user.value?.id}:${props.entryId}`,
);
const editStale = computed(() => editBaseRevision.value !== detail.value?.entry.id);
let restoring = false;
async function load(version = "") {
  loading.value = true;
  try {
    const d = await api<Detail>(
      `/entries/${props.entryId}${version ? "?revision_id=" + version : ""}`,
    );
    restoring = true;
    detail.value = d;
    editContent.value = d.entry.content;
    editBaseRevision.value = d.entry.id;
    editSource.value = d.entry.source;
    deleteEntry.value = d.entry.operation === "delete";
    const editDraft = d.entry.id === d.entry.current_revision ? sessionStorage.getItem(editDraftKey.value) : null;
    if (editDraft) {
      try {
        const saved = JSON.parse(editDraft);
        editContent.value = saved.content;
        editBaseRevision.value = saved.baseRevision || d.entry.id;
        editSource.value = saved.source;
        deleteEntry.value = saved.deleteEntry;
      } catch { sessionStorage.removeItem(editDraftKey.value); }
    }
    const draft = sessionStorage.getItem(draftKey.value);
    form.value = draft
      ? JSON.parse(draft)
      : {
          verdict: "changes",
          body: "",
          quote: "",
          suggestion: "",
          evidence: "",
        };
    setTimeout(() => (restoring = false), 0);
  } catch (e) {
    toast((e as Error).message, true);
  } finally {
    loading.value = false;
  }
}
watch(
  [editContent, editSource, deleteEntry, editBaseRevision],
  () => {
    if (!restoring && detail.value && isCurrent.value)
      sessionStorage.setItem(editDraftKey.value, JSON.stringify({
        content: editContent.value, baseRevision: editBaseRevision.value, source: editSource.value, deleteEntry: deleteEntry.value,
      }));
  },
);
watch(
  form,
  () => {
    if (!restoring && detail.value)
      sessionStorage.setItem(draftKey.value, JSON.stringify(form.value));
  },
  { deep: true },
);
async function act(fn: () => Promise<void>) {
  if (busy.value) return;
  busy.value = true;
  try {
    await fn();
    await refresh();
  } catch (e) {
    toast((e as Error).message, true);
  } finally {
    busy.value = false;
  }
}
function submitRecord() {
  if (!detail.value) return;
  act(async () => {
    const rid = detail.value!.entry.id;
    await post(`/entries/${props.entryId}/reviews`, {
      ...form.value,
      revision_id: rid,
    });
    sessionStorage.removeItem(draftKey.value);
    await load(rid);
    toast("审核记录已提交，最终决定由管理员作出");
  });
}
function submitDecision() {
  act(async () => {
    await post(`/entries/${props.entryId}/decision`, {
      revision_id: detail.value!.entry.id,
      status: decisionStatus.value,
      reason: decisionReason.value,
    });
    decisionOpen.value = false;
    decisionReason.value = "";
    await load();
    toast("管理员决定已保存");
  });
}
function saveRevision() {
  act(async () => {
    await post(`/entries/${props.entryId}/revisions`, {
      base_revision: editBaseRevision.value,
      content: editContent.value,
      source: editSource.value,
      operation: deleteEntry.value ? "delete" : "upsert",
    });
    sessionStorage.removeItem(editDraftKey.value);
    tab.value = "diff";
    await load();
    toast("已生成新的待裁决版本，旧审核记录已保留");
  });
}
function submitReply() {
  act(async () => {
    await post(`/entries/${props.entryId}/reviews`, {
      revision_id: replyTo.value!.revision_id,
      parent_id: replyTo.value!.id,
      verdict: "reply",
      body: replyText.value,
    });
    replyTo.value = null;
    replyText.value = "";
    await load(detail.value!.entry.id);
    toast("回复已保存");
  });
}
function resolve() {
  act(async () => {
    await api(`/reviews/${resolveTarget.value!.id}`, {
      method: "PATCH",
      body: JSON.stringify({
        resolution: resolution.value,
        note: resolutionNote.value,
      }),
    });
    resolveTarget.value = null;
    resolutionNote.value = "";
    await load(detail.value!.entry.id);
    toast("意见处理结果已保存");
  });
}
function assign(id: string | null) {
  act(async () => {
    await api(`/entries/${props.entryId}/assignee`, {
      method: "PUT",
      body: JSON.stringify({ user_id: id }),
    });
    await load(detail.value!.entry.id);
    toast(id ? "审核任务已分配" : "已取消认领");
  });
}
function quoteSelection() {
  const selection = window.getSelection()?.toString().trim();
  if (selection && detail.value?.entry.content.includes(selection)) {
    form.value.quote = selection;
    toast("已引用所选文字");
  } else toast("请先在正文中选中要讨论的原文", true);
}
async function next() {
  try {
    const data = await api("/entries?status=pending&limit=100");
    const other = data.items.find((e: any) => e.entry_id !== props.entryId);
    if (other) go("review", other.entry_id);
    else toast("当前没有其他待裁决的词条");
  } catch (e) {
    toast((e as Error).message, true);
  }
}
onMounted(() => load());
</script>
<template>
  <div v-if="loading && !detail" class="loading-state">
    <span class="spinner"></span>正在读取词条
  </div>
  <template v-if="detail"
    ><div class="review-top">
      <button class="text-button muted" @click="go('entries')">
        <Icon name="back" :size="16" />知识库
      </button>
      <div class="review-top-actions">
        <span class="muted"
          >{{ labels[detail.entry.category] }} /
          {{ detail.entry.path.split("/").pop() }}</span
        ><button class="button small" @click="next">
          下一条待审<Icon name="arrow" :size="15" />
        </button>
      </div>
    </div>
    <div class="review-heading">
      <div>
        <div class="inline-meta">
          <span class="eyebrow">{{ labels[detail.entry.category] }}</span
          ><span v-if="detail.entry.kind" class="tag">{{
            detail.entry.kind
          }}</span
          ><span class="tag">v{{ detail.entry.number }}</span
          ><span v-if="!isCurrent" class="badge needs_changes">历史版本</span
          ><span
            v-if="detail.entry.operation === 'delete'"
            class="badge rejected"
            >拟删除</span
          >
        </div>
        <h1>{{ detail.entry.title }}</h1>
        <p>{{ detail.entry.summary }}</p>
      </div>
      <span class="badge large" :class="detail.entry.status">{{
        labels[detail.entry.status]
      }}</span>
    </div>
    <div class="review-grid">
      <aside class="review-directory">
        <div class="directory-section">
          <h3>词条信息</h3>
          <dl>
            <dt>当前版本</dt>
            <dd>v{{ detail.entry.number }}</dd>
            <dt>更新时间</dt>
            <dd>{{ date(detail.entry.created_at) }}</dd>
            <dt>发布状态</dt>
            <dd>
              {{ detail.entry.published ? "已进入当前发布" : "尚未发布" }}
            </dd>
          </dl>
        </div>
        <div class="directory-section">
          <h3>审核负责人</h3>
          <select
            v-if="admin"
            :value="detail.entry.assignee_id || ''"
            aria-label="分配审核负责人"
            :disabled="busy"
            @change="assign(($event.target as HTMLSelectElement).value || null)"
          >
            <option value="">未分配</option>
            <option
              v-for="person in people.filter((p) => p.active)"
              :key="person.id"
              :value="person.id"
            >
              {{ person.name }}
            </option></select
          ><template v-else
            ><p>
              {{
                people.find((p) => p.id === detail?.entry.assignee_id)?.name ||
                "未分配"
              }}
            </p>
            <button
              v-if="
                !detail.entry.assignee_id ||
                detail.entry.assignee_id === user?.id
              "
              class="button small full"
              :disabled="busy"
              @click="assign(detail.entry.assignee_id ? null : user!.id)"
            >
              {{ detail.entry.assignee_id ? "取消认领" : "认领此词条" }}
            </button></template
          >
        </div>
        <div class="directory-section">
          <h3>版本历史</h3>
          <button
            v-for="version in detail.versions"
            :key="version.id"
            class="version-item"
            :class="{ selected: version.id === detail.entry.id }"
            @click="
              tab = 'read';
              load(version.id);
            "
          >
            <span
              >v{{ version.number
              }}<small>{{ date(version.created_at) }}</small></span
            ><span class="version-dot" :class="version.status"></span>
          </button>
        </div>
        <div class="directory-section">
          <h3>来源</h3>
          <p class="source-text">{{ detail.entry.source || "尚未补充来源" }}</p>
        </div>
      </aside>
      <section class="document-panel panel">
        <div class="document-toolbar">
          <div class="tabs">
            <button :class="{ active: tab === 'read' }" @click="tab = 'read'">
              正文</button
            ><button :class="{ active: tab === 'diff' }" @click="tab = 'diff'">
              版本差异</button
            ><button :class="{ active: tab === 'raw' }" @click="tab = 'raw'">
              原文</button
            ><button
              v-if="admin && isCurrent"
              :class="{ active: tab === 'edit' }"
              @click="tab = 'edit'"
            >
              修订
            </button>
          </div>
          <button
            v-if="tab === 'read'"
            class="icon-button"
            aria-label="引用所选文字"
            title="引用所选文字"
            @mousedown.prevent
            @click="quoteSelection"
          >
            <Icon name="message" :size="17" />
          </button>
        </div>
        <div v-if="detail.errors.length" class="validation-box error">
          <strong>发布前需要修正</strong>
          <p v-for="item in detail.errors" :key="item">{{ item }}</p>
        </div>
        <details v-if="detail.warnings.length" class="validation-box">
          <summary>{{ detail.warnings.length }} 项核实提示</summary>
          <p v-for="item in detail.warnings" :key="item">{{ item }}</p>
        </details>
        <Markdown v-if="tab === 'read'" :text="detail.entry.content" /><Diff
          v-else-if="tab === 'diff'"
          :lines="detail.diff"
        />
        <pre v-else-if="tab === 'raw'" class="raw-document">{{
          detail.entry.content
        }}</pre>
        <form v-else class="edit-form" @submit.prevent="saveRevision">
          <p v-if="detail.warnings.some(w => w.startsWith('历史正文定点兼容'))" class="callout">
            旧知识可保留原章节，修订简介或现有节点的值。新增、删除、重排节点及修改名称、别名等匹配字段需单独整理；无法可靠兼容时会保留草稿并说明原因。
          </p>
          <p class="callout">
            保存将产生新的待裁决版本。历史正文与成员记录会完整保留。
          </p>
          <div v-if="editStale" class="callout">
            草稿基于旧版本，已保留。请先查看最新正文并手动合并，再继续修订。
            <button type="button" class="text-button" @click="editBaseRevision = detail.entry.id">
              已对照当前版本，保留草稿继续修订
            </button>
          </div>
          <label
            >Markdown 正文<textarea
              v-model="editContent"
              class="code-editor"
              spellcheck="false"
              rows="24"
            ></textarea></label
          ><label
            >来源说明<textarea
              v-model="editSource"
              rows="2"
              placeholder="节目期数、时间码或参考来源"
            ></textarea></label
          ><label class="checkbox-label"
            ><input
              v-model="deleteEntry"
              type="checkbox"
            />将此修订标记为删除提案</label
          >
          <p v-if="deleteEntry" class="form-error">
            只有此提案获管理员通过并发布后，正式知识库才会移除此词条。
          </p>
          <button class="button primary" :disabled="busy || editStale">保存为新版本</button>
        </form>
      </section>
      <aside class="review-sidebar">
        <section class="decision-panel">
          <div class="section-label">
            <Icon name="shield" :size="17" />
            <h2>管理员最终决定</h2>
          </div>
          <div class="decision-status">
            <span class="badge" :class="detail.entry.status">{{
              labels[detail.entry.status]
            }}</span
            ><span v-if="detail.entry.published" class="muted">已发布</span>
          </div>
          <p v-if="latestDecision" class="decision-reason">
            {{ latestDecision.reason
            }}<small
              >{{ latestDecision.author }} ·
              {{ date(latestDecision.created_at) }}</small
            >
          </p>
          <p v-else class="muted small-text">
            暂无最终决定。成员提交的审核记录仅供管理员参考。
          </p>
          <button
            v-if="admin && isCurrent && !detail.entry.published"
            class="button primary full"
            :disabled="busy"
            @click="decisionOpen = true"
          >
            作出管理员决定<Icon name="arrow" :size="16" />
          </button>
        </section>
        <section class="records-panel">
          <div class="section-label">
            <Icon name="message" :size="17" />
            <h2>成员审核记录</h2>
            <span class="count-chip">{{ currentRecords.length }}</span>
          </div>
          <p class="muted small-text">意见会被记录，不会自动通过或驳回词条。</p>
          <label class="checkbox-label history-toggle"
            ><input
              v-model="showHistory"
              type="checkbox"
            />包含其他版本的记录</label
          >
          <div v-if="!roots.length" class="record-empty">
            还没有审核记录。<br />可以在下方留下你的判断和依据。
          </div>
          <article v-for="record in roots" :key="record.id" class="record">
            <div class="record-header">
              <span class="avatar small">{{ record.author.slice(0, 1) }}</span
              ><strong>{{ record.author }}</strong
              ><small>{{ date(record.created_at) }}</small>
            </div>
            <div class="record-tags">
              <span class="opinion-label" :class="record.verdict">{{
                labels[record.verdict]
              }}</span
              ><span v-if="record.stale" class="tag">历史版本</span
              ><span v-if="record.resolution !== 'open'" class="tag">{{
                labels[record.resolution]
              }}</span>
            </div>
            <blockquote v-if="record.quote">{{ record.quote }}</blockquote>
            <p class="preserve-lines">{{ record.body }}</p>
            <div v-if="record.suggestion" class="record-evidence">
              <strong>建议文本</strong>
              <p>{{ record.suggestion }}</p>
            </div>
            <div v-if="record.evidence" class="record-evidence">
              <strong>依据</strong>
              <p>{{ record.evidence }}</p>
            </div>
            <div v-if="record.resolution_note" class="resolution-note">
              <strong>管理员处理说明</strong>
              <p>{{ record.resolution_note }}</p>
            </div>
            <div class="record-actions">
              <button class="text-button" @click="replyTo = record">回复</button
              ><button
                v-if="admin"
                class="text-button"
                @click="
                  resolveTarget = record;
                  resolution =
                    record.resolution === 'open'
                      ? 'accepted'
                      : record.resolution;
                  resolutionNote = record.resolution_note;
                "
              >
                处理意见
              </button>
            </div>
            <div
              v-for="reply in visibleRecords.filter(
                (r) => r.parent_id === record.id,
              )"
              :key="reply.id"
              class="reply"
            >
              <strong>{{ reply.author }}</strong>
              <p>{{ reply.body }}</p>
              <small>{{ date(reply.created_at) }}</small>
            </div>
          </article>
          <form class="record-form" @submit.prevent="submitRecord">
            <h3>提交审核记录</h3>
            <label
              >你的判断<select v-model="form.verdict">
                <option value="approve">建议通过</option>
                <option value="changes">建议修改</option>
                <option value="reject">建议驳回</option>
                <option value="evidence">证据不足</option>
              </select></label
            ><label
              >意见说明<textarea
                v-model="form.body"
                rows="4"
                required
                maxlength="15000"
                placeholder="具体哪里需要确认？请说明你的理由。"
              ></textarea>
            </label>
            <details :open="!!form.quote">
              <summary>引用原文与建议文本</summary>
              <label
                >引用原文<textarea
                  v-model="form.quote"
                  rows="2"
                  placeholder="粘贴当前版本中的文字"
                ></textarea></label
              ><label
                >建议替换为<textarea
                  v-model="form.suggestion"
                  rows="3"
                  placeholder="仅作为建议，不直接修改正文"
                ></textarea>
              </label>
            </details>
            <label
              >依据（选填）<textarea
                v-model="form.evidence"
                rows="2"
                placeholder="例如：第 20 期，12:34，日文原句或来源链接"
              ></textarea>
            </label>
            <div class="record-submit">
              <small>记录将关联 v{{ detail.entry.number }}</small
              ><button
                class="button primary"
                :disabled="busy || !form.body.trim()"
              >
                提交记录
              </button>
            </div>
          </form>
        </section>
      </aside>
    </div></template
  >
  <div v-else-if="!loading" class="empty-state">
    <h2>无法读取词条</h2>
    <button class="button" @click="load()">重试</button>
  </div>
  <Modal
    v-if="decisionOpen"
    title="管理员最终决定"
    @close="decisionOpen = false"
    ><form @submit.prevent="submitDecision">
      <p class="callout">
        针对「{{ detail?.entry.title }}」v{{
          detail?.entry.number
        }}
        作出决定。成员意见数量不限制你的决定。
      </p>
      <label
        >决定<select v-model="decisionStatus">
          <option value="approved">通过，等待发布</option>
          <option value="needs_changes">待补充 / 需修改</option>
          <option value="rejected">驳回</option>
          <option value="pending">重新进入待裁决</option>
        </select></label
      ><label
        >决定理由<textarea
          v-model="decisionReason"
          required
          rows="4"
          placeholder="说明采纳的依据或需要补充的内容"
        ></textarea>
      </label>
      <div class="modal-actions">
        <button type="button" class="button" @click="decisionOpen = false">
          取消</button
        ><button class="button primary" :disabled="busy">确认决定</button>
      </div>
    </form></Modal
  >
  <Modal v-if="replyTo" title="回复审核记录" @close="replyTo = null"
    ><form @submit.prevent="submitReply">
      <blockquote>{{ replyTo.body }}</blockquote>
      <label
        >回复内容<textarea
          v-model="replyText"
          required
          rows="4"
          placeholder="补充你的说明"
        ></textarea>
      </label>
      <div class="modal-actions">
        <button class="button primary" :disabled="busy">保存回复</button>
      </div>
    </form></Modal
  >
  <Modal v-if="resolveTarget" title="处理成员意见" @close="resolveTarget = null"
    ><form @submit.prevent="resolve">
      <blockquote>{{ resolveTarget.body }}</blockquote>
      <label
        >处理结果<select v-model="resolution">
          <option value="accepted">已采纳</option>
          <option value="partial">部分采纳</option>
          <option value="declined">不采纳</option>
          <option value="more_evidence">待补充依据</option>
          <option value="open">重新打开</option>
        </select></label
      ><label
        >处理说明<textarea
          v-model="resolutionNote"
          required
          rows="4"
          placeholder="记录采纳方式或不采纳的理由"
        ></textarea>
      </label>
      <p class="muted small-text">
        采纳标记不会修改正文；需要更新知识时，请到“修订”页保存新版本。
      </p>
      <div class="modal-actions">
        <button class="button primary" :disabled="busy">保存处理结果</button>
      </div>
    </form></Modal
  >
</template>
