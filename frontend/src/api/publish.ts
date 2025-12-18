import http from "./http";
import type {
  PublishAccount,
  PublishAccountCreate,
  PublishTask,
  PublishTaskCreateDraftRequest,
} from "@/types";

export const listPublishAccounts = () =>
  http.get<PublishAccount[]>("/publish/accounts").then((r) => r.data);

export const createPublishAccount = (payload: PublishAccountCreate) =>
  http.post<PublishAccount>("/publish/accounts", payload).then((r) => r.data);

export const createWechatDraft = (payload: PublishTaskCreateDraftRequest) =>
  http.post<PublishTask>("/publish/wechat/draft", payload).then((r) => r.data);

export const enqueueWechatDraft = (payload: PublishTaskCreateDraftRequest) =>
  http.post<PublishTask>("/publish/wechat/draft:enqueue", payload).then((r) => r.data);

export const getPublishTask = (taskId: number) =>
  http.get<PublishTask>(`/publish/tasks/${taskId}`).then((r) => r.data);

export const retryPublishTask = (taskId: number) =>
  http.post<PublishTask>(`/publish/tasks/${taskId}:retry`).then((r) => r.data);
