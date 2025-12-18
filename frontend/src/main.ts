import { createApp } from "vue";
import ElementPlus from "element-plus";
import zhCn from "element-plus/es/locale/lang/zh-cn";
import "element-plus/dist/index.css";
import { createPinia } from "pinia";
import App from "./App.vue";
import router from "./router";
import "./styles/index.css";

import prettier from "prettier/standalone";
import prettierPluginMarkdown from "prettier/plugins/markdown";

// md-editor-v3 的“美化(Prettier)”功能依赖全局 prettier 对象
// 这里按官方推荐做法在入口处注入，避免在组件内重复配置
(window as any).prettier = prettier;
(window as any).prettierPlugins = { markdown: prettierPluginMarkdown };

const app = createApp(App);
app.use(ElementPlus, { locale: zhCn });
app.use(createPinia());
app.use(router);
app.mount("#app");
