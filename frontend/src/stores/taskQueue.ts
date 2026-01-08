import { defineStore } from "pinia";
import { computed, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { quickGenerateFromEvent, quickGenerateFromTopic } from "@/api/dailyHotspots";

export type QueueTaskStatus = "queued" | "running" | "success" | "failed";
export type QueueTaskType = "topic" | "event";

export interface QueueTask {
  id: string;
  type: QueueTaskType;
  label: string;
  status: QueueTaskStatus;
  createdAt: number;
  topic?: string;
  eventId?: number;
  articleId?: number;
  errorMessage?: string;
}

const STORAGE_KEY = "auto_media.task_queue.v1";

const _newId = () => `${Date.now()}-${Math.random().toString(16).slice(2)}`;

const _safeParse = (raw: string | null) => {
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
};

export const useTaskQueueStore = defineStore("taskQueue", () => {
  const tasks = ref<QueueTask[]>([]);
  const queueRunning = ref(false);

  // 用于 Dashboard 热点卡片按钮的 loading 展示
  const runningEventId = ref<number | null>(null);

  const queuedCount = computed(() => tasks.value.filter((t) => t.status === "queued").length);

  const statusText = (s: QueueTaskStatus) => {
    if (s === "queued") return "排队中";
    if (s === "running") return "执行中";
    if (s === "success") return "已完成";
    return "失败";
  };

  const statusTagType = (s: QueueTaskStatus) => {
    if (s === "success") return "success";
    if (s === "failed") return "danger";
    if (s === "running") return "warning";
    return "info";
  };

  const persist = () => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(tasks.value));
    } catch {
      // 中文说明：本地存储失败时不影响主流程（可能是浏览器隐私模式/容量不足）
    }
  };

  const hydrate = () => {
    const parsed = _safeParse(localStorage.getItem(STORAGE_KEY));
    if (!Array.isArray(parsed)) return;

    const normalized: QueueTask[] = [];
    for (const x of parsed) {
      if (!x || typeof x !== "object") continue;
      if (typeof x.id !== "string" || typeof x.type !== "string" || typeof x.label !== "string") continue;
      if (typeof x.status !== "string" || typeof x.createdAt !== "number") continue;

      // 中文说明：页面刷新/重载后，原先 running 的任务无法恢复执行上下文，统一降级为 queued
      const status: QueueTaskStatus = x.status === "running" ? "queued" : x.status;

      normalized.push({
        id: x.id,
        type: x.type,
        label: x.label,
        status: status as QueueTaskStatus,
        createdAt: x.createdAt,
        topic: typeof x.topic === "string" ? x.topic : undefined,
        eventId: typeof x.eventId === "number" ? x.eventId : undefined,
        articleId: typeof x.articleId === "number" ? x.articleId : undefined,
        errorMessage: typeof x.errorMessage === "string" ? x.errorMessage : undefined,
      });
    }

    tasks.value = normalized;
  };

  const processQueue = async () => {
    if (queueRunning.value) return;
    queueRunning.value = true;
    try {
      // 中文说明：严格串行执行（FIFO），保证“排队”语义成立
      while (true) {
        const next = tasks.value.find((t) => t.status === "queued");
        if (!next) break;

        next.status = "running";
        next.errorMessage = undefined;
        next.articleId = undefined;

        if (next.type === "event" && typeof next.eventId === "number") {
          runningEventId.value = next.eventId;
        }

        try {
          if (next.type === "topic" && next.topic) {
            const article = await quickGenerateFromTopic(next.topic);
            next.articleId = article?.id;
          } else if (next.type === "event" && typeof next.eventId === "number") {
            const article = await quickGenerateFromEvent(next.eventId);
            next.articleId = article?.id;
          } else {
            throw new Error("任务参数缺失");
          }

          next.status = "success";
          ElMessage.success(`${next.label}：生成完成`);
        } catch (err: any) {
          next.status = "failed";
          next.errorMessage = err?.message || "生成失败";
          ElMessage.error(`${next.label}：${next.errorMessage}`);
        } finally {
          runningEventId.value = null;
          persist();
        }
      }
    } finally {
      queueRunning.value = false;
      runningEventId.value = null;
    }
  };

  const enqueueTopic = (topic: string) => {
    const t = (topic || "").trim();
    if (!t) return;

    tasks.value.push({
      id: _newId(),
      type: "topic",
      topic: t,
      label: `主题：${t}`,
      status: "queued",
      createdAt: Date.now(),
    });

    ElMessage.success("已加入队列");
    persist();
    void processQueue();
  };

  const enqueueEvent = (eventId: number, title: string) => {
    if (!eventId) return;

    tasks.value.push({
      id: _newId(),
      type: "event",
      eventId,
      label: `热点：${title}`,
      status: "queued",
      createdAt: Date.now(),
    });

    ElMessage.success("已加入队列");
    persist();
    void processQueue();
  };

  const retryTask = (taskId: string) => {
    const t = tasks.value.find((x) => x.id === taskId);
    if (!t) return;
    if (t.status === "running") return;

    t.status = "queued";
    t.errorMessage = undefined;
    t.articleId = undefined;

    persist();
    void processQueue();
  };

  const removeTask = (taskId: string) => {
    const idx = tasks.value.findIndex((x) => x.id === taskId);
    if (idx < 0) return;
    if (tasks.value[idx].status === "running") return;
    tasks.value.splice(idx, 1);
    persist();
  };

  // 初始化：从本地恢复队列
  hydrate();

  // 中文说明：只要队列里还有 queued 任务，就自动继续执行（支持页面刷新后恢复继续跑）
  if (tasks.value.some((t) => t.status === "queued")) {
    void processQueue();
  }

  // 兜底：外部直接修改 tasks 时也能落盘（避免漏 persist）
  watch(
    tasks,
    () => {
      persist();
    },
    { deep: true }
  );

  return {
    tasks,
    queuedCount,
    queueRunning,
    runningEventId,

    statusText,
    statusTagType,

    enqueueTopic,
    enqueueEvent,
    processQueue,
    retryTask,
    removeTask,
  };
});
