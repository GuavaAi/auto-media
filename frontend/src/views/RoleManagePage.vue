<template>
  <div class="page">
    <div class="toolbar">
      <div class="left">
        <div class="title">角色管理</div>
        <div class="sub">配置每个角色可访问的菜单（用于侧边栏展示与路由拦截）</div>
      </div>
      <div class="right">
        <el-button type="primary" size="large" @click="openCreate">新增角色</el-button>
        <el-button size="large" :loading="loading" @click="load">刷新</el-button>
      </div>
    </div>

    <el-card shadow="never">
      <el-table :data="roles" v-loading="loading" style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="key" label="角色Key" min-width="140" />
        <el-table-column prop="name" label="角色名称" min-width="180" />
        <el-table-column label="菜单权限" min-width="360">
          <template #default="scope">
            <el-tag v-for="m in (scope.row.menus || [])" :key="m" class="tag">{{ menuLabelMap[m] || m }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="scope">
            <el-button size="small" @click="openEdit(scope.row)">编辑</el-button>
            <el-button
              size="small"
              type="danger"
              plain
              :disabled="isBuiltinRole(scope.row)"
              @click="handleDelete(scope.row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="720px">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="角色Key" prop="key">
              <el-input v-model="form.key" :disabled="editing" placeholder="例如：ops / auditor" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="角色名称" prop="name">
              <el-input v-model="form.name" placeholder="例如：运营" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="可访问菜单" prop="menus">
          <el-checkbox-group v-model="form.menus" class="menu-group">
            <div v-for="group in menuGroups" :key="group.key" class="menu-section">
              <div class="menu-section-title">{{ group.label }}</div>
              <div class="menu-section-items">
                <el-checkbox v-for="item in group.items" :key="item.key" :label="item.key">
                  {{ item.label }}
                </el-checkbox>
              </div>
            </div>
          </el-checkbox-group>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox, FormInstance, FormRules } from "element-plus";
import type { RoleOut } from "@/types";
import { createRole, deleteRole, fetchRoles, updateRole } from "@/api/roles";

type MenuItem = { key: string; label: string };

type MenuGroup = {
  key: string;
  label: string;
  items: MenuItem[];
};

const menuGroups: MenuGroup[] = [
  {
    key: "content",
    label: "内容生产",
    items: [
      { key: "generate", label: "生成软文" },
      { key: "articles", label: "软文管理" },
      { key: "materials", label: "素材包" },
      { key: "publish", label: "发布" },
    ],
  },
  {
    key: "data",
    label: "数据采集",
    items: [
      { key: "daily-hotspots", label: "热点榜单" },
      { key: "crawl-records", label: "抓取记录" },
      { key: "datasources", label: "数据源管理" },
    ],
  },
  {
    key: "system",
    label: "系统配置",
    items: [
      { key: "prompt-templates", label: "模板管理" },
      { key: "api-keys", label: "API Key 池" },
      { key: "users", label: "用户管理" },
      { key: "roles", label: "角色管理" },
    ],
  },
];

const menuLabelMap = computed(() => {
  const map: Record<string, string> = {
    dashboard: "工作台",
    quickstart: "新手教程",
    "config-guide": "配置教程",
  };
  for (const g of menuGroups) {
    for (const item of g.items) {
      map[item.key] = item.label;
    }
  }
  return map;
});

const loading = ref(false);
const saving = ref(false);
const roles = ref<RoleOut[]>([]);

const dialogVisible = ref(false);
const editing = ref(false);
const editingId = ref<number | null>(null);

const formRef = ref<FormInstance>();
const form = reactive<{ key: string; name: string; menus: string[] }>({
  key: "",
  name: "",
  menus: [],
});

const rules: FormRules = {
  key: [{ required: true, message: "请输入角色Key", trigger: "blur" }],
  name: [{ required: true, message: "请输入角色名称", trigger: "blur" }],
};

const dialogTitle = computed(() => (editing.value ? "编辑角色" : "新增角色"));

function isBuiltinRole(role: RoleOut) {
  return ["admin", "editor"].includes((role.key || "").toLowerCase());
}

async function load() {
  loading.value = true;
  try {
    const resp = await fetchRoles();
    roles.value = resp.items || [];
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  editing.value = false;
  editingId.value = null;
  form.key = "";
  form.name = "";
  form.menus = [];
  dialogVisible.value = true;
}

function openEdit(row: RoleOut) {
  editing.value = true;
  editingId.value = row.id;
  form.key = row.key;
  form.name = row.name;
  form.menus = Array.isArray(row.menus) ? [...row.menus] : [];
  dialogVisible.value = true;
}

async function handleSave() {
  await formRef.value?.validate();

  saving.value = true;
  try {
    if (!editing.value) {
      await createRole({ key: form.key, name: form.name, menus: form.menus });
      ElMessage.success("创建成功");
    } else if (editingId.value != null) {
      await updateRole(editingId.value, { name: form.name, menus: form.menus });
      ElMessage.success("保存成功");
    }

    dialogVisible.value = false;
    await load();
  } finally {
    saving.value = false;
  }
}

async function handleDelete(row: RoleOut) {
  await ElMessageBox.confirm(`确认删除角色「${row.name}」吗？`, "提示", {
    type: "warning",
    confirmButtonText: "删除",
    cancelButtonText: "取消",
  });

  await deleteRole(row.id);
  ElMessage.success("删除成功");
  await load();
}

onMounted(load);
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.toolbar {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
}

.title {
  font-size: 18px;
  font-weight: 600;
}

.sub {
  margin-top: 6px;
  color: #909399;
  font-size: 13px;
}

.tag {
  margin-right: 8px;
  margin-bottom: 8px;
}

.menu-group {
  width: 100%;
}

.menu-section {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
}

.menu-section-title {
  font-weight: 600;
  margin-bottom: 10px;
}

.menu-section-items {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 16px;
}
</style>
