<template>
  <div class="cron-row">
    <el-input
      v-model="inputValue"
      placeholder="例如：0 */2 * * *"
      @input="onInputChange"
    />
    <el-popover v-model:visible="popoverVisible" placement="right-start" width="520" trigger="click">
      <template #reference>
        <el-button class="cron-btn" type="primary" text>选择 / 生成</el-button>
      </template>
      <div class="cron-popover">
        <div class="cron-section">
          <p class="title">快速选择</p>
          <el-button
            v-for="item in presets"
            :key="item.value"
            size="small"
            :type="item.value === inputValue ? 'primary' : 'default'"
            @click="applyPreset(item.value)"
          >
            {{ item.label }}
          </el-button>
        </div>
        <div class="cron-section">
          <p class="title">可视化构建</p>
          <div class="cron-grid">
            <label>分钟</label>
            <el-select v-model="builder.minute" filterable>
              <el-option label="*" value="*" />
              <el-option v-for="m in minuteOptions" :key="m" :label="m" :value="m" />
            </el-select>
            <label>小时</label>
            <el-select v-model="builder.hour" filterable>
              <el-option label="*" value="*" />
              <el-option v-for="h in hourOptions" :key="h" :label="h" :value="h" />
            </el-select>
            <label>日期(天)</label>
            <el-select v-model="builder.dom" filterable>
              <el-option label="*" value="*" />
              <el-option v-for="d in domOptions" :key="d" :label="d" :value="d" />
            </el-select>
            <label>月份</label>
            <el-select v-model="builder.month" filterable>
              <el-option label="*" value="*" />
              <el-option v-for="m in monthOptions" :key="m" :label="m" :value="m" />
            </el-select>
            <label>星期</label>
            <el-select v-model="builder.dow" filterable>
              <el-option label="*" value="*" />
              <el-option v-for="w in dowOptions" :key="w.value" :label="w.label" :value="w.value" />
            </el-select>
          </div>
          <div class="cron-actions">
            <span class="cron-preview">结果：{{ previewCron }}</span>
            <el-button size="small" type="primary" @click="confirmCron">确认</el-button>
          </div>
        </div>
      </div>
    </el-popover>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";

const props = defineProps<{ modelValue?: string }>();
const emit = defineEmits<{
  (e: "update:modelValue", value: string): void;
}>();

const inputValue = ref(props.modelValue || "");
const popoverVisible = ref(false);

const presets = [
  { label: "每 5 分钟", value: "*/5 * * * *" },
  { label: "每小时", value: "0 * * * *" },
  { label: "每天 8 点", value: "0 8 * * *" },
  { label: "每周一 9 点", value: "0 9 * * 1" },
  { label: "每月 1 号 10 点", value: "0 10 1 * *" },
];

const minuteOptions = Array.from({ length: 60 }, (_, i) => String(i));
const hourOptions = Array.from({ length: 24 }, (_, i) => String(i));
const domOptions = Array.from({ length: 31 }, (_, i) => String(i + 1));
const monthOptions = Array.from({ length: 12 }, (_, i) => String(i + 1));
const dowOptions = [
  { label: "周日", value: "0" },
  { label: "周一", value: "1" },
  { label: "周二", value: "2" },
  { label: "周三", value: "3" },
  { label: "周四", value: "4" },
  { label: "周五", value: "5" },
  { label: "周六", value: "6" },
];

const builder = reactive({
  minute: "*",
  hour: "*",
  dom: "*",
  month: "*",
  dow: "*",
});

const previewCron = computed(
  () => `${builder.minute} ${builder.hour} ${builder.dom} ${builder.month} ${builder.dow}`
);

const syncBuilderFromCron = (cron?: string) => {
  if (!cron) return;
  const parts = cron.trim().split(/\s+/);
  if (parts.length < 5) return;
  [builder.minute, builder.hour, builder.dom, builder.month, builder.dow] = parts.slice(0, 5) as string[];
};

const onInputChange = (val: string) => {
  inputValue.value = val;
  syncBuilderFromCron(val);
  emit("update:modelValue", val);
};

const applyPreset = (val: string) => {
  inputValue.value = val;
  syncBuilderFromCron(val);
  emit("update:modelValue", val);
};

const confirmCron = () => {
  inputValue.value = previewCron.value;
  emit("update:modelValue", previewCron.value);
  popoverVisible.value = false;
};

watch(
  () => props.modelValue,
  (val) => {
    inputValue.value = val || "";
    syncBuilderFromCron(val || "");
  }
);

onMounted(() => {
  syncBuilderFromCron(inputValue.value);
});
</script>

<style scoped>
.cron-row {
  display: flex;
  gap: 8px;
  align-items: center;
}
.cron-popover {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.cron-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.cron-grid {
  display: grid;
  grid-template-columns: 80px 1fr;
  gap: 6px 12px;
  align-items: center;
}
.cron-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.cron-preview {
  font-size: 13px;
  color: #374151;
}
</style>
