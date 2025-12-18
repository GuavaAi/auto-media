import http from "./http";
import type {
  Article,
  ArticleAiEditRequest,
  ArticleAiEditResponse,
  ArticleUpdate,
  DeleteResponse,
  GenerationRequest,
  PromptTemplateListResponse,
  PromptTemplate,
} from "@/types";

export const generateArticle = (payload: GenerationRequest) =>
  http.post<Article>("/generate/article", payload).then((r) => r.data);

export const listArticles = () =>
  http.get<Article[]>("/generate/articles").then((r) => r.data);

export const getArticle = (id: number) =>
  http.get<Article>(`/generate/articles/${id}`).then((r) => r.data);

export const updateArticle = (id: number, payload: ArticleUpdate) =>
  http.patch<Article>(`/generate/articles/${id}`, payload).then((r) => r.data);

export const deleteArticle = (id: number) =>
  http.delete<DeleteResponse>(`/generate/articles/${id}`).then((r) => r.data);

export const aiEditArticle = (id: number, payload: ArticleAiEditRequest) =>
  http.post<ArticleAiEditResponse>(`/generate/articles/${id}/ai-edit`, payload).then((r) => r.data);

export const listPromptTemplates = (key?: string) =>
  http
    .get<PromptTemplateListResponse>("/generate/prompt-templates", { params: { key } })
    .then((r) => r.data.items as PromptTemplate[]);

export const getPromptTemplate = (key: string, version?: number) =>
  http
    .get<{ item: PromptTemplate }>(`/generate/prompt-templates/${encodeURIComponent(key)}`, {
      params: { version },
    })
    .then((r) => r.data.item as PromptTemplate);

export const createPromptTemplate = (payload: { key: string; content: string }) =>
  http
    .post<{ item: PromptTemplate }>("/generate/prompt-templates", payload)
    .then((r) => r.data.item as PromptTemplate);

export const deletePromptTemplate = (key: string) =>
  http
    .delete<DeleteResponse>(`/generate/prompt-templates/${encodeURIComponent(key)}`)
    .then((r) => r.data);
