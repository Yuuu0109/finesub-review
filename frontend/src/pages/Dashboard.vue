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
  <div class="page-heading dashboard-heading">
    <div>
      <h1>欢迎回来，{{ user?.name }}</h1>
    </div>
    <button
      v-if="user?.role === 'admin'"
      class="button primary"
      @click="go('imports')"
    >
      <Icon name="plus" :size="18" />导入知识库
    </button>
    <button v-else class="button primary" @click="go('entries')">
      <Icon name="book" :size="18" />浏览知识库
    </button>
  </div>
  <p v-if="error" class="form-error">{{ error }}</p>
  <template v-if="stats">
    <div class="metrics">
      <button @click="go('entries')">
        <span class="metric-label"
          >知识条目<Icon name="book" :size="18"
        /></span>
        <strong>{{ stats.total }}<small>条</small></strong>
        <span class="metric-foot"
          >全部知识<Icon name="arrow" :size="14"
        /></span>
      </button>
      <button class="metric-pending" @click="go('entries', 'pending')">
        <span class="metric-label"
          >等待裁决<Icon name="clock" :size="18"
        /></span>
        <strong class="amber-text"
          >{{ stats.counts.pending || 0 }}<small>条</small></strong
        >
        <span class="metric-foot"
          >查看待审词条<Icon name="arrow" :size="14"
        /></span>
      </button>
      <button @click="go('releases')">
        <span class="metric-label"
          >通过待发布<Icon name="check" :size="18"
        /></span>
        <strong class="green-text"
          >{{ stats.pending_publish }}<small>条</small></strong
        >
        <span class="metric-foot"
          >前往发布<Icon name="arrow" :size="14"
        /></span>
      </button>
      <button @click="go('mine')">
        <span class="metric-label"
          >分配给我<Icon name="users" :size="18"
        /></span>
        <strong>{{ stats.mine }}<small>条</small></strong>
        <span class="metric-foot"
          >我的审核<Icon name="arrow" :size="14"
        /></span>
      </button>
    </div>
    <div class="dashboard-columns">
      <section class="panel">
        <div class="panel-heading">
          <div class="heading-with-count">
            <h2>待裁决知识</h2>
            <span class="count-chip">{{ stats.counts.pending || 0 }}</span>
          </div>
          <button class="text-button" @click="go('entries', 'pending')">
            查看全部<Icon name="arrow" :size="16" />
          </button>
        </div>
        <div v-if="!entries.length" class="empty-state">
          <Icon name="check" :size="36" />
          <h3>{{ stats.total ? "待审知识已处理完毕" : "还没有待审知识" }}</h3>
          <button
            v-if="user?.role === 'admin' && !stats.total"
            class="button"
            @click="go('imports')"
          >
            导入知识库<Icon name="arrow" :size="16" />
          </button>
        </div>
        <button
          v-for="entry in entries"
          :key="entry.id"
          class="entry-preview"
          @click="go('review', entry.entry_id)"
        >
          <span class="entry-file"
            ><Icon
              :name="entry.category === 'translation' ? 'message' : 'file'"
          /></span>
          <span class="entry-preview-body"
            ><strong>{{ entry.title }}</strong
            ><small
              >{{ labels[entry.category]
              }}<span v-if="entry.kind"> / {{ entry.kind }}</span
              ><span> · v{{ entry.number }}</span></small
            ></span
          >
          <span class="review-count"
            ><Icon name="message" :size="15" />{{ entry.review_count }}</span
          >
          <span class="badge pending">待裁决</span
          ><Icon name="chevron" :size="16" />
        </button>
      </section>
      <div class="dashboard-side">
        <section class="panel">
          <div class="panel-heading">
            <h2>最近导入</h2>
            <Icon name="upload" :size="18" />
          </div>
          <p v-if="!stats.recent_batches.length" class="empty-small">
            暂无导入批次
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
        <section class="panel quick-links">
          <div class="panel-heading">
            <h2>继续协作</h2>
            <span class="muted small-text">{{ stats.reviews }} 条审核记录</span>
          </div>
          <button @click="go('mine')">
            <span class="quick-link-icon"><Icon name="check" :size="18" /></span
            ><span>我的审核</span
            ><Icon name="chevron" :size="16" />
          </button>
          <button @click="go('streamer')">
            <span class="quick-link-icon"><Icon name="users" :size="18" /></span
            ><span>主播档案</span
            ><Icon name="chevron" :size="16" />
          </button>
        </section>
      </div>
    </div>
  </template>
  <div v-else-if="!error" class="loading-state">
    <span class="spinner"></span>正在读取工作台
  </div>
</template>
