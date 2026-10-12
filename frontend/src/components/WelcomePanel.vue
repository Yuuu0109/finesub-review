<script setup lang="ts">
import Brand from "./Brand.vue";
import Icon from "./Icon.vue";
</script>

<template>
  <aside class="welcome-panel">
    <Brand />
    <div class="welcome-copy">
      <span class="welcome-kicker">让好翻译，有迹可循</span>
      <h1>一起，把每个词<br />校对得更好<span>。</span></h1>
      <div class="proof-sheet" aria-hidden="true">
        <div class="proof-sheet-top">
          <span>校对札记</span><Icon name="book" :size="18" />
        </div>
        <div class="proof-word">
          <span lang="ja">こもれび</span><strong lang="ja">木漏れ日</strong>
        </div>
        <p>穿过枝叶的<span class="proof-highlight">阳光</span>。</p>
        <div class="proof-sheet-bottom">
          <span class="proof-rule"></span><Icon name="check" :size="16" /><span
            >让语意，恰如其分</span
          >
        </div>
      </div>
    </div>
    <div class="welcome-footer">
      <span>FineSub Review</span><span>共建 · 校对 · 定稿</span>
    </div>
  </aside>
</template>
