import http from "./http";

export interface UploadImageResponse {
  url: string;
  key?: string;
}

export const uploadImage = (file: File) => {
  const form = new FormData();
  form.append("file", file);
  return http
    .post<UploadImageResponse>("/utils/upload-image", form, {
      headers: { "Content-Type": "multipart/form-data" },
    })
    .then((r) => r.data);
};
