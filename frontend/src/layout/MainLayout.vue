<template>
  <el-container class="layout-container">
    <el-aside width="240px" class="aside">
      <div class="brand">
        <div class="logo-icon">AM</div>
        <div class="brand-text">
          <div class="app-name">Auto Media</div>
          <div class="app-desc">自动化内容矩阵</div>
        </div>
      </div>
      
      <el-menu
        :default-active="activeMenu"
        :default-openeds="openedMenus"
        class="aside-menu"
        background-color="transparent"
        text-color="rgba(255, 255, 255, 0.7)"
        active-text-color="#fff"
        :router="true"
      >
        <el-menu-item index="/dashboard">
          <el-icon><Odometer /></el-icon>
          <span>工作台</span>
        </el-menu-item>

        <el-sub-menu index="group-content">
          <template #title>
            <el-icon><EditPen /></el-icon>
            <span>内容生产</span>
          </template>
          <el-menu-item index="/generate">
            <el-icon><EditPen /></el-icon>
            <span>生成软文</span>
          </el-menu-item>
          <el-menu-item index="/articles">
            <el-icon><Document /></el-icon>
            <span>软文管理</span>
          </el-menu-item>
          <el-menu-item index="/materials/packs">
            <el-icon><FolderOpened /></el-icon>
            <span>素材包</span>
          </el-menu-item>
          <el-menu-item index="/publish">
            <el-icon><Promotion /></el-icon>
            <span>发布</span>
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="group-data">
          <template #title>
            <el-icon><DataLine /></el-icon>
            <span>数据采集</span>
          </template>
          <el-menu-item index="/daily-hotspots">
            <el-icon><DataLine /></el-icon>
            <span>热点榜单</span>
          </el-menu-item>
          <el-menu-item index="/crawl-records">
            <el-icon><DocumentCopy /></el-icon>
            <span>抓取记录</span>
          </el-menu-item>
          <el-menu-item index="/datasources" v-if="can('datasources')">
            <el-icon><Connection /></el-icon>
            <span>数据源管理</span>
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="group-system" v-if="showSystemGroup">
          <template #title>
            <el-icon><Collection /></el-icon>
            <span>系统配置</span>
          </template>
          <el-menu-item index="/prompt-templates" v-if="can('prompt-templates')">
            <el-icon><Collection /></el-icon>
            <span>模板管理</span>
          </el-menu-item>
          <el-menu-item index="/api-keys" v-if="can('api-keys')">
            <el-icon><Key /></el-icon>
            <span>API Key 池</span>
          </el-menu-item>
          <el-menu-item index="/users" v-if="can('users')">
            <el-icon><User /></el-icon>
            <span>用户管理</span>
          </el-menu-item>
          <el-menu-item index="/roles" v-if="can('roles')">
            <el-icon><User /></el-icon>
            <span>角色管理</span>
          </el-menu-item>
        </el-sub-menu>
      </el-menu>
    </el-aside>

    <el-container class="main-container">
      <el-header class="header">
        <div class="header-left">
          <div class="page-title">{{ currentPageTitle }}</div>
        </div>
        <div class="header-right">
          <el-button type="warning" size="large" @click="goConfigGuide">配置教程</el-button>
          <el-button type="primary" plain @click="goQuickStart">新手教程</el-button>
          <el-divider direction="vertical" />
          <el-dropdown>
            <span class="user-entry">
              <el-icon><UserFilled /></el-icon>
              <span class="user-name">{{ displayName }}</span>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item>{{ currentUser?.role === "admin" ? "管理员" : "成员" }}</el-dropdown-item>
                <el-dropdown-item divided @click="goUsers" v-if="can('users')">用户管理</el-dropdown-item>
                <el-dropdown-item divided @click="goRoles" v-if="can('roles')">角色管理</el-dropdown-item>
                <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main-content">
        <div class="content-wrapper">
          <router-view v-slot="{ Component }">
            <transition name="fade" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </div>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessageBox } from "element-plus";
import {
  EditPen,
  DataLine,
  Document,
  DocumentCopy,
  Connection,
  Collection,
  Key,
  Odometer,
  FolderOpened,
  Promotion,
  UserFilled,
  User
} from "@element-plus/icons-vue";

import { useAuthStore } from "@/stores/auth";

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();

const goQuickStart = () => {
  router.push("/quickstart");
};

const goConfigGuide = () => {
  router.push("/config-guide");
};

const goUsers = () => {
  router.push("/users");
};

const goRoles = () => {
  router.push("/roles");
};

const handleLogout = () => {
  ElMessageBox.confirm("确定要退出登录吗？", "提示", {
    type: "warning",
    confirmButtonText: "退出",
    cancelButtonText: "取消",
  })
    .then(() => {
      authStore.logout();
      router.push("/login");
    })
    .catch(() => undefined);
};

const activeMenu = computed(() => {
  if (route.path.startsWith("/dashboard")) return "/dashboard";
  if (route.path.startsWith("/quickstart")) return "/dashboard";
  if (route.path.startsWith("/config-guide")) return "/dashboard";
  if (route.path.startsWith("/articles")) return "/articles";
  if (route.path.startsWith("/materials")) return "/materials/packs";
  if (route.path.startsWith("/publish")) return "/publish";
  if (route.path.startsWith("/datasources")) return "/datasources";
  if (route.path.startsWith("/crawl-records")) return "/crawl-records";
  if (route.path.startsWith("/daily-hotspots")) return "/daily-hotspots";
  if (route.path.startsWith("/prompt-templates")) return "/prompt-templates";
  if (route.path.startsWith("/api-keys")) return "/api-keys";
  if (route.path.startsWith("/users")) return "/users";
  if (route.path.startsWith("/roles")) return "/roles";
  return "/generate";
});

const openedMenus = computed(() => {
  if (
    route.path.startsWith("/generate") ||
    route.path.startsWith("/articles") ||
    route.path.startsWith("/materials") ||
    route.path.startsWith("/publish")
  ) {
    return ["group-content"];
  }
  if (
    route.path.startsWith("/daily-hotspots") ||
    route.path.startsWith("/crawl-records") ||
    route.path.startsWith("/datasources")
  ) {
    return ["group-data"];
  }
  if (
    route.path.startsWith("/prompt-templates") ||
    route.path.startsWith("/api-keys") ||
    route.path.startsWith("/users") ||
    route.path.startsWith("/roles")
  ) {
    return ["group-system"];
  }
  return [];
});

const currentPageTitle = computed(() => {
  const map: Record<string, string> = {
    "/dashboard": "工作台",
    "/quickstart": "运营手册",
    "/config-guide": "配置教程",
    "/generate": "生成软文",
    "/articles": "软文管理",
    "/materials": "素材包",
    "/publish": "发布",
    "/daily-hotspots": "全网热点",
    "/crawl-records": "抓取记录",
    "/datasources": "数据源配置",
    "/prompt-templates": "Prompt 模板",
    "/api-keys": "API Key 池",
    "/users": "用户管理",
    "/roles": "角色管理",
  };
  // 简单匹配前缀
  for (const key in map) {
    if (route.path.startsWith(key)) return map[key];
  }
  return "工作台";
});

const currentUser = computed(() => authStore.user);
const displayName = computed(() => authStore.displayName);

const can = (menuKey: string) => authStore.isAdmin || authStore.hasMenu(menuKey);

const showSystemGroup = computed(() =>
  can("prompt-templates") || can("api-keys") || can("users") || can("roles")
);
</script>

<style scoped>
.layout-container {
  height: 100vh;
  background-color: #f6f8fa;
}

.aside {
  background: #1e293b;
  color: #fff;
  display: flex;
  flex-direction: column;
  transition: width 0.3s;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.05);
  z-index: 10;
}

.brand {
  height: 64px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.logo-icon {
  width: 32px;
  height: 32px;
  background: linear-gradient(135deg, #409eff, #36d1dc);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  font-size: 14px;
  color: #fff;
  margin-right: 12px;
}

.brand-text {
  display: flex;
  flex-direction: column;
}

.app-name {
  font-size: 16px;
  font-weight: 600;
  color: #fff;
  line-height: 1.2;
}

.app-desc {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.5);
}

.aside-menu {
  border-right: none;
  margin-top: 16px;
}

.aside-menu :deep(.el-menu-item) {
  height: 50px;
  line-height: 50px;
  margin: 4px 12px;
  border-radius: 8px;
}

.aside-menu :deep(.el-sub-menu__title) {
  height: 50px;
  line-height: 50px;
  margin: 4px 12px;
  border-radius: 8px;
}

.aside-menu :deep(.el-menu-item:hover) {
  background-color: rgba(255, 255, 255, 0.08);
}

.aside-menu :deep(.el-sub-menu__title:hover) {
  background-color: rgba(255, 255, 255, 0.08);
}

.aside-menu :deep(.el-menu-item.is-active) {
  background: linear-gradient(90deg, #409eff, #3a8ee6);
  color: #fff;
  font-weight: 500;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.3);
}

.main-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

.header {
  height: 64px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
  z-index: 5;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-entry {
  display: flex;
  align-items: center;
  cursor: pointer;
  padding: 6px 12px;
  border-radius: 6px;
  transition: background-color 0.2s;
  color: #606266;
}

.user-entry:hover {
  background-color: #f3f4f6;
  color: #303133;
}

.user-name {
  margin-left: 8px;
  font-size: 14px;
  font-weight: 500;
}

.main-content {
  padding: 24px;
  position: relative;
  overflow-y: auto;
  overscroll-behavior-y: contain;
  background: #f8fafc;
}

.content-wrapper {
  max-width: 1400px;
  margin: 0 auto;
  min-height: 100%;
}

/* 过渡动画 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
