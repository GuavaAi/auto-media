import { createRouter, createWebHistory, RouteRecordRaw } from "vue-router";
import { ElMessage } from "element-plus";

import MainLayout from "@/layout/MainLayout.vue";
import { useAuthStore } from "@/stores/auth";
import { getToken } from "@/utils/token";

const mainChildren: RouteRecordRaw[] = [
  {
    path: "dashboard",
    name: "Dashboard",
    component: () => import("@/views/DashboardPage.vue"),
  },
  {
    path: "quickstart",
    name: "QuickStart",
    component: () => import("@/views/QuickStartPage.vue"),
  },
  {
    path: "config-guide",
    name: "ConfigGuide",
    component: () => import("@/views/QuickStartPage.vue"),
  },
  {
    path: "generate",
    name: "Generate",
    component: () => import("@/views/GeneratePage.vue"),
  },
  {
    path: "materials/packs",
    name: "MaterialPacks",
    component: () => import("@/views/MaterialPackPage.vue"),
  },
  {
    path: "materials/packs/:id",
    name: "MaterialPackDetail",
    component: () => import("@/views/MaterialPackDetailPage.vue"),
    props: true,
  },
  {
    path: "crawl-records",
    name: "CrawlRecords",
    component: () => import("@/views/CrawlRecordPage.vue"),
  },
  {
    path: "crawl-records/:id",
    name: "CrawlRecordDetail",
    component: () => import("@/views/CrawlRecordDetail.vue"),
    props: true,
  },
  {
    path: "daily-hotspots",
    name: "DailyHotspots",
    component: () => import("@/views/DailyHotspotPage.vue"),
  },
  {
    path: "daily-hotspots/:id",
    name: "DailyHotspotDetail",
    component: () => import("@/views/DailyHotspotDetail.vue"),
    props: true,
  },
  {
    path: "datasources",
    name: "DataSources",
    component: () => import("@/views/DataSourcePage.vue"),
  },
  {
    path: "prompt-templates",
    name: "PromptTemplates",
    component: () => import("@/views/PromptTemplatePage.vue"),
  },
  {
    path: "api-keys",
    name: "ApiKeys",
    component: () => import("@/views/ApiKeyPoolPage.vue"),
  },
  {
    path: "publish",
    name: "Publish",
    component: () => import("@/views/PublishPage.vue"),
  },
  {
    path: "articles",
    name: "Articles",
    component: () => import("@/views/ArticleManagePage.vue"),
  },
  {
    path: "articles/:id",
    name: "ArticleDetail",
    component: () => import("@/views/ArticleDetail.vue"),
    props: true,
  },
  {
    path: "articles/:id/edit",
    name: "ArticleEdit",
    component: () => import("@/views/ArticleEditPage.vue"),
    props: true,
  },
  {
    path: "users",
    name: "Users",
    component: () => import("@/views/UserManagePage.vue"),
    meta: { requiresAdmin: true },
  },
];

const routes: RouteRecordRaw[] = [
  {
    path: "/login",
    name: "Login",
    component: () => import("@/views/LoginPage.vue"),
    meta: { public: true },
  },
  {
    path: "/",
    component: MainLayout,
    redirect: "/dashboard",
    children: mainChildren,
  },
  {
    path: "/:pathMatch(.*)*",
    redirect: "/dashboard",
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore();
  const token = getToken();

  if (to.meta.public) {
    if (to.path === "/login" && token) {
      try {
        await authStore.loadProfile();
        return next((to.query.redirect as string) || "/dashboard");
      } catch {
        authStore.logout();
      }
    }
    return next();
  }

  try {
    await authStore.loadProfile();
  } catch {
    authStore.logout();
    return next({
      path: "/login",
      query: { redirect: to.fullPath },
    });
  }

  if (!authStore.user) {
    return next({
      path: "/login",
      query: { redirect: to.fullPath },
    });
  }

  if (to.meta.requiresAdmin && !authStore.isAdmin) {
    ElMessage.warning("仅管理员可访问");
    return next(from.path && from.path !== "/login" ? from.fullPath : "/dashboard");
  }

  return next();
});

export default router;
