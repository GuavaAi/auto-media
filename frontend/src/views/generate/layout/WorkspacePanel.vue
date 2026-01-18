<template>
  <div class="workspace-panel">
    <div class="workspace-top">
      <slot name="status" />
    </div>

    <div class="workspace-main">
      <slot name="main" />
    </div>
  </div>
</template>

<script setup lang="ts"></script>

<style scoped>
.workspace-panel {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: #fcfdfe;
}

.workspace-top {
  padding: 12px 24px;
  background: #fff;
  border-bottom: 1px solid #f1f5f9;
}

.workspace-main {
  padding: 20px 24px;
}
</style>
