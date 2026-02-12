
<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { SwitchButton, Edit, CopyDocument, Document, Check, Stamp } from '@element-plus/icons-vue'
import { http } from './api/http'
import { clearAuth, getUser } from './auth'

const apiStatus = ref('unknown') // unknown, success, error
const route = useRoute()
const router = useRouter()
const user = ref(getUser())

let timer = null

const isLoginPage = computed(() => route.path === '/login')

async function checkHealth() {
  try {
    // 假设后端有 /api/health 接口
    // 如果没有，可以调用 /dicts/subjects 等轻量接口替代
    await http.get('/health', { timeout: 3000 })
    apiStatus.value = 'success'
  } catch (e) {
    apiStatus.value = 'error'
  }
}

async function logout() {
  clearAuth()
  user.value = null
  await router.push('/login')
}

onMounted(() => {
  checkHealth()
  timer = setInterval(checkHealth, 30000)
})

watch(
  () => route.path,
  () => {
    user.value = getUser()
  },
)

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <router-view v-if="isLoginPage" />

  <el-container v-else class="layout">
    <el-header class="header">
      <div class="brand">智能组卷系统</div>
      <div class="right">
        <div v-if="user" class="user">
          <span class="userName">{{ user.name }}</span>
          <el-button size="small" @click="logout" :icon="SwitchButton">退出登录</el-button>
        </div>
        <div class="health-check">
          <div class="indicator" :class="apiStatus"></div>
          <span>API连通性</span>
        </div>
      </div>
    </el-header>

    <el-container class="container-body">
      <el-aside class="aside" width="220px">
        <el-menu router :default-active="$route.path" class="menu">
          <el-menu-item index="/dicts">
            <el-icon><Collection /></el-icon>
            <span>基础信息</span>
          </el-menu-item>
          <el-sub-menu index="/ai-review">
            <template #title>
              <el-icon><MagicStick /></el-icon>
              <span>AI出题</span>
            </template>
            <el-menu-item index="/ai-review/text">
              <el-icon><Edit /></el-icon>
              <span>AI出题</span>
            </el-menu-item>
            <el-menu-item index="/ai-review/paper">
              <el-icon><CopyDocument /></el-icon>
              <span>试卷变式</span>
            </el-menu-item>
            <el-menu-item index="/ai-review/file">
              <el-icon><Document /></el-icon>
              <span>文档变式</span>
            </el-menu-item>
            <el-menu-item index="/question-verify">
              <el-icon><Check /></el-icon>
              <span>题目校验</span>
            </el-menu-item>
          </el-sub-menu>
          <el-menu-item index="/textbooks">
            <el-icon><Notebook /></el-icon>
            <span>教材管理</span>
          </el-menu-item>
          <el-menu-item index="/questions">
            <el-icon><DocumentCopy /></el-icon>
            <span>题库管理</span>
          </el-menu-item>
          <el-sub-menu index="paper-management">
            <template #title>
              <el-icon><Files /></el-icon>
              <span>试卷管理</span>
            </template>
            <el-menu-item index="/paper-generate">
              <el-icon><Cpu /></el-icon>
              <span>智能组卷</span>
            </el-menu-item>
            <el-menu-item index="/papers">
              <el-icon><Edit /></el-icon>
              <span>试卷编辑/导出</span>
            </el-menu-item>
            <el-menu-item index="/paper-review">
              <el-icon><Stamp /></el-icon>
              <span>试卷审核</span>
            </el-menu-item>
          </el-sub-menu>
          <el-menu-item index="/answer-sheets">
            <el-icon><Tickets /></el-icon>
            <span>答题卡</span>
          </el-menu-item>
        </el-menu>
      </el-aside>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--el-border-color);
  height: 60px;
}

.brand {
  font-weight: 700;
  letter-spacing: 0.5px;
}

.right {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 14px;
}

.user {
  display: flex;
  align-items: center;
  gap: 10px;
}

.userName {
  color: var(--el-text-color-regular);
}

.health-check {
  display: flex;
  align-items: center;
  gap: 8px;
}

.indicator {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background-color: var(--el-text-color-disabled); /* unknown */
  transition: background-color 0.3s;
}

.indicator.success {
  background-color: var(--el-color-success);
}

.indicator.error {
  background-color: var(--el-color-danger);
}

.container-body {
  flex: 1;
  overflow: hidden;
  display: flex;
}

.aside {
  border-right: 1px solid var(--el-border-color);
  height: 100%;
  overflow-y: auto;
  background-color: var(--el-bg-color-page);
}

.menu {
  border-right: none;
  background-color: transparent;
  padding: 8px;
}

:deep(.el-menu-item),
:deep(.el-sub-menu__title) {
  border-radius: 8px;
  margin-bottom: 4px;
  height: 44px;
  line-height: 44px;
  font-size: 15px;
  font-weight: 500;
}

:deep(.el-menu-item.is-active) {
  background-color: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-weight: 600;
}

:deep(.el-menu-item:hover),
:deep(.el-sub-menu__title:hover) {
  background-color: var(--el-fill-color);
}

/* Submenu container styling */
:deep(.el-sub-menu .el-menu) {
  background-color: var(--el-fill-color-lighter);
  border-radius: 8px;
  margin: 4px 8px 8px 8px; /* Indent the whole submenu block */
  padding: 4px;
}

/* Submenu item specific styling */
:deep(.el-sub-menu .el-menu-item) {
  min-width: unset;
  margin: 0 0 2px 0;
  width: auto;
  height: 36px;
  line-height: 36px;
  font-size: 13px; /* Smaller font size */
  color: var(--el-text-color-regular);
}

:deep(.el-sub-menu .el-menu-item:hover) {
  background-color: var(--el-fill-color-darker);
}

:deep(.el-sub-menu .el-menu-item.is-active) {
  background-color: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}

.main {
  padding: 16px;
  flex: 1;
  overflow-y: auto;
}
</style>
