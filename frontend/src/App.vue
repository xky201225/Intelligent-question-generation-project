<script setup>
import { computed, onMounted, onUnmounted, ref, watch, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NIcon, NConfigProvider, darkTheme, zhCN, dateZhCN } from 'naive-ui'
import {
  LogOutOutline,
  BookOutline,
  DocumentTextOutline,
  CheckmarkCircleOutline,
  LayersOutline,
  FileTrayFullOutline,
  SettingsOutline,
  CreateOutline,
  CopyOutline,
  DocumentOutline,
  CheckmarkOutline,
  FlashOutline,
  NewspaperOutline,
  RibbonOutline,
  TicketOutline,
  SunnyOutline,
  MoonOutline,
  WifiOutline,
  CloudOfflineOutline
} from '@vicons/ionicons5'
import { http } from './api/http'
import { clearAuth, getUser } from './auth'
import { useTaskStore } from './stores/taskStore'
import { NProgress } from 'naive-ui'

const apiStatus = ref('unknown') // unknown, success, error
const route = useRoute()
const router = useRouter()
const user = ref(getUser())
const taskStore = useTaskStore()

const isDarkMode = ref(false)
const collapsed = ref(true) // 默认折叠
let themeMediaQuery = null
let themeMediaListener = null

// 主题色 - 蓝色
const primaryColor = '#2080f0'

// 主题覆盖配置
const themeOverrides = computed(() => ({
  common: {
    primaryColor: primaryColor,
    primaryColorHover: '#4098fc',
    primaryColorPressed: '#1060c9',
    primaryColorSuppl: primaryColor
  }
}))

function applyTheme(nextIsDark) {
  const mode = nextIsDark ? 'dark' : 'light'
  document.documentElement.dataset.theme = mode
  localStorage.setItem('theme', mode)
  const metaColorScheme = document.querySelector('meta[name="color-scheme"]')
  if (metaColorScheme) {
    metaColorScheme.content = mode
  }
}

function initTheme() {
  const saved = localStorage.getItem('theme')
  if (saved === 'dark' || saved === 'light') {
    isDarkMode.value = saved === 'dark'
    applyTheme(isDarkMode.value)
    return
  }

  themeMediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
  isDarkMode.value = themeMediaQuery.matches
  applyTheme(isDarkMode.value)
  themeMediaListener = (e) => {
    if (localStorage.getItem('theme')) return
    isDarkMode.value = e.matches
    applyTheme(isDarkMode.value)
  }
  themeMediaQuery.addEventListener('change', themeMediaListener)
}

function toggleTheme() {
  isDarkMode.value = !isDarkMode.value
  applyTheme(isDarkMode.value)
}

let timer = null

const isLoginPage = computed(() => route.path === '/login')

async function checkHealth() {
  try {
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

const renderIcon = (icon) => {
  return () => h(NIcon, null, { default: () => h(icon) })
}

const menuOptions = computed(() => [
  {
    label: '基础信息',
    key: '/dicts',
    icon: renderIcon(SettingsOutline)
  },
  {
    label: '智能出题',
    key: '/ai-review',
    icon: renderIcon(FlashOutline),
    children: [
      { label: 'AI出题', key: '/ai-review/text', icon: renderIcon(CreateOutline) },
      { label: '试卷变式', key: '/ai-review/paper', icon: renderIcon(CopyOutline) },
      { label: '文档变式', key: '/ai-review/file', icon: renderIcon(DocumentOutline) },
      { label: '题目校验', key: '/question-verify', icon: renderIcon(CheckmarkOutline) }
    ]
  },
  {
    label: '教材管理',
    key: '/textbooks',
    icon: renderIcon(BookOutline)
  },
  {
    label: '题库管理',
    key: '/questions',
    icon: renderIcon(DocumentTextOutline)
  },
  {
    label: '试卷管理',
    key: 'paper-management',
    icon: renderIcon(FileTrayFullOutline),
    children: [
      { label: '智能组卷', key: '/paper-generate', icon: renderIcon(LayersOutline) },
      { label: '试卷编辑/导出', key: '/papers', icon: renderIcon(NewspaperOutline) },
      { label: '试卷审核', key: '/paper-review', icon: renderIcon(RibbonOutline) }
    ]
  },
  {
    label: '答题卡',
    key: '/answer-sheets',
    icon: renderIcon(TicketOutline)
  }
])

const activeKey = computed(() => route.path)

function handleMenuUpdate(key) {
  if (!key.startsWith('/')) return
  router.push(key)
}

onMounted(() => {
  checkHealth()
  timer = setInterval(checkHealth, 30000)
  initTheme()
})

watch(
  () => route.path,
  () => {
    user.value = getUser()
  },
)

onUnmounted(() => {
  if (timer) clearInterval(timer)
  if (themeMediaQuery && themeMediaListener) {
    themeMediaQuery.removeEventListener('change', themeMediaListener)
  }
})
</script>

<template>
  <n-config-provider :theme="isDarkMode ? darkTheme : null" :theme-overrides="themeOverrides" :locale="zhCN" :date-locale="dateZhCN">
    <n-message-provider>
      <n-dialog-provider>
        <router-view v-if="isLoginPage" />

        <n-layout v-else class="layout" has-sider>
          <n-layout-sider
            v-model:collapsed="collapsed"
            bordered
            collapse-mode="width"
            :collapsed-width="64"
            :width="220"
            show-trigger
            content-style="display: flex; flex-direction: column;"
          >
            <div class="logo" :class="{ 'logo-collapsed': collapsed }">
              {{ collapsed ? '组卷' : '智能组卷系统' }}
            </div>
            <n-menu
              :options="menuOptions"
              :value="activeKey"
              :collapsed="collapsed"
              @update:value="handleMenuUpdate"
              :collapsed-width="64"
              :collapsed-icon-size="22"
              style="flex: 1;"
            />
            <div class="aside-footer">
              <!-- 主题切换按钮 -->
              <n-tooltip v-if="collapsed" placement="right">
                <template #trigger>
                  <div class="footer-item" @click="toggleTheme">
                    <n-icon size="18" class="footer-icon">
                      <SunnyOutline v-if="isDarkMode" />
                      <MoonOutline v-else />
                    </n-icon>
                  </div>
                </template>
                {{ isDarkMode ? '切换到亮色' : '切换到暗色' }}
              </n-tooltip>
              <div v-else class="footer-item" @click="toggleTheme">
                <n-icon size="18" class="footer-icon">
                  <SunnyOutline v-if="isDarkMode" />
                  <MoonOutline v-else />
                </n-icon>
                <span class="footer-text">{{ isDarkMode ? '切换到亮色' : '切换到暗色' }}</span>
              </div>

              <!-- API 连通性状态 -->
              <n-tooltip v-if="collapsed" placement="right">
                <template #trigger>
                  <div class="footer-item api-item" :class="apiStatus">
                    <n-icon size="18" class="footer-icon">
                      <WifiOutline v-if="apiStatus === 'success'" />
                      <CloudOfflineOutline v-else />
                    </n-icon>
                  </div>
                </template>
                API {{ apiStatus === 'success' ? '已连接' : '未连接' }}
              </n-tooltip>
              <div v-else class="footer-item api-item" :class="apiStatus">
                <n-icon size="18" class="footer-icon">
                  <WifiOutline v-if="apiStatus === 'success'" />
                  <CloudOfflineOutline v-else />
                </n-icon>
                <span class="footer-text">API {{ apiStatus === 'success' ? '已连接' : '未连接' }}</span>
              </div>
            </div>
          </n-layout-sider>

          <n-layout>
            <n-layout-header bordered class="header">
              <div class="header-left"></div>
              <div class="right">
                <div v-if="taskStore.task.status === 'running' || taskStore.task.status === 'done'" class="task-status-bar" @click="() => { router.push(taskStore.task.sourcePath); taskStore.showPanel = true }">
                  <n-progress
                    v-if="taskStore.task.status === 'running'"
                    type="circle"
                    :percentage="taskStore.task.progress"
                    :status="taskStore.task.status === 'error' ? 'error' : 'default'"
                    style="width: 24px; height: 24px"
                    :stroke-width="4"
                    :show-indicator="false"
                  >
                  </n-progress>
                  <n-icon v-else size="20" color="#18a058"><CheckmarkCircleOutline /></n-icon>
                  <span class="task-status-text">
                    {{ taskStore.task.status === 'running' ? 'AI处理中...' : '处理完成' }}
                  </span>
                </div>

                <div v-if="user" class="user">
                  <span class="userName">{{ user.name }}</span>
                  <n-button size="small" @click="logout">
                    <template #icon>
                      <n-icon><LogOutOutline /></n-icon>
                    </template>
                    退出登录
                  </n-button>
                </div>
              </div>
            </n-layout-header>

            <n-layout-content class="main" content-style="padding: 16px;">
              <router-view />
            </n-layout-content>
          </n-layout>
        </n-layout>
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<style scoped>
.layout {
  height: 100vh;
}

.logo {
  padding: 16px;
  font-weight: 700;
  font-size: 16px;
  text-align: center;
  border-bottom: 1px solid var(--n-border-color);
  white-space: nowrap;
  overflow: hidden;
  transition: all 0.3s;
}

.logo-collapsed {
  padding: 16px 8px;
  font-size: 14px;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 60px;
  padding: 0 20px;
}

.header-left {
  flex: 1;
}

.right {
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

.main {
  overflow-y: auto;
}

.aside-footer {
  padding: 8px;
  border-top: 1px solid var(--n-border-color);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.footer-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  font-size: 13px;
  color: var(--n-text-color-3);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.footer-item:hover {
  background-color: var(--n-color-hover);
  color: var(--n-text-color-2);
}

.footer-icon {
  flex-shrink: 0;
}

.footer-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* API 状态颜色 */
.api-item.success {
  color: #18a058;
}

.api-item.success:hover {
  background-color: rgba(24, 160, 88, 0.1);
  color: #18a058;
}

.api-item.error {
  color: #d03050;
}

.api-item.error:hover {
  background-color: rgba(208, 48, 80, 0.1);
  color: #d03050;
}

.api-item.unknown {
  color: var(--n-text-color-3);
}
:deep(.n-button) {
  border-radius: 14px;
}

.task-status-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: var(--n-color-embedded);
  border-radius: 20px;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  border: 1px solid var(--n-border-color);
  animation: slideIn 0.5s ease-out;
}

.task-status-bar:hover {
  background: var(--n-color-hover);
  transform: translateY(1px);
}

.task-status-text {
  font-size: 12px;
  font-weight: 500;
  color: var(--n-text-color-2);
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
