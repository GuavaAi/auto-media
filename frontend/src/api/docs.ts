import http from "./http";

export const getUserGuideMarkdown = () =>
  http
    .get<string>("/docs/user-guide", {
      responseType: "text" as any,
      transformResponse: (r) => r,
    })
    .then((r) => r.data);

export const getConfigGuideMarkdown = () =>
  http
    .get<string>("/docs/config-guide", {
      responseType: "text" as any,
      transformResponse: (r) => r,
    })
    .then((r) => r.data);
