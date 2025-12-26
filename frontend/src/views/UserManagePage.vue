<template>
  <div class="page">
    <div class="toolbar">
      <div class="left">
        <div class="title">用户管理</div>
        <div class="sub">仅管理员可访问：创建/编辑用户、重置密码、禁用账号</div>
      </div>
      <div class="right">
        <el-button type="primary" size="large" @click="openCreate">新增用户</el-button>
        <el-button size="large" :loading="loading" @click="load">刷新</el-button>
      </div>
    </div>

    <el-card shadow="never">
      <el-table :data="users" v-loading="loading" style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="username" label="用户名" min-width="160" />
        <el-table-column prop="full_name" label="姓名" min-width="160" />
        <el-table-column prop="email" label="邮箱" min-width="220" />
        <el-table-column label="角色" width="120">
          <template #default="scope">
            <el-tag :type="scope.row.role === 'admin' ? 'danger' : 'info'">
              {{ scope.row.role === "admin" ? "管理员" : "成员" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="scope">
            <el-tag :type="scope.row.is_active ? 'success' : 'warning'">
              {{ scope.row.is_active ? "启用" : "禁用" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" min-width="180" />
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="scope">
            <el-button size="small" @click="openEdit(scope.row)">编辑</el-button>
            <el-button
              size="small"
              type="warning"
              plain
              @click="openResetPassword(scope.row)"
            >
              重置密码
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="createDialogVisible" title="新增用户" width="520px">
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-position="top">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="createForm.username" placeholder="例如：editor" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="createForm.password" type="password" show-password placeholder="至少 6 位" />
        </el-form-item>
        <el-form-item label="姓名" prop="full_name">
          <el-input v-model="createForm.full_name" placeholder="可选" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="createForm.email" placeholder="可选" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="createForm.role" style="width: 100%">
            <el-option label="成员" value="editor" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态" prop="is_active">
          <el-switch v-model="createForm.is_active" active-text="启用" inactive-text="禁用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editDialogVisible" title="编辑用户" width="520px">
      <el-form ref="editFormRef" :model="editForm" :rules="editRules" label-position="top">
        <el-form-item label="用户名">
          <el-input v-model="editForm.username" disabled />
        </el-form-item>
        <el-form-item label="姓名" prop="full_name">
          <el-input v-model="editForm.full_name" placeholder="可选" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="editForm.email" placeholder="可选" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="editForm.role" style="width: 100%">
            <el-option label="成员" value="editor" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态" prop="is_active">
          <el-switch v-model="editForm.is_active" active-text="启用" inactive-text="禁用" />
        </el-form-item>
        <el-form-item label="重置密码（可选）" prop="password">
          <el-input v-model="editForm.password" type="password" show-password placeholder="留空则不修改" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="resetDialogVisible" title="重置密码" width="460px">
      <el-form ref="resetFormRef" :model="resetForm" :rules="resetRules" label-position="top">
        <el-form-item label="用户名">
          <el-input v-model="resetForm.username" disabled />
        </el-form-item>
        <el-form-item label="新密码" prop="password">
          <el-input v-model="resetForm.password" type="password" show-password placeholder="至少 6 位" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitReset">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";

import type { UserInfo } from "@/types";
import { createUser, listUsers, updateUser } from "@/api/users";

const loading = ref(false);
const saving = ref(false);
const users = ref<UserInfo[]>([]);

const load = async () => {
  if (loading.value) return;
  loading.value = true;
  try {
    const resp = await listUsers();
    users.value = resp.items || [];
  } catch (e: any) {
    ElMessage.error(e?.message || "加载失败");
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  load();
});

// -------------------- 新增用户 --------------------
const createDialogVisible = ref(false);
const createFormRef = ref();

const createForm = reactive({
  username: "",
  password: "",
  full_name: "",
  email: "",
  role: "editor",
  is_active: true,
});

const createRules = {
  username: [{ required: true, message: "请输入用户名", trigger: "blur" }],
  password: [{ required: true, message: "请输入密码", trigger: "blur" }],
  role: [{ required: true, message: "请选择角色", trigger: "change" }],
};

const openCreate = () => {
  createForm.username = "";
  createForm.password = "";
  createForm.full_name = "";
  createForm.email = "";
  createForm.role = "editor";
  createForm.is_active = true;
  createDialogVisible.value = true;
};

const submitCreate = async () => {
  try {
    await createFormRef.value?.validate?.();
  } catch {
    return;
  }

  saving.value = true;
  try {
    // 中文说明：后端要求 username/password 必填，其余字段可选
    await createUser({
      username: createForm.username,
      password: createForm.password,
      full_name: createForm.full_name || null,
      email: createForm.email || null,
      role: createForm.role,
      is_active: createForm.is_active,
    });
    ElMessage.success("创建成功");
    createDialogVisible.value = false;
    await load();
  } catch (e: any) {
    ElMessage.error(e?.message || "创建失败");
  } finally {
    saving.value = false;
  }
};

// -------------------- 编辑用户 --------------------
const editDialogVisible = ref(false);
const editFormRef = ref();
const editingId = ref<number | null>(null);

const editForm = reactive({
  username: "",
  full_name: "",
  email: "",
  role: "editor",
  is_active: true,
  password: "",
});

const editRules = {
  role: [{ required: true, message: "请选择角色", trigger: "change" }],
};

const openEdit = (row: UserInfo) => {
  editingId.value = row.id;
  editForm.username = row.username;
  editForm.full_name = row.full_name || "";
  editForm.email = row.email || "";
  editForm.role = row.role;
  editForm.is_active = row.is_active;
  editForm.password = "";
  editDialogVisible.value = true;
};

const submitEdit = async () => {
  if (!editingId.value) return;

  try {
    await editFormRef.value?.validate?.();
  } catch {
    return;
  }

  saving.value = true;
  try {
    await updateUser(editingId.value, {
      full_name: editForm.full_name || null,
      email: editForm.email || null,
      role: editForm.role,
      is_active: editForm.is_active,
      password: editForm.password ? editForm.password : null,
    });
    ElMessage.success("保存成功");
    editDialogVisible.value = false;
    await load();
  } catch (e: any) {
    ElMessage.error(e?.message || "保存失败");
  } finally {
    saving.value = false;
  }
};

// -------------------- 重置密码 --------------------
const resetDialogVisible = ref(false);
const resetFormRef = ref();
const resetUserId = ref<number | null>(null);

const resetForm = reactive({
  username: "",
  password: "",
});

const resetRules = {
  password: [{ required: true, message: "请输入新密码", trigger: "blur" }],
};

const openResetPassword = (row: UserInfo) => {
  resetUserId.value = row.id;
  resetForm.username = row.username;
  resetForm.password = "";
  resetDialogVisible.value = true;
};

const submitReset = async () => {
  if (!resetUserId.value) return;

  try {
    await resetFormRef.value?.validate?.();
  } catch {
    return;
  }

  saving.value = true;
  try {
    await updateUser(resetUserId.value, { password: resetForm.password });
    ElMessage.success("密码已重置");
    resetDialogVisible.value = false;
  } catch (e: any) {
    ElMessage.error(e?.message || "重置失败");
  } finally {
    saving.value = false;
  }
};
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.title {
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
}

.sub {
  margin-top: 4px;
  font-size: 12px;
  color: rgba(15, 23, 42, 0.55);
}

.right {
  display: flex;
  align-items: center;
  gap: 10px;
}
</style>
