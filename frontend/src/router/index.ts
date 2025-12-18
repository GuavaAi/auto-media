import { createRouter, createWebHistory, RouteRecordRaw } from "vue-router";

const routes: RouteRecordRaw[] = [
  {
    path: "/",
    redirect: "/dashboard",
  },
  {
    path: "/dashboard",
    name: "Dashboard",
    component: () => import("@/views/DashboardPage.vue"),
  },
  {
    path: "/quickstart",
    name: "QuickStart",
    component: () => import("@/views/QuickStartPage.vue"),
  },
  {
    path: "/config-guide",
    name: "ConfigGuide",
    component: () => import("@/views/QuickStartPage.vue"),
  },
  {
    path: "/generate",
    name: "Generate",
    component: () => import("@/views/GeneratePage.vue"),
  },
  {
    path: "/materials/packs",
    name: "MaterialPacks",
    component: () => import("@/views/MaterialPackPage.vue"),
  },
  {
    path: "/materials/packs/:id",
    name: "MaterialPackDetail",
    component: () => import("@/views/MaterialPackDetailPage.vue"),
    props: true,
  },
  {
    path: "/crawl-records",
    name: "CrawlRecords",
    component: () => import("@/views/CrawlRecordPage.vue"),
  },
  {
    path: "/crawl-records/:id",
    name: "CrawlRecordDetail",
    component: () => import("@/views/CrawlRecordDetail.vue"),
    props: true,
  },
  {
    path: "/daily-hotspots",
    name: "DailyHotspots",
    component: () => import("@/views/DailyHotspotPage.vue"),
  },
  {
    path: "/daily-hotspots/:id",
    name: "DailyHotspotDetail",
    component: () => import("@/views/DailyHotspotDetail.vue"),
    props: true,
  },
  {
    path: "/datasources",
    name: "DataSources",
    component: () => import("@/views/DataSourcePage.vue"),
  },
  {
    path: "/prompt-templates",
    name: "PromptTemplates",
    component: () => import("@/views/PromptTemplatePage.vue"),
  },
  {
    path: "/api-keys",
    name: "ApiKeys",
    component: () => import("@/views/ApiKeyPoolPage.vue"),
  },
  {
    path: "/publish",
    name: "Publish",
    component: () => import("@/views/PublishPage.vue"),
  },
  {
    path: "/articles",
    name: "Articles",
    component: () => import("@/views/ArticleManagePage.vue"),
  },
  {
    path: "/articles/:id",
    name: "ArticleDetail",
    component: () => import("@/views/ArticleDetail.vue"),
    props: true,
  },
  {
    path: "/articles/:id/edit",
    name: "ArticleEdit",
    component: () => import("@/views/ArticleEditPage.vue"),
    props: true,
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
