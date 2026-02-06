<script setup>
import { onMounted, onUnmounted, reactive, ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { VideoPlay, Plus, Delete, Close, Refresh } from '@element-plus/icons-vue'
import { http } from '../api/http'
import { getToken } from '../auth'

const loading = ref(false)
const error = ref('')

const subjects = ref([])
const types = ref([])
const difficulties = ref([])
const textbooks = ref([])
const chapters = ref([])
const chapterTree = ref([])

const rootSelectedChapters = computed(() => {
  const selectedSet = new Set(gen.chapter_ids)
  const roots = []

  // 判断节点是否被选中（显式选中或隐式全选）
  const isSelected = (node) => {
    // 1. 显式选中
    if (selectedSet.has(node.chapter_id)) return true
    // 2. 隐式全选（必须有子节点，且所有子节点都被选中）
    if (node.children && node.children.length > 0) {
      return node.children.every(child => isSelected(child))
    }
    return false
  }

  // 遍历树寻找最高层级的选中节点
  const traverse = (nodes) => {
    for (const node of nodes) {
      if (isSelected(node)) {
        roots.push(node.chapter_id)
        // 既然父节点被视为选中，就不再展示子节点
      } else {
        if (node.children && node.children.length > 0) {
          traverse(node.children)
        }
      }
    }
  }

  traverse(chapterTree.value)
  return roots.sort((a, b) => a - b)
})

const gen = reactive({
  subject_id: null,
  textbook_id: null,
  chapter_ids: [],
  chapter_weights: {}, // {chapter_id: weight}
  type_ids: [],
  configs: {},
  create_user: 'ai',
})

const stream = reactive({
  visible: false,
  job_id: null,
  status: 'idle',
  lines: [],
  output: '',
  progress: 0,
  generatedCount: 0,
  totalCount: 0,
  currentStage: '',
})

const generated = reactive({
  items: [],
  loading: false,
})

const streamBodyRef = ref(null)
let eventSource = null
let typingTimer = null
let outputQueue = ''

async function loadDicts() {
  const [s, t, d] = await Promise.all([
    http.get('/dicts/subjects'),
    http.get('/dicts/question-types'),
    http.get('/dicts/difficulties'),
  ])
  subjects.value = s.data.items || []
  types.value = t.data.items || []
  difficulties.value = d.data.items || []
}

async function loadTextbooks() {
  const resp = await http.get('/textbooks', {
    params: gen.subject_id ? { subject_id: gen.subject_id } : {},
  })
  textbooks.value = resp.data.items || []
}

async function loadChapters() {
  if (!gen.textbook_id) {
    chapters.value = []
    chapterTree.value = []
    return
  }
  const resp = await http.get(`/textbooks/${gen.textbook_id}/chapters`)
  chapters.value = resp.data.items || []
  chapterTree.value = resp.data.tree || []
}

async function generate() {
  if (!gen.subject_id || gen.chapter_ids.length === 0 || gen.type_ids.length === 0) {
    ElMessage.warning('请选择科目、至少一个章节和至少一个题型')
    return
  }

  const rules = []
  for (const tid of gen.type_ids) {
    const cfg = gen.configs[tid]
    if (!cfg || !Array.isArray(cfg.rules) || cfg.rules.length === 0) {
      ElMessage.warning('请为每个题型至少配置一种难度与数量')
      return
    }
    const seen = new Set()
    for (const r of cfg.rules) {
      if (!r || !r.difficulty_id || !r.count) {
        ElMessage.warning('请完善选中题型的配置（难度/数量）')
        return
      }
      const key = String(r.difficulty_id)
      if (seen.has(key)) {
        ElMessage.warning(`${getTypeName(tid)} 的难度存在重复，请调整后再生成`)
        return
      }
      seen.add(key)
      rules.push({
        type_id: tid,
        difficulty_id: r.difficulty_id,
        count: r.count,
      })
    }
  }

  loading.value = true
  error.value = ''
  generated.items = [] // 清空上次生成结果
  
  // 仅传递根节点的权重配置
  const finalWeights = {}
  for (const cid of rootSelectedChapters.value) {
    if (gen.chapter_weights[cid] !== undefined) {
      finalWeights[cid] = gen.chapter_weights[cid]
    }
  }
  
  try {
    const resp = await http.post('/ai/generate-questions', {
      subject_id: gen.subject_id,
      chapter_ids: gen.chapter_ids, // 传递数组
      chapter_weights: finalWeights,
      rules: rules,
      create_user: gen.create_user,
    })
    ElMessage.success('已提交生成（后台生成中）')
    startStream(resp.data.job_id)
  } catch (e) {
    error.value = e?.message || '生成失败'
  } finally {
    loading.value = false
  }
}

async function loadGeneratedQuestions(ids) {
  if (!ids || ids.length === 0) return
  generated.loading = true
  try {
    const resp = await http.get('/questions', {
      params: { ids: ids.join(',') }
    })
    generated.items = resp.data.items || []
  } catch (e) {
    console.error(e)
  } finally {
    generated.loading = false
  }
}

async function fetchJobDetails(jobId) {
  try {
    const resp = await http.get(`/ai/jobs/${jobId}`)
    const job = resp.data.job
    if (job && job.question_ids && job.question_ids.length > 0) {
      await loadGeneratedQuestions(job.question_ids)
    }
  } catch (e) {
    console.error(e)
  }
}

function pushLine(text) {
  stream.lines.push(text)
  if (stream.lines.length > 2000) {
    stream.lines.splice(0, stream.lines.length - 2000)
  }
  requestAnimationFrame(() => scrollStreamToBottom())
}

function scrollStreamToBottom() {
  if (!streamBodyRef.value) return
  streamBodyRef.value.scrollTop = streamBodyRef.value.scrollHeight
}

function stopTyping() {
  if (typingTimer) {
    clearInterval(typingTimer)
    typingTimer = null
  }
  outputQueue = ''
}

function enqueueOutput(text) {
  if (!text) return
  outputQueue += text
  if (!typingTimer) {
    typingTimer = setInterval(() => {
      if (!outputQueue) {
        clearInterval(typingTimer)
        typingTimer = null
        return
      }
      const backlog = outputQueue.length
      const step = Math.min(60, Math.max(1, Math.floor(backlog / 120)))
      const chunk = outputQueue.slice(0, step)
      outputQueue = outputQueue.slice(step)

      stream.output += chunk
      if (stream.output.length > 200000) {
      stream.output = stream.output.slice(stream.output.length - 200000)
    }
    
    // 进度更新：每输出一个包含 "question_analysis" 的题目算作完成一题
    if (stream.totalCount > 0) {
      const matches = stream.output.match(/"question_analysis"/g)
      const count = matches ? matches.length : 0
      stream.generatedCount = Math.max(stream.generatedCount, count)
      stream.progress = Math.min(100, Math.floor((stream.generatedCount / stream.totalCount) * 100))
    }
    
    requestAnimationFrame(() => scrollStreamToBottom())
    }, 16)
  }
}

function stopStream() {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
  stopTyping()
}

function startStream(jobId) {
  stopStream()
  stream.visible = true
  stream.job_id = jobId
  stream.status = 'running'
  stream.lines = []
  stream.output = ''
  stream.progress = 0
  stream.generatedCount = 0
  stream.totalCount = 0
  stream.currentStage = '准备中...'
  
  // 计算总数
  let total = 0
  Object.values(gen.configs).forEach(cfg => {
    (cfg.rules || []).forEach(r => total += (r.count || 0))
  })
  stream.totalCount = total

  outputQueue = ''
  pushLine(`任务已创建：${jobId}`)

  const token = getToken()
  const url = `${http.defaults.baseURL}/ai/jobs/${jobId}/events${token ? `?token=${encodeURIComponent(token)}` : ''}`
  eventSource = new EventSource(url)
  eventSource.onmessage = (e) => {
    try {
      const ev = JSON.parse(e.data)
      if (ev.type === 'ai_delta') {
        const t = ev?.data?.text || ''
        stream.currentStage = '正在生成题目...'
        enqueueOutput(t)
      } else {
        const ts = ev.ts ? `【${ev.ts}】` : ''
        const msg = ev.message ? ` ${ev.message}` : ''
        pushLine(`${ts}${ev.type}${msg}`)
        if (ev.type === 'job_done') {
          stream.status = 'done'
          stream.currentStage = '生成完成'
          stream.progress = 100
          stream.generatedCount = stream.totalCount
          stopStream()
          fetchJobDetails(stream.job_id)
          // 延迟1.5秒自动关闭窗口，给用户一点时间看到“完成”状态
          setTimeout(() => {
            stream.visible = false
          }, 1500)
        } else if (ev.type === 'job_error') {
          stream.status = 'error'
          stream.currentStage = '生成出错'
          stopStream()
        }
      }
    } catch {
      pushLine(e.data || '')
    }
  }

  eventSource.onerror = () => {
    if (stream.status === 'running') {
      pushLine('连接中断：将继续在后台生成，可稍后刷新待校验列表')
    }
    stopStream()
  }
}

function handleTypeChange(val) {
  const selected = new Set(val || [])
  Object.keys(gen.configs).forEach((k) => {
    const tid = Number(k)
    if (!selected.has(tid)) {
      delete gen.configs[k]
    }
  })

  ;(val || []).forEach((tid) => {
    if (!gen.configs[tid]) {
      gen.configs[tid] = { rules: [{ difficulty_id: null, count: 5 }] }
    } else if (!Array.isArray(gen.configs[tid].rules) || gen.configs[tid].rules.length === 0) {
      gen.configs[tid].rules = [{ difficulty_id: null, count: 5 }]
    }
  })
}

function getTypeName(tid) {
  const t = types.value.find(x => x.type_id === tid)
  return t ? t.type_name : `题型${tid}`
}

function addDifficultyRule(tid) {
  const cfg = gen.configs[tid]
  if (!cfg) return
  if (!Array.isArray(cfg.rules)) cfg.rules = []
  cfg.rules.push({ difficulty_id: null, count: 5 })
}

function removeDifficultyRule(tid, index) {
  const cfg = gen.configs[tid]
  if (!cfg || !Array.isArray(cfg.rules)) return
  cfg.rules.splice(index, 1)
  if (cfg.rules.length === 0) {
    cfg.rules.push({ difficulty_id: null, count: 5 })
  }
}

function getChapterName(cid) {
  const find = (list) => {
    for (const c of list) {
      if (c.chapter_id === cid) return c.chapter_name
      if (c.children) {
        const name = find(c.children)
        if (name) return name
      }
    }
    return null
  }
  return find(chapters.value) || `章节${cid}`
}

// 递归获取所有子章节 ID
function getAllSubChapterIds(nodes) {
  let ids = []
  for (const node of nodes) {
    ids.push(node.chapter_id)
    if (node.children && node.children.length > 0) {
      ids = ids.concat(getAllSubChapterIds(node.children))
    }
  }
  return ids
}

function handleChapterChange(val) {
  // 当选择章节变化时，自动处理子章节选中逻辑
  // 并同步权重配置（只保留 rootSelectedChapters 中的项）
  
  // 此时 rootSelectedChapters 应该已经基于新的 gen.chapter_ids 更新了
  const validRoots = new Set(rootSelectedChapters.value)
  
  // 1. 清理不再需要的权重
  Object.keys(gen.chapter_weights).forEach(k => {
    if (!validRoots.has(Number(k))) {
      delete gen.chapter_weights[k]
    }
  })
  
  // 2. 为新增的 root 初始化权重
  validRoots.forEach(cid => {
    if (gen.chapter_weights[cid] === undefined) {
      gen.chapter_weights[cid] = 10
    }
  })
}

onMounted(async () => {
  await loadDicts()
  await loadTextbooks()
})

onUnmounted(() => {
  stopStream()
})
</script>

<template>
  <div class="page">
    <el-card>
      <template #header>
        <div class="header">
          <div>AI 出题</div>
          <el-button type="primary" :loading="loading" @click="generate" :icon="VideoPlay">生成</el-button>
        </div>
      </template>

      <el-alert v-if="error" :title="error" type="error" show-icon />

      <div class="formRow">
        <el-select
          v-model="gen.subject_id"
          clearable
          placeholder="科目"
          style="width: 180px"
          @change="
            async () => {
              gen.textbook_id = null
              gen.chapter_ids = []
              await loadTextbooks()
            }
          "
        >
          <el-option v-for="s in subjects" :key="s.subject_id" :label="s.subject_name" :value="s.subject_id" />
        </el-select>

        <el-select
          v-model="gen.textbook_id"
          clearable
          placeholder="教材"
          style="width: 260px"
          @change="
            async () => {
              gen.chapter_ids = []
              await loadChapters()
            }
          "
        >
          <el-option v-for="t in textbooks" :key="t.textbook_id" :label="t.textbook_name" :value="t.textbook_id" />
        </el-select>

        <el-tree-select
          v-model="gen.chapter_ids"
          :data="chapterTree"
          :props="{ label: 'chapter_name', children: 'children', value: 'chapter_id' }"
          node-key="chapter_id"
          multiple
          show-checkbox
          collapse-tags
          collapse-tags-tooltip
          clearable
          placeholder="章节（多选）"
          style="width: 260px"
          @change="handleChapterChange"
        />

        <el-select
          v-model="gen.type_ids"
          multiple
          collapse-tags
          collapse-tags-tooltip
          clearable
          placeholder="选择题型（多选）"
          style="width: 260px"
          @change="handleTypeChange"
        >
          <el-option v-for="t in types" :key="t.type_id" :label="t.type_name" :value="t.type_id" />
        </el-select>
      </div>

      <!-- 章节权重配置区域 -->
      <div v-if="gen.chapter_ids.length > 0" class="config-list">
        <div class="config-header">章节权重设置</div>
        <div class="weight-grid">
          <div v-for="cid in rootSelectedChapters" :key="cid" class="weight-item">
            <span class="weight-label" :title="getChapterName(cid)">{{ getChapterName(cid) }}</span>
            <el-input-number 
              v-model="gen.chapter_weights[cid]" 
              :min="0" 
              :max="100" 
              controls-position="right"
              style="width: 100px" 
            />
            <span class="weight-unit">%</span>
          </div>
        </div>
      </div>

      <!-- 动态配置区域 -->
      <div v-if="gen.type_ids.length > 0" class="config-list">
        <div class="config-header">题型规则配置</div>
        <div v-for="tid in gen.type_ids" :key="tid" class="config-item">
          <div class="type-name">{{ getTypeName(tid) }}</div>
          <div class="rules">
            <div v-for="(r, idx) in gen.configs[tid]?.rules" :key="idx" class="rule-row">
              <el-select v-model="r.difficulty_id" placeholder="难度" style="width: 140px">
                <el-option v-for="d in difficulties" :key="d.difficulty_id" :label="d.difficulty_name" :value="d.difficulty_id" />
              </el-select>
              <el-input-number v-model="r.count" :min="1" :max="50" style="width: 140px" />
              <el-button link type="danger" @click="removeDifficultyRule(tid, idx)" :icon="Delete">删除</el-button>
            </div>
            <el-button size="small" @click="addDifficultyRule(tid)" :icon="Plus">添加难度</el-button>
          </div>
        </div>
      </div>
    </el-card>

    <div 
      v-if="gen.chapter_ids.length === 0 && gen.type_ids.length === 0 && generated.items.length === 0" 
      class="welcome-placeholder"
    >
      欢迎使用
    </div>

    <el-card v-if="generated.items.length > 0">
      <template #header>
        <div class="header">
          <span>本次生成结果 ({{ generated.items.length }})</span>
        </div>
      </template>
      <el-table :data="generated.items" style="width: 100%" v-loading="generated.loading">
        <el-table-column prop="question_id" label="ID" width="80" />
        <el-table-column prop="subject_name" label="科目" width="120" />
        <el-table-column prop="chapter_name" label="章节" width="150" show-overflow-tooltip />
        <el-table-column prop="type_name" label="题型" width="100" />
        <el-table-column prop="difficulty_name" label="难度" width="80" />
        <el-table-column label="题目内容">
          <template #default="{ row }">
            <div class="content">{{ row.question_content }}</div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.review_status === 0" type="warning">待校验</el-tag>
            <el-tag v-else-if="row.review_status === 1" type="success">已通过</el-tag>
            <el-tag v-else-if="row.review_status === 2" type="danger">已拒绝</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <div v-if="stream.visible" class="streamPanel">
      <div class="streamHeader">
        <div class="streamTitle">
          <span>生成过程</span>
          <span class="streamMeta">ID: {{ stream.job_id }}（{{ stream.status }}）</span>
        </div>
        <div class="streamActions">
          <el-button size="small" @click="stream.output = ''; stream.lines = []" :icon="Delete">清空</el-button>
          <el-button size="small" @click="stream.visible = false" :icon="Close">关闭</el-button>
        </div>
      </div>

      <!-- 顶部固定进度栏 -->
      <div class="streamProgress">
        <div class="progress-info">
          <span class="stage-text">{{ stream.currentStage }}</span>
          <span class="count-text">已生成 {{ stream.generatedCount }} / {{ stream.totalCount }}</span>
        </div>
        <el-progress 
          :percentage="stream.progress" 
          :stroke-width="8" 
          striped 
          striped-flow 
          :duration="10"
        />
      </div>

      <div ref="streamBodyRef" class="streamBody">
        <div v-if="stream.lines.length > 0" class="streamLines">
          <div v-for="(l, i) in stream.lines" :key="i">{{ l }}</div>
        </div>
        <div v-else class="streamHint">等待事件流…</div>

        <div v-if="stream.output" class="streamOutput">
          <div class="streamOutputTitle">模型输出（实时）</div>
          <pre class="streamOutputPre">{{ stream.output }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.formRow {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.config-list {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  background-color: var(--el-fill-color-light);
  padding: 12px;
  border-radius: 4px;
}

.config-header {
  font-weight: bold;
  color: var(--el-color-primary);
  margin-bottom: 8px;
}

.config-item {
  display: flex;
  gap: 12px;
}

.type-name {
  width: 120px;
  text-align: right;
  font-weight: 700;
  color: var(--el-text-color-regular);
  padding-top: 6px;
}

.rules {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.rule-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.streamPanel {
  position: fixed;
  right: 18px;
  top: 86px;
  width: 520px;
  height: 70vh;
  background-color: var(--el-bg-color);
  border: 1px solid var(--el-border-color);
  border-radius: 10px;
  box-shadow: var(--el-box-shadow);
  display: flex;
  flex-direction: column;
  z-index: 2000;
}

.streamHeader {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid var(--el-border-color);
}

.streamTitle {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.streamMeta {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.streamActions {
  display: flex;
  gap: 8px;
}

.streamProgress {
  padding: 10px 12px;
  background-color: var(--el-bg-color-page);
  border-bottom: 1px solid var(--el-border-color);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.stage-text {
  font-weight: 500;
  color: var(--el-color-primary);
}

.count-text {
  color: var(--el-text-color-secondary);
}

.streamBody {
  padding: 10px 12px;
  overflow: auto;
  flex: 1;
}

.streamLines {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 12px;
  white-space: pre-wrap;
  color: var(--el-text-color-regular);
  margin-bottom: 12px;
}

.streamHint {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.streamOutputTitle {
  font-weight: 700;
  margin-bottom: 6px;
}

.streamOutputPre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 12px;
  color: var(--el-text-color-regular);
}

.welcome-placeholder {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
  font-size: 60px;
  font-weight: bold;
  color: var(--el-color-primary);
  opacity: 0.6;
  user-select: none;
  pointer-events: none;
}
</style>