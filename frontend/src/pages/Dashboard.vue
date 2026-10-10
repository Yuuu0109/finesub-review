<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api, date, labels, type Entry } from "../api";
import { useApp } from "../context";
import Icon from "../components/Icon.vue";
const { user, go, toast } = useApp();
const stats = ref<any>(null),
  entries = ref<Entry[]>([]),
  error = ref("");
onMounted(async () => {
  try {
    const [s, e] = await Promise.all([
      api("/dashboard"),
      api("/entries?status=pending&limit=6"),
    ]);
    stats.value = s;
    entries.value = e.items;
  } catch (e) {
    error.value = (e as Error).message;
    toast(error.value, true);
  }
});
</script>
<template>
  <div class="page-heading">
    <div>
      <div class="eyebrow">工作台</div>
      <h1>把知识核实，再交给下一次翻译。</h1>
      <p>
        欢迎回来，{{
          user?.name
        }}。从待裁决的词条开始，查看内容和成员的审核记录。
      </p>
    </div>
    <button
      v-if="user?.role === 'admin'"
      class="button primary"
      @click="go('imports')"
    >
      <Icon name="plus" :size="18" />导入知识库
    </button>
  </div>
  <p v-if="error" class="form-error">{{ error }}</p>
  <template v-if="stats"
    ><div class="metrics">
      <button @click="go('entries')">
        <span>知识条目</span><strong>{{ stats.total }}<small>条</small></strong
        ><span class="metric-foot">已导入的全部知识</span></button
      ><button @click="go('entries')">
        <span>等待管理员裁决</span
        ><strong class="amber-text"
          >{{ stats.counts.pending || 0 }}<small>条</small></strong
        ><span class="metric-foot">意见记录不自动改变状态</span></button
      ><button @click="go('releases')">
        <span>通过，待发布</span
        ><strong class="green-text"
          >{{ stats.pending_publish }}<small>条</small></strong
        ><span class="metric-foot">由管理员选择发布</span></button
      ><button @click="go('mine')">
        <span>分配给我</span><strong>{{ stats.mine }}<small>条</small></strong
        ><span class="metric-foot">累计 {{ stats.reviews }} 条审核记录</span>
      </button>
    </div>
    <div class="dashboard-columns">
      <section class="panel">
        <div class="panel-heading">
          <div>
            <h2>待裁决知识</h2>
            <p>查看差异，留下可追溯的判断。</p>
          </div>
          <button class="text-button" @click="go('entries')">
            查看全部<Icon name="arrow" :size="16" />
          </button>
        </div>
        <div v-if="!entries.length" class="empty-state">
          <Icon name="book" :size="36" />
          <h3>还没有待裁决的词条</h3>
          <p>
            {{
              stats.total
                ? "所有当前词条都已有管理员决定。"
                : "管理员导入知识库后，待审核内容会出现在这里。"
            }}
          </p>
        </div>
        <button
          v-for="entry in entries"
          :key="entry.id"
          class="entry-preview"
          @click="go('review', entry.entry_id)"
        >
          <span class="entry-file"
            ><Icon
              :name="
                entry.category === 'translation' ? 'message' : 'file'
              " /></span
          ><span class="entry-preview-body"
            ><strong>{{ entry.title }}</strong
            ><small
              >{{ labels[entry.category]
              }}<span v-if="entry.kind"> / {{ entry.kind }}</span
              ><span> · v{{ entry.number }}</span></small
            ></span
          ><span class="review-count"
            ><Icon name="message" :size="15" />{{ entry.review_count }}</span
          ><span class="badge pending">待裁决</span
          ><Icon name="chevron" :size="16" />
        </button>
      </section>
      <div class="dashboard-side">
        <section class="panel">
          <div class="panel-heading">
            <h2>最近导入</h2>
            <Icon name="upload" :size="19" />
          </div>
          <p v-if="!stats.recent_batches.length" class="empty-small">
            暂无导入批次。
          </p>
          <button
            v-for="batch in stats.recent_batches"
            :key="batch.id"
            class="batch-preview"
            @click="go('imports', batch.id)"
          >
            <div>
              <strong>{{ batch.name }}</strong
              ><small>{{ date(batch.created_at) }}</small>
            </div>
            <span class="badge" :class="batch.status">{{
              labels[batch.status]
            }}</span>
          </button>
        </section>
        <section class="workflow-note">
          <span class="eyebrow">审核约定</span>
          <h3>意见留下来，决定有出处。</h3>
          <p>
            普通成员可以建议通过、修改或驳回，并补充依据。管理员查看记录后作出最终决定。
          </p>
          <div>
            <Icon name="shield" :size="16" /><span
              >正文更新后，旧意见仍保留在对应版本。</span
            >
          </div>
        </section>
      </div>
    </div></template
  >
  <div v-else-if="!error" class="loading-state">
    <span class="spinner"></span>正在读取工作台
  </div>
</template>
