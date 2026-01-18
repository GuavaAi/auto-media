import { defineStore } from "pinia";
import { computed, ref } from "vue";
import type { MaterialItemCreate } from "@/types";

export interface MaterialBasketItem extends MaterialItemCreate {
  // 用于前端列表渲染的临时 id
  _key: string;
  // 中文说明：NotebookLM 风格侧边栏需要支持勾选哪些素材参与生成。
  selected?: boolean;
}

const _norm = (s: string) => (s || "").trim().replace(/\s+/g, " ");

export const useMaterialBasketStore = defineStore("materialBasket", () => {
  // 素材篮：用于把多个事件/来源的条目临时收集起来，再一次性入库到素材包
  const items = ref<MaterialBasketItem[]>([]);

  const count = computed(() => items.value.length);

  const selectedCount = computed(() => items.value.filter((x) => !!x.selected).length);
  const selectedItems = computed(() => items.value.filter((x) => !!x.selected));

  const _makeKey = (it: MaterialItemCreate) => {
    const t = _norm(it.item_type || "").toLowerCase();
    const text = _norm(it.text || "");
    return `${t}|${text}`;
  };

  const addMany = (newItems: MaterialItemCreate[]) => {
    // 本地轻量去重：按 item_type + 规范化 text 去重
    const existed = new Set(items.value.map((x) => _makeKey(x)));

    for (const it of newItems || []) {
      const key = _makeKey(it);
      if (!key || key.endsWith("|")) continue;
      if (existed.has(key)) continue;
      existed.add(key);
      items.value.push({
        ...it,
        _key: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
        selected: true,
      });
    }
  };

  const setSelectedByKey = (key: string, selected: boolean) => {
    const it = items.value.find((x) => x._key === key);
    if (!it) return;
    it.selected = !!selected;
  };

  const toggleSelectedByKey = (key: string) => {
    const it = items.value.find((x) => x._key === key);
    if (!it) return;
    it.selected = !it.selected;
  };

  const selectAll = () => {
    for (const it of items.value) it.selected = true;
  };

  const clearSelection = () => {
    for (const it of items.value) it.selected = false;
  };

  const updateTextByKey = (key: string, text: string) => {
    const it = items.value.find((x) => x._key === key);
    if (!it) return;
    it.text = String(text || "");
  };

  const removeByKey = (key: string) => {
    items.value = items.value.filter((x) => x._key !== key);
  };

  const clear = () => {
    items.value = [];
  };

  return {
    items,
    count,
    selectedCount,
    selectedItems,
    addMany,
    setSelectedByKey,
    toggleSelectedByKey,
    selectAll,
    clearSelection,
    updateTextByKey,
    removeByKey,
    clear,
  };
});
