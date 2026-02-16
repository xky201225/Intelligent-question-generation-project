<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { PersonOutline, LockClosedOutline, KeyOutline, TicketOutline, ArrowForwardOutline, RefreshOutline } from '@vicons/ionicons5'
import { http } from '../api/http'
import { setToken, setUser } from '../auth'
import poster from '../poster.jpg'

const router = useRouter()
const message = useMessage()
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
    message.error('请完整填写信息')
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
      message.success(`注册成功，邀请码：${resp.data.user.invitationCode}`)
    }
    await router.replace('/dicts')
  } catch (e) {
    message.error(e?.message || '操作失败')
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
      <n-card class="left-panel">
        <template #header>
          <div class="header">
            <div class="brand">智能组卷系统 V3</div>
            <div class="title">{{ title }}</div>
          </div>
        </template>

        <n-form label-placement="left" label-width="72px">
          <n-form-item label="用户名">
            <n-input v-model:value="form.name" placeholder="请输入用户名">
              <template #prefix>
                <n-icon><PersonOutline /></n-icon>
              </template>
            </n-input>
          </n-form-item>
          <n-form-item label="密码">
            <n-input v-model:value="form.password" type="password" show-password-on="click" placeholder="请输入密码">
              <template #prefix>
                <n-icon><LockClosedOutline /></n-icon>
              </template>
            </n-input>
          </n-form-item>
          <n-form-item label="验证码">
            <div class="captcha-row">
              <n-input v-model:value="form.captchaText" placeholder="请输入验证码">
                <template #prefix>
                  <n-icon><KeyOutline /></n-icon>
                </template>
              </n-input>
              <div class="captcha-box" @click="loadCaptcha">
                <img v-if="captcha.image" :src="captcha.image" alt="captcha" />
                <span v-else>加载中</span>
              </div>
            </div>
          </n-form-item>
          <n-form-item v-if="mode === 'register'" label="邀请码">
            <n-input v-model:value="form.invitationCode" placeholder="首位注册可不填">
              <template #prefix>
                <n-icon><TicketOutline /></n-icon>
              </template>
            </n-input>
          </n-form-item>
        </n-form>

        <div class="actions">
          <n-button type="primary" :loading="loading" @click="submit">
            <template #icon>
              <n-icon><ArrowForwardOutline /></n-icon>
            </template>
            {{ title }}
          </n-button>
          <n-button :disabled="loading" @click="() => { mode = mode === 'login' ? 'register' : 'login' }">
            <template #icon>
              <n-icon><RefreshOutline /></n-icon>
            </template>
            切换到{{ mode === 'login' ? '注册' : '登录' }}
          </n-button>
        </div>
      </n-card>

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
  background: #f5f6f8;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 22px;
}

:global(html[data-theme="dark"]) .login-page {
  background: #18181c;
}

.hero {
  background: #fff;
  border-radius: 18px;
  padding: 22px;
  display: flex;
  gap: 22px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

:global(html[data-theme="dark"]) .hero {
  background: #2a2a2e;
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
  color: #999;
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
  border: 1px solid #e0e0e6;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fafafa;
  cursor: pointer;
  overflow: hidden;
}

:global(html[data-theme="dark"]) .captcha-box {
  border-color: #4a4a4e;
  background: #3a3a3e;
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

:global(html[data-theme="dark"]) .right-mask {
  background: linear-gradient(120deg, rgba(20, 20, 20, 0.92), rgba(20, 20, 20, 0.6));
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
}

.right-text {
  font-size: 14px;
  line-height: 1.7;
  color: #555;
  min-height: 120px;
  white-space: pre-wrap;
}

:global(html[data-theme="dark"]) .right-text {
  color: #aaa;
}

.stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.stat-card {
  background: #fff;
  border-radius: 14px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 76px;
}

:global(html[data-theme="dark"]) .stat-card {
  background: #2a2a2e;
}

.stat-value {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.number {
  font-size: 22px;
  font-weight: 700;
  color: #18a058;
}

.unit {
  font-size: 12px;
  color: #999;
}

.stat-label {
  font-size: 13px;
  color: #666;
}

:global(html[data-theme="dark"]) .stat-label {
  color: #aaa;
}
</style>
