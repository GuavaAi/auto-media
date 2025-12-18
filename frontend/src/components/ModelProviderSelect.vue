<template>
  <el-select
    :model-value="modelValue"
    :placeholder="placeholder"
    :clearable="clearable"
    :disabled="disabled"
    @update:model-value="onUpdate"
  >
    <el-option
      v-if="includeEmptyOption"
      :label="emptyLabel"
      :value="emptyValue"
    />

    <el-option v-for="p in normalizedOptions" :key="p" :label="providerLabel(p)" :value="p">
      <span style="float: left">{{ p }}</span>
      <span style="float: right; color: #8492a6; font-size: 13px">{{ providerCn(p) }}</span>
    </el-option>
  </el-select>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { getProviderCn, MODEL_PROVIDER_OPTIONS } from "@/utils/providerNames";

type ModelValue = string | undefined | null;

const props = withDefaults(
  defineProps<{
    modelValue?: ModelValue;
    options?: string[];
    placeholder?: string;
    clearable?: boolean;
    disabled?: boolean;
    includeEmptyOption?: boolean;
    emptyLabel?: string;
    emptyValue?: string;
  }>(),
  {
    placeholder: "默认后端配置",
    clearable: false,
    disabled: false,
    includeEmptyOption: false,
    emptyLabel: "跟随默认",
    emptyValue: "",
  }
);

const emit = defineEmits<{
  (e: "update:modelValue", v: string | undefined): void;
}>();

const normalizedOptions = computed(() => {
  const opts = props.options && props.options.length ? props.options : Array.from(MODEL_PROVIDER_OPTIONS);
  return opts.map((x) => String(x));
});

const providerCn = (p: string) => getProviderCn(p);

const providerLabel = (p: string) => {
  const cn = providerCn(p);
  return cn || p;
};

const onUpdate = (v: any) => {
  if (v === null || v === undefined) {
    emit("update:modelValue", undefined);
    return;
  }

  const raw = String(v);
  if (props.includeEmptyOption && raw === props.emptyValue) {
    emit("update:modelValue", raw);
    return;
  }

  emit("update:modelValue", raw ? raw : undefined);
};
</script>
