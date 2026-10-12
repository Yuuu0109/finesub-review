<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { api, date, labels, type Entry } from "../api";
import { useApp } from "../context";
import Icon from "../components/Icon.vue";
const props = defineProps<{
  mine?: boolean;
  search?: string;
  initialStatus?: string;
}>();
const { go, toast, people } = useApp();
const rows = ref<Entry[]>([]),
  query = ref(props.search || ""),
  status = ref(
    ["pending", "needs_changes", "approved", "rejected"].includes(
      props.initialStatus || "",
    )
      ? props.initialStatus!
      : "",
  ),
  category = ref(""),
  page = ref(1),
  total = ref(0),
  loading = ref(false);
let sequence = 0;
async function load() {
  const current = ++sequence;
  loading.value = true;
  try {
    const p = new URLSearchParams({
      q: query.value,
      status: status.value,
      category: category.value,
      mine: String(!!props.mine),
      page: String(page.value),
    });
    const data = await api("/entries?" + p);
    if (current === sequence) {
      rows.value = data.items;
      total.value = data.total;
    }
  } catch (e) {
    toast((e as Error).message, true);
  } finally {
    if (current === sequence) loading.value = false;
  }
}
function filter() {
  page.value = 1;
  load();
}
watch(
  () => props.search,
  (v) => {
    query.value = v || "";
    filter();
  },
);
onMounted(load);
</script>
<template>
  <div class="page-heading">
    <div>
      <h1>{{ mine ? "我的审核" : "知识库" }}</h1>
    </div>
    <button class="button" @click="load">
      <Icon name="refresh" :size="17" />刷新
    </button>
  </div>
  <section class="panel">
    <form class="filter-bar" @submit.prevent="filter">
      <div class="search-field">
        <Icon name="search" :size="18" /><input
          v-model="query"
          aria-label="搜索词条"
          placeholder="搜索名称、别名或正文"
        />
      </div>
      <select v-model="category" aria-label="分类筛选" @change="filter">
        <option value="">全部分类</option>
        <option value="streamer">主播档案</option>
        <option value="common">通用知识</option>
        <option value="style">翻译风格</option>
        <option value="translation">翻译纠错</option></select
      ><select v-model="status" aria-label="审核状态筛选" @change="filter">
        <option value="">全部裁决状态</option>
        <option value="pending">待裁决</option>
        <option value="needs_changes">待补充</option>
        <option value="approved">已通过</option>
        <option value="rejected">已驳回</option></select
      ><button class="button" type="submit">查询</button
      ><span class="filter-count">{{ total }} 条知识</span>
    </form>
    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th class="entry-title-column">词条</th>
            <th>分类</th>
            <th>管理员决定</th>
            <th>成员记录</th>
            <th>负责人</th>
            <th>更新时间</th>
            <th><span class="sr-only">操作</span></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="entry in rows" :key="entry.id">
            <td>
              <button class="table-title" @click="go('review', entry.entry_id)">
                {{ entry.title
                }}<span
                  v-if="entry.operation === 'delete'"
                  class="badge rejected"
                  >拟删除</span
                >
              </button>
              <div class="table-subtitle">{{ entry.summary }}</div>
            </td>
            <td>
              <span>{{ labels[entry.category] }}</span
              ><small class="cell-note">{{ entry.kind || "—" }}</small>
            </td>
            <td>
              <span class="badge" :class="entry.status">{{
                labels[entry.status]
              }}</span
              ><small class="cell-note">{{
                entry.published ? "已发布" : "v" + entry.number
              }}</small>
            </td>
            <td>
              <span class="review-count"
                ><Icon name="message" :size="15" />{{
                  entry.review_count
                }}</span
              >
            </td>
            <td>
              {{
                people.find((p) => p.id === entry.assignee_id)?.name || "未分配"
              }}
            </td>
            <td class="nowrap muted">{{ date(entry.created_at) }}</td>
            <td>
              <button class="text-button" @click="go('review', entry.entry_id)">
                查看<Icon name="chevron" :size="14" />
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="!rows.length && !loading" class="empty-state">
      <Icon name="search" :size="32" />
      <h3>没有找到匹配的知识</h3>
      <p>
        {{
          mine
            ? "可以在知识库中认领任务，或等待管理员分配。"
            : "调整筛选条件，或导入一个新的知识库批次。"
        }}
      </p>
    </div>
    <div v-if="loading" class="loading-inline">正在读取…</div>
    <div class="pagination">
      <span
        >共 {{ total }} 条 · 第 {{ page }} /
        {{ Math.max(1, Math.ceil(total / 30)) }} 页</span
      >
      <div>
        <button
          class="button small"
          :disabled="page === 1 || loading"
          @click="
            page--;
            load();
          "
        >
          上一页</button
        ><button
          class="button small"
          :disabled="page * 30 >= total || loading"
          @click="
            page++;
            load();
          "
        >
          下一页
        </button>
      </div>
    </div>
  </section>
</template>
