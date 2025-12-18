/// <reference types="vite/client" />

declare module "prettier/standalone" {
  const prettier: any;
  export default prettier;
}

declare module "prettier/plugins/markdown" {
  const plugin: any;
  export default plugin;
}

interface Window {
  prettier?: any;
  prettierPlugins?: Record<string, any>;
}

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
