<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api, date, labels, type Detail, type Entry } from "../api";
import { useApp } from "../context";
import Icon from "../components/Icon.vue";
import Markdown from "../components/Markdown.vue";

const props = defineProps<{ entryId?: string }>();
const { go, toast, settings } = useApp();

const loading = ref(true),
  error = ref(""),
  profile = ref<Detail | null>(null),
  entries = ref<Entry[]>([]),
  typeFilter = ref("");

/* ---------------------------------------------------------------- 解析 */

type Field = { key: string; value: string };
type Nest = { depth: number; value: string };

function splitSections(md: string): Record<string, string> {
  const out: Record<string, string> = {};
  let heading = "";
  let buffer: string[] = [];
  const flush = () => {
    if (heading) out[heading] = buffer.join("\n").trim();
  };
  for (const line of md.split(/\r?\n/)) {
    const found = line.match(/^#{1,3}\s+(.+?)\s*$/);
    if (found) {
      flush();
      heading = found[1]!;
      buffer = [];
    } else buffer.push(line);
  }
  flush();
  return out;
}

function strip(value: string): string {
  return value.replace(/^-\s*/, "").trim();
}

function fields(text: string): Field[] {
  return (text ?? "").replace(/<!--[^]*?-->/g, "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("#"))
    .map(strip)
    .map((line) => {
      const label = line.match(/^\[([^\[\]]+)\]\s?(.*)$/);
      if (label) return { key: label[1]!.trim(), value: label[2]!.trim() };
      const at = line.search(/[:：]/);
      return at > 0
        ? { key: line.slice(0, at).trim(), value: line.slice(at + 1).trim() }
        : { key: "", value: line };
    })
    .filter((item) => item.value);
}

function pick(list: Field[], key: string): string {
  return list.find((item) => item.key === key)?.value ?? "";
}

// 有些条目写作「- 节目问候梗「…」「…」」而没有冒号，需要按前缀找整行。
function prefix(list: Field[], head: string): string {
  const hit = list.find((item) => item.value.startsWith(head));
  return hit ? hit.value.slice(head.length).replace(/^[:：]\s*/, "") : "";
}

function bullets(text: string): string[] {
  return (text ?? "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.startsWith("-"))
    .map(strip);
}

function nests(text: string): Nest[] {
  return (text ?? "")
    .split(/\r?\n/)
    .filter((line) => line.trim().startsWith("-"))
    .map((line) => ({
      depth: Math.floor((line.length - line.trimStart().length) / 2),
      value: strip(line),
    }));
}

function quotes(text: string): string[] {
  return [...(text ?? "").matchAll(/「([^」]+)」/g)].map((match) => match[1]!);
}

const visibleContent = computed(() => (profile.value?.entry.content ?? "").replace(/<!--[^]*?-->/g, ""));
const sections = computed(() => splitSections(visibleContent.value));
const nodeFormat = computed(() => settings.value.profile === "finesub-0.5.1" || /^(?:-\s+)?\[[^\[\]]+\]/m.test(visibleContent.value));

const intro = computed(
  () =>
    visibleContent.value
      .split(/\r?\n/)
      .find((line) => line.trim() && !line.startsWith("#"))
      ?.trim() ?? "",
);

const registry = computed(() => fields(sections.value["档案"] ?? ""));

const basics = computed(() => {
  const list = fields(sections.value["基本信息"] ?? "");
  return [
    { key: "生日", value: pick(list, "生日") },
    { key: "出身地", value: pick(list, "出身地") },
    { key: "身高", value: pick(list, "身高") },
    { key: "血型", value: pick(list, "血型") },
    { key: "事务所", value: pick(list, "事务所") },
    { key: "特长", value: pick(list, "特长") },
  ].filter((item) => item.value);
});

const names = computed(() =>
  pick(registry.value, "别名")
    .split(/[,、，]/)
    .map((item) => item.replace(/（[^）]*）/g, "").trim())
    .filter(Boolean),
);

const basicName = computed(() =>
  pick(registry.value, "本名").split(/[／/]/).map((item) => item.trim()),
);

const live = computed(() => fields(sections.value["直播内容"] ?? ""));

const segments = computed(() =>
  pick(live.value, "固定环节")
    .split("、")
    .map((item) =>
      item
        .replace(/等（[^）]*）$/, "")
        .replace(/等$/, "")
        .trim(),
    )
    .filter(Boolean)
    .map((item) => {
      const found = item.match(/^(.+?)（([^）]*)）$/);
      return found
        ? { name: found[1]!.trim(), note: found[2]!.trim() }
        : { name: item, note: "" };
    }),
);

const greetings = computed(() =>
  quotes(prefix(live.value, "节目问候梗")).map((name) => ({
    name,
    note: "节目问候",
  })),
);

const style = computed(() => fields(sections.value["说话风格"] ?? ""));

const catchphrases = computed(() => quotes(pick(style.value, "口癖")));

const timeline = computed(() =>
  bullets(sections.value["重要经历"] ?? "").map((line) => {
    // 日期写法不统一：「2024-12」「2026-03-23」「2025 年末」「2026-07~08」。
    const found = line.match(/^(\d{4}[^:：]*?)\s*[:：]\s*(.+)$/);
    return found
      ? { date: found[1]!.trim(), text: found[2]! }
      : { date: "", text: line };
  }),
);

const relations = computed(() => {
  const list = nests(sections.value["人际关系"] ?? "");
  const groups: {
    title: string;
    note: string;
    items: { name: string; note: string }[];
  }[] = [];
  for (const item of list) {
    const at = item.value.search(/[:：]/);
    const head = at > 0 ? item.value.slice(0, at).trim() : item.value.trim();
    const rest = at > 0 ? item.value.slice(at + 1).trim() : "";
    if (item.depth === 0) {
      groups.push({ title: head, note: rest, items: [] });
      continue;
    }
    const group = groups[groups.length - 1];
    if (!group) continue;
    if (!rest) {
      // 纯补充说明：并入上一位成员，或作为整组的说明
      const last = group.items[group.items.length - 1];
      if (last) last.note = `${last.note}（${head}）`.trim();
      else group.note = `${group.note}（${head}）`.trim();
      continue;
    }
    group.items.push({ name: head, note: rest });
  }
  return groups;
});

const kindOf = (item: Entry) => item.kind || "未标注类型";

const kinds = computed(() => {
  const seen = new Map<string, number>();
  for (const item of entries.value)
    seen.set(kindOf(item), (seen.get(kindOf(item)) ?? 0) + 1);
  return [...seen.entries()].sort((a, b) => b[1] - a[1]);
});

// 翻译纠错词条本身没有「类型」字段，属正常；只统计应填而未填的。
const untyped = computed(() =>
  entries.value.filter((item) => !item.kind && item.category !== "translation"),
);

const visibleEntries = computed(() =>
  typeFilter.value
    ? entries.value.filter((item) => kindOf(item) === typeFilter.value)
    : entries.value,
);

const profileEntryId = computed(() => profile.value?.entry.entry_id ?? "");

/* ------------------------------------------------------- 联网核对补充 */
// 已公开可查、但当前知识库档案里尚未收录的信息。核对后可作为下一批导入素材。
const webFacts = [
  {
    date: "2025-09-16",
    text: "发行首支个人单曲《夢の道標（夢のみちしるべ）》，作词由本人担任，是个人歌手出道的首支原创曲。",
    source: "官方音源 / Bandori Wiki",
  },
  {
    date: "2025-02",
    text: "以长崎爽世身份出演 Sony 音乐节目 THE FIRST TAKE，演唱《春日影》与《潜在表明》。",
    source: "萌娘百科",
  },
  {
    date: "2024-12-22",
    text: "确诊甲型流感，因此缺席 MyGO!!!!! 7th LIVE。",
    source: "MyGO!!!!! 官方 X / Bandori Wiki",
  },
  {
    date: "2023-06-29",
    text: "动画《BanG Dream! It's MyGO!!!!!》首播，长崎爽世为其声优出道角色。",
    source: "百度百科",
  },
  {
    date: "",
    text: "小学时担任学生会长；中学二年级因 LoveLive! 立志成为声优；高中因 BanG Dream! 开始弹贝斯，第一首练的是《STAR BEAT!〜ホシノコドウ〜》。",
    source: "萌娘百科 / Bandori Wiki",
  },
  {
    date: "",
    text: "不喜欢的食物是胡萝卜；兴趣含跳舞，偏好 anisong 与偶像歌谣，喜欢的艺人有 saji、石原夏织、水濑伊织。",
    source: "Bandori Wiki",
  },
];

const conflicts = [
  {
    title: "血型记录不一致",
    detail:
      "知识库档案记为 O 型（依据 namu 称官网确认），Bandori Wiki 记 A 型，部分粉丝 wiki 也标 A。以官方资料为准，建议核实后统一。",
  },
];

/* ---------------------------------------------------------------- 加载 */

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const list = await api<{ items: Entry[] }>("/entries?category=streamer&limit=20");
    const target =
      list.items.find((item) => item.path === "streamer/小日向美香.md") ??
      list.items[0];
    if (!target) {
      error.value = "知识库里还没有主播档案词条。请先在“导入批次”导入 streamer/ 目录。";
      return;
    }
    const [detail, common, translation] = await Promise.all([
      api<Detail>(`/entries/${target.entry_id}`),
      api<{ items: Entry[] }>("/entries?category=common&limit=100"),
      api<{ items: Entry[] }>("/entries?category=translation&limit=100"),
    ]);
    profile.value = detail;
    entries.value = [
      ...common.items,
      ...translation.items.map((item) => ({ ...item, kind: "翻译纠错" })),
    ];
  } catch (e) {
    error.value = (e as Error).message;
    toast(error.value, true);
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div v-if="loading" class="loading-state">
    <span class="spinner"></span>正在读取主播档案
  </div>
  <div v-else-if="error" class="panel empty-state">
    <Icon name="users" :size="36" />
    <h2>暂时无法生成档案页</h2>
    <p>{{ error }}</p>
    <button class="button" @click="load">重试</button>
  </div>
  <template v-else-if="profile">
    <section class="profile-hero">
      <div class="profile-identity">
        <span class="profile-monogram">蜜</span>
        <div>
          <div class="eyebrow">主播档案</div>
          <h1>{{ profile.entry.title }}</h1>
          <p class="profile-romaji">{{ basicName.join(" / ") }}</p>
          <p v-if="nodeFormat" class="profile-role">{{ pick(registry, "人设") }}</p>
          <p v-else class="profile-role">
            声优 ·《小日向美香のひなたぼっこ。》主播 ·
            MyGO!!!!! 贝斯手（长崎爽世）
          </p>
        </div>
      </div>
      <div class="profile-hero-side">
        <div class="nickname-block">
          <span class="nickname-label">观众爱称</span>
          <div class="nickname-chips">
            <span v-for="name in names" :key="name" class="nickname-chip">{{
              name
            }}</span>
          </div>
        </div>
        <div class="profile-actions">
          <button class="button primary" @click="go('review', profileEntryId)">
            <Icon name="edit" :size="16" />审核 / 修订档案
          </button>
          <button class="button" @click="load">
            <Icon name="refresh" :size="16" />刷新
          </button>
        </div>
      </div>
    </section>

    <p v-if="intro" class="profile-intro">{{ intro }}</p>

    <section class="profile-facts" v-if="basics.length">
      <div v-for="item in basics" :key="item.key" class="fact">
        <span class="fact-label">{{ item.key }}</span>
        <span class="fact-value">{{ item.value }}</span>
      </div>
    </section>

    <section v-if="nodeFormat" class="panel profile-block">
      <div class="panel-heading"><h2>当前主播档案</h2></div>
      <div class="content-pad"><Markdown :text="visibleContent" /></div>
    </section>
    <section v-else class="panel profile-block">
      <div class="panel-heading">
        <div>
          <h2>节目「ひなたぼっこ。」</h2>
        </div>
        <Icon name="message" :size="19" />
      </div>
      <div class="content-pad">
        <div v-if="catchphrases.length" class="catchphrase-row">
          <span class="nickname-label">标志台词</span>
          <p v-for="line in catchphrases" :key="line" class="catchphrase">
            {{ line }}
          </p>
        </div>
        <div v-if="greetings.length" class="segment-grid">
          <article
            v-for="item in greetings"
            :key="item.name"
            class="segment-card quote"
          >
            <strong>{{ item.name }}</strong>
            <small>节目问候语</small>
          </article>
        </div>
        <template v-if="segments.length">
          <h3 class="profile-subheading">固定环节</h3>
          <div class="segment-grid">
            <article
              v-for="item in segments"
              :key="item.name"
              class="segment-card"
            >
              <strong>{{ item.name }}</strong>
              <small v-if="item.note">{{ item.note }}</small>
            </article>
          </div>
        </template>
        <div v-if="live.length" class="profile-notes">
          <p
            v-for="item in live.filter(
              (x) => x.key && x.key !== '固定环节',
            )"
            :key="item.key"
          >
            <strong>{{ item.key }}</strong>{{ item.value }}
          </p>
        </div>
      </div>
    </section>

    <div class="profile-columns">
      <div class="profile-main">
        <section v-if="!nodeFormat" class="panel profile-block">
          <div class="panel-heading">
            <div>
              <h2>年表 <span class="count-chip">{{ timeline.length }}</span></h2>
            </div>
            <Icon name="clock" :size="19" />
          </div>
          <ol class="timeline">
            <li v-for="item in timeline" :key="item.text" class="timeline-item">
              <span class="timeline-dot"></span>
              <div>
                <span v-if="item.date" class="timeline-date">{{
                  item.date
                }}</span>
                <p>{{ item.text }}</p>
              </div>
            </li>
          </ol>
        </section>

        <section class="panel profile-block">
          <div class="panel-heading">
            <div>
              <h2>知识库词条 <span class="count-chip">{{ entries.length }}</span></h2>
            </div>
            <Icon name="book" :size="19" />
          </div>
          <div class="content-pad">
            <div class="type-filter">
              <button
                class="filter-chip"
                :class="{ active: typeFilter === '' }"
                @click="typeFilter = ''"
              >
                全部 <span>{{ entries.length }}</span>
              </button>
              <button
                v-for="[kind, count] in kinds"
                :key="kind"
                class="filter-chip"
                :class="{ active: typeFilter === kind }"
                @click="typeFilter = kind"
              >
                {{ kind }} <span>{{ count }}</span>
              </button>
            </div>
            <p v-if="untyped.length" class="untyped-hint">
              <Icon name="shield" :size="15" />有
              {{ untyped.length }}
              条词条尚未标注类型。可以在导入时附上 common/index.md，保留已有分类。
            </p>
          </div>
          <div class="kb-grid">
            <button
              v-for="item in visibleEntries"
              :key="item.id"
              class="kb-card"
              @click="go('review', item.entry_id)"
            >
              <span class="kb-card-head">
                <strong>{{ item.title }}</strong>
                <span class="badge" :class="item.status">{{
                  labels[item.status]
                }}</span>
              </span>
              <small :class="{ missing: !item.kind }">{{ kindOf(item) }}</small>
              <p>{{ item.summary || "暂无摘要" }}</p>
              <span class="kb-card-foot">
                <span class="review-count"
                  ><Icon name="message" :size="14" />{{
                    item.review_count
                  }}</span
                >
                <span v-if="item.published" class="tag current">已发布</span>
                <span v-else class="tag">v{{ item.number }}</span>
              </span>
            </button>
          </div>
        </section>
      </div>

      <aside v-if="!nodeFormat" class="profile-aside">
        <section class="panel profile-block">
          <div class="panel-heading">
            <div><h2>说话风格</h2></div>
          </div>
          <div class="content-pad profile-notes">
            <p v-for="item in style" :key="item.key + item.value">
              <strong v-if="item.key">{{ item.key }}</strong>{{ item.value }}
            </p>
          </div>
        </section>

        <section class="panel profile-block">
          <div class="panel-heading">
            <div>
              <h2>人际关系</h2>
            </div>
          </div>
          <div class="content-pad relation-groups">
            <div
              v-for="group in relations"
              :key="group.title"
              class="relation-group"
            >
              <h3>{{ group.title }}</h3>
              <p v-if="group.note && !group.items.length" class="relation-note">
                {{ group.note }}
              </p>
              <ul v-if="group.items.length">
                <li v-for="item in group.items" :key="item.name">
                  <strong>{{ item.name }}</strong>
                  <span v-if="item.note">{{ item.note }}</span>
                </li>
              </ul>
            </div>
          </div>
        </section>

        <section class="panel profile-block web-panel">
          <div class="panel-heading">
            <div>
              <h2>联网核对补充</h2>
            </div>
          </div>
          <div class="content-pad">
            <article v-for="item in webFacts" :key="item.text" class="web-fact">
              <span v-if="item.date" class="timeline-date">{{ item.date }}</span>
              <p>{{ item.text }}</p>
              <small class="web-source">来源：{{ item.source }}</small>
            </article>
            <article v-for="item in conflicts" :key="item.title" class="web-fact conflict">
              <strong>{{ item.title }}</strong>
              <p>{{ item.detail }}</p>
            </article>
          </div>
        </section>

        <section class="panel profile-block">
          <div class="content-pad meta-block">
            <h3>档案元数据</h3>
            <dl>
              <dt>词条路径</dt>
              <dd>{{ profile.entry.path }}</dd>
              <dt>当前版本</dt>
              <dd>v{{ profile.entry.number }}</dd>
              <dt>更新时间</dt>
              <dd>{{ date(profile.entry.created_at) }}</dd>
              <dt>审核状态</dt>
              <dd>{{ labels[profile.entry.status] }}</dd>
              <dt>发布状态</dt>
              <dd>
                {{ profile.entry.published ? "已进入当前发布" : "尚未发布" }}
              </dd>
            </dl>
          </div>
        </section>
      </aside>
    </div>

    <details class="panel raw-panel">
      <summary>查看档案词条原文（Markdown）</summary>
      <Markdown :text="profile.entry.content" />
    </details>
  </template>
</template>
