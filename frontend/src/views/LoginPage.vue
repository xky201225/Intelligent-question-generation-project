<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock, Key, Ticket, Right, Refresh } from '@element-plus/icons-vue'
import { http } from '../api/http'
import { setToken, setUser } from '../auth'
import poster from '../poster.jpg'

const router = useRouter()
const loading = ref(false)
const mode = ref('login') // login | register

const form = reactive({
  name: '',
  password: '',
  invitationCode: '',
  captchaText: '',
})

const title = computed(() => (mode.value === 'login' ? '登录' : '注册'))
const stats = ref({
  subjects: 0,
  textbooks: 0,
  questions: 0,
  papers: 0,
  users: 0,
})

const captcha = reactive({
  id: '',
  image: '',
})

const typedText = ref('')
const introText =
  '智能组卷系统面向题库管理、章节出题、试卷生成与答题卡配置，提供高效的题目管理、AI辅助出题与多样化导出能力。'
let typingTimer = null

const statItems = computed(() => [
  { label: '已收录科目', value: stats.value.subjects, unit: '类' },
  { label: '教材数量', value: stats.value.textbooks, unit: '本' },
  { label: '题库规模', value: stats.value.questions, unit: '题' },
  { label: '试卷数量', value: stats.value.papers, unit: '份' },
])

function startTyping() {
  if (typingTimer) clearInterval(typingTimer)
  typedText.value = ''
  let idx = 0
  typingTimer = setInterval(() => {
    typedText.value += introText[idx]
    idx += 1
    if (idx >= introText.length) {
      clearInterval(typingTimer)
      typingTimer = null
    }
  }, 60)
}

async function loadCaptcha() {
  try {
    const resp = await http.get('/auth/captcha')
    captcha.id = resp.data.id || ''
    captcha.image = resp.data.image || ''
  } catch {
    captcha.id = ''
    captcha.image = ''
  }
}

async function loadStats() {
  try {
    const resp = await http.get('/auth/stats')
    stats.value = { ...stats.value, ...(resp.data || {}) }
  } catch {
    stats.value = { ...stats.value }
  }
}

async function submit() {
  const name = form.name.trim()
  if (!name || !form.password || !form.captchaText) {
    ElMessage.error('请完整填写信息')
    return
  }
  loading.value = true
  try {
    const path = mode.value === 'login' ? '/auth/login' : '/auth/register'
    const resp = await http.post(path, {
      name,
      password: form.password,
      invitationCode: form.invitationCode,
      captchaId: captcha.id,
      captchaText: form.captchaText,
    })
    setToken(resp.data.token)
    setUser(resp.data.user)
    if (mode.value === 'register' && resp.data?.user?.invitationCode) {
      ElMessage.success(`注册成功，邀请码：${resp.data.user.invitationCode}`)
    }
    await router.replace('/dicts')
  } catch (e) {
    ElMessage.error(e?.message || '操作失败')
    await loadCaptcha()
  } finally {
    loading.value = false
  }
}

watch(
  () => mode.value,
  async () => {
    form.captchaText = ''
    await loadCaptcha()
  },
)

onMounted(async () => {
  await loadCaptcha()
  await loadStats()
  startTyping()
})

onUnmounted(() => {
  if (typingTimer) clearInterval(typingTimer)
})
</script>

<template>
  <div class="login-page">
    <div class="hero">
      <el-card class="left-panel">
        <template #header>
          <div class="header">
            <div class="brand">智能组卷系统 V3</div>
            <div class="title">{{ title }}</div>
          </div>
        </template>

        <el-form label-width="72px">
          <el-form-item label="用户名">
            <el-input v-model="form.name" autocomplete="username" :prefix-icon="User" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input v-model="form.password" type="password" show-password autocomplete="current-password" :prefix-icon="Lock" />
          </el-form-item>
          <el-form-item label="验证码">
            <div class="captcha-row">
              <el-input v-model="form.captchaText" :prefix-icon="Key" />
              <div class="captcha-box" @click="loadCaptcha">
                <img v-if="captcha.image" :src="captcha.image" alt="captcha" />
                <span v-else>加载中</span>
              </div>
            </div>
          </el-form-item>
          <el-form-item v-if="mode === 'register'" label="邀请码">
            <el-input v-model="form.invitationCode" placeholder="首位注册可不填" :prefix-icon="Ticket" />
          </el-form-item>
        </el-form>

        <div class="actions">
          <el-button type="primary" :loading="loading" @click="submit" :icon="Right">{{ title }}</el-button>
          <el-button
            :disabled="loading"
            :icon="Refresh"
            @click="
              () => {
                mode = mode === 'login' ? 'register' : 'login'
              }
            "
          >
            切换到{{ mode === 'login' ? '注册' : '登录' }}
          </el-button>
        </div>
      </el-card>

      <div class="right-panel" :style="{ backgroundImage: `url(${poster})` }">
        <div class="right-mask"></div>
        <div class="right-content">
          <div class="right-title">AI智能出题</div>
          <div class="right-text">{{ typedText }}</div>
        </div>
      </div>
    </div>

    <div class="stats">
      <div v-for="item in statItems" :key="item.label" class="stat-card">
        <div class="stat-value">
          <span class="number">{{ item.value }}</span>
          <span class="unit">{{ item.unit }}</span>
        </div>
        <div class="stat-label">{{ item.label }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  padding: 32px;
  background: var(--el-bg-color-page, #f5f6f8);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 22px;
}

.hero {
  background: var(--el-bg-color, #fff);
  border-radius: 18px;
  padding: 22px;
  display: flex;
  gap: 22px;
  box-shadow: var(--el-box-shadow-light);
}

.left-panel {
  width: 420px;
  border-radius: 14px;
}

.header {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.brand {
  font-weight: 700;
}

.title {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.captcha-row {
  display: flex;
  gap: 10px;
  align-items: center;
  width: 100%;
}

.captcha-box {
  width: 120px;
  height: 40px;
  border-radius: 8px;
  border: 1px solid var(--el-border-color);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--el-fill-color-light, #fafafa);
  cursor: pointer;
  overflow: hidden;
}

.captcha-box img {
  width: 120px;
  height: 40px;
  object-fit: contain;
}

.actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.right-panel {
  width: 580px;
  border-radius: 16px;
  background-size: cover;
  background-position: center;
  min-height: 320px;
  position: relative;
  overflow: hidden;
}

.right-mask {
  position: absolute;
  inset: 0;
  background: linear-gradient(120deg, rgba(255, 255, 255, 0.92), rgba(255, 255, 255, 0.6));
}

@media (prefers-color-scheme: dark) {
  .right-mask {
    background: linear-gradient(120deg, rgba(20, 20, 20, 0.92), rgba(20, 20, 20, 0.6));
  }
}

.right-content {
  position: relative;
  z-index: 1;
  padding: 26px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 80%;
  margin: 0 auto;
  text-align: center;
  height: 100%;
  justify-content: center;
}

.right-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--el-text-color-primary, #333);
}

.right-text {
  font-size: 14px;
  line-height: 1.7;
  color: var(--el-text-color-regular, #555);
  min-height: 120px;
  white-space: pre-wrap;
}

.stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.stat-card {
  background: var(--el-bg-color, #fff);
  border-radius: 14px;
  padding: 16px;
  box-shadow: var(--el-box-shadow-light);
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 76px;
}

.stat-value {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.number {
  font-size: 22px;
  font-weight: 700;
  color: var(--el-color-primary, #2f4b7c);
}

.unit {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.stat-label {
  font-size: 13px;
  color: var(--el-text-color-regular);
}
</style>
