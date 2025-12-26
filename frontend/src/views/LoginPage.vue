<template>
  <div class="login-page">
    <div class="login-bg" />
    <div class="login-card">
      <div class="brand">
        <div class="logo">AM</div>
        <div class="brand-text">
          <div class="title">自媒体自动化系统</div>
          <div class="desc">登录后进入内容生产工作台</div>
        </div>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        class="login-form"
        @submit.prevent
      >
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="form.username"
            placeholder="请输入用户名"
            size="large"
            autocomplete="username"
          />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            placeholder="请输入密码"
            size="large"
            type="password"
            show-password
            autocomplete="current-password"
            @keyup.enter="onSubmit"
          />
        </el-form-item>

        <el-button
          type="primary"
          size="large"
          class="submit"
          :loading="submitting"
          @click="onSubmit"
        >
          登录
        </el-button>

        <div class="tips">
          <div class="tip">默认管理员：admin / admin123</div>
        </div>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";

import { useAuthStore } from "@/stores/auth";

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();

const formRef = ref();
const submitting = ref(false);

const form = reactive({
  username: "",
  password: "",
});

const rules = {
  username: [{ required: true, message: "请输入用户名", trigger: "blur" }],
  password: [{ required: true, message: "请输入密码", trigger: "blur" }],
};

const onSubmit = async () => {
  if (submitting.value) return;

  try {
    await formRef.value?.validate?.();
  } catch {
    return;
  }

  submitting.value = true;
  try {
    // 中文说明：登录成功后后端返回 token + user，这里存 token 并写入 store
    await authStore.login({ username: form.username, password: form.password });

    const redirect = (route.query.redirect as string) || "/dashboard";
    await router.replace(redirect);

    ElMessage.success("登录成功");
  } catch (e: any) {
    ElMessage.error(e?.message || "登录失败");
  } finally {
    submitting.value = false;
  }
};
</script>

<style scoped>
.login-page {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.login-bg {
  position: absolute;
  inset: 0;
  background: radial-gradient(
      1200px 600px at 20% 10%,
      rgba(64, 158, 255, 0.35),
      transparent 60%
    ),
    radial-gradient(
      900px 500px at 90% 40%,
      rgba(54, 209, 220, 0.28),
      transparent 55%
    ),
    linear-gradient(135deg, #0f172a, #1e293b);
}

.login-card {
  position: relative;
  width: 420px;
  max-width: 100%;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-radius: 16px;
  padding: 28px;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.25);
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.logo {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 900;
  color: #fff;
  background: linear-gradient(135deg, #409eff, #36d1dc);
}

.brand-text .title {
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
}

.brand-text .desc {
  margin-top: 2px;
  font-size: 12px;
  color: rgba(15, 23, 42, 0.55);
}

.submit {
  width: 100%;
  margin-top: 8px;
}

.tips {
  margin-top: 14px;
  font-size: 12px;
  color: rgba(15, 23, 42, 0.6);
}

.tip {
  line-height: 1.6;
}
</style>
