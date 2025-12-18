<template>
  <div class="ai-thinking">
    <div class="ai-thinking-orb">
      <div class="orb-inner"></div>
    </div>
    <div class="ai-thinking-steps">
      <transition name="fade" mode="out-in">
        <span :key="currentStep" class="step-text">{{ steps[currentStep] }}</span>
      </transition>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';

const props = defineProps<{
  steps?: string[];
}>();

const defaultSteps = [
  '正在阅读素材...',
  '分析核心观点...',
  '构思文章结构...',
  '组织语言表达...',
  '优化内容细节...',
];

const steps = props.steps || defaultSteps;
const currentStep = ref(0);
let timer: ReturnType<typeof setInterval> | null = null;

onMounted(() => {
  timer = setInterval(() => {
    currentStep.value = (currentStep.value + 1) % steps.length;
  }, 2000);
});

onUnmounted(() => {
  if (timer) clearInterval(timer);
});
</script>

<style scoped>
.ai-thinking {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
  gap: 24px;
}

.ai-thinking-orb {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  animation: breathe 2s ease-in-out infinite;
  box-shadow: 0 8px 32px rgba(102, 126, 234, 0.3);
}

.orb-inner {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.9);
  animation: pulse-inner 1.5s ease-in-out infinite;
}

@keyframes breathe {
  0%, 100% {
    transform: scale(1);
    box-shadow: 0 8px 32px rgba(102, 126, 234, 0.3);
  }
  50% {
    transform: scale(1.08);
    box-shadow: 0 12px 48px rgba(102, 126, 234, 0.4);
  }
}

@keyframes pulse-inner {
  0%, 100% {
    opacity: 0.8;
    transform: scale(1);
  }
  50% {
    opacity: 1;
    transform: scale(0.9);
  }
}

.ai-thinking-steps {
  min-height: 24px;
}

.step-text {
  font-size: 15px;
  font-weight: 500;
  color: #666;
  display: inline-block;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.fade-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

.fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
