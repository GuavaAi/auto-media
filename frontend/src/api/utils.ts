import http from "./http";

/**
 * 获取页面预览 HTML（用于元素选择器）
 */
export const getPagePreviewHtml = (params: { url: string; use_playwright?: boolean }) =>
  http
    .get<string>("/utils/page-preview", {
      params,
      responseType: "text" as any,
      transformResponse: (r) => r,
    })
    .then((r) => r.data);

/**
 * 发现子页面链接
 */
export const discoverLinks = (params: {
  url: string;
  limit?: number;
  use_playwright?: boolean;
  css_selector?: string;
}) =>
  http
    .get<{ links: string[] }>("/utils/discover-links", {
      params,
    })
    .then((r) => r.data);
