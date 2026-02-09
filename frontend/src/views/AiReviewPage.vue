<script setup>
import { onMounted, onUnmounted, reactive, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { VideoPlay, Plus, Delete, Close, Refresh } from '@element-plus/icons-vue'
import { http } from '../api/http'
import { getToken } from '../auth'

const loading = ref(false)
const error = ref('')
const router = useRouter()

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

const modifiedRows = reactive(new Set())
const hasUnsavedChanges = computed(() => modifiedRows.size > 0)
const saving = ref(false)

function handleRowChange(row) {
  modifiedRows.add(row)
}

async function saveChanges() {
  if (modifiedRows.size === 0) return
  saving.value = true
  try {
    const items = Array.from(modifiedRows).map(row => ({
      question_id: row.question_id,
      chapter_id: row.chapter_id,
      difficulty_id: row.difficulty_id
    }))
    
    // We can use update_question endpoint one by one or implement a batch update
    // Since we don't have batch update for arbitrary fields, let's use loop for now or add batch endpoint
    // Actually /questions/batch-create exists, but not batch-update for general fields.
    // However, updating one by one is slow.
    // Let's assume we can call PUT /questions/:id
    
    // For better UX, let's do it in parallel
    const promises = items.map(item => http.put(`/questions/${item.question_id}`, item))
    await Promise.all(promises)
    
    ElMessage.success('保存成功')
    modifiedRows.clear()
    
    // Reload questions to reflect changes (e.g. chapter name) if needed, 
    // but we updated local state. Just in case names need update from backend logic:
    // await loadGeneratedQuestions(items.map(i => i.question_id)) 
    // Actually we changed IDs, but names (difficulty_name) might be stale if we rely on them.
    // But dropdowns use IDs. The display span uses names.
    // If we toggle out of 'file' tab, we might see old names. 
    // But since this is a transient result view, maybe it's fine.
    
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.message || '未知错误'))
  } finally {
    saving.value = false
  }
}

const streamBodyRef = ref(null)
let eventSource = null
let typingTimer = null
let pollingTimer = null
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

const activeTab = ref('text')
const papers = ref([])
const sourcePaperId = ref(null)
const uploadFile = ref(null)
const fileList = ref([])

const filterTextbookId = ref(null)
const filterReviewer = ref('')
const reviewers = ref([])

const loadReviewers = async () => {
  try {
    const res = await http.get('/papers/reviewers')
    reviewers.value = res.data.items || []
  } catch (e) {
    console.error(e)
  }
}

async function loadPapers() {
  const params = gen.subject_id ? { subject_id: gen.subject_id } : {}
  if (filterTextbookId.value) params.textbook_id = filterTextbookId.value
  if (filterReviewer.value) params.reviewer = filterReviewer.value

  const resp = await http.get('/papers', { params })
  papers.value = resp.data.items || []
}

function handleFileChange(file) {
  const rawFile = file.raw
  const isLt10M = rawFile.size / 1024 / 1024 < 10
  const isValidType = ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'].includes(rawFile.type) || /\.(pdf|doc|docx)$/i.test(rawFile.name)

  if (!isValidType) {
    ElMessage.error('只能上传 PDF/Word 文件!')
    fileList.value = []
    uploadFile.value = null
    return
  }
  if (!isLt10M) {
    ElMessage.error('文件大小不能超过 10MB!')
    fileList.value = []
    uploadFile.value = null
    return
  }

  fileList.value = [file]
  uploadFile.value = rawFile
}

const isChapterSelectionDisabled = computed(() => {
  return ['paper', 'file'].includes(activeTab.value)
})

function handleChapterWrapperClick() {
  if (isChapterSelectionDisabled.value) {
    ElMessage.info('无需选择章节，生成后可手动设置')
  }
}

async function generate() {
  // 1. 基础校验：科目必选（除非后续改为也不需要科目，但目前保持需要）
  if (!gen.subject_id) {
    ElMessage.warning('请选择科目')
    return
  }

  // 2. 模式特定的校验
  if (activeTab.value === 'text') {
    if (gen.chapter_ids.length === 0) {
      ElMessage.warning('请至少选择一个章节')
      return
    }
  }

  // Common logic for weights (only if chapters selected)
  const finalWeights = {}
  if (gen.chapter_ids.length > 0) {
    for (const cid of rootSelectedChapters.value) {
      if (gen.chapter_weights[cid] !== undefined) {
        finalWeights[cid] = gen.chapter_weights[cid]
      }
    }
  }

  loading.value = true
  error.value = ''
  generated.items = [] // 清空上次生成结果

  try {
    let resp;
    if (activeTab.value === 'text') {
      if (gen.type_ids.length === 0) {
        ElMessage.warning('请至少选择一个题型')
        loading.value = false
        return
      }
      
      const rules = []
      for (const tid of gen.type_ids) {
        const cfg = gen.configs[tid]
        if (!cfg || !Array.isArray(cfg.rules) || cfg.rules.length === 0) {
          ElMessage.warning('请为每个题型至少配置一种难度与数量')
          loading.value = false
          return
        }
        // ... (existing validation logic)
        for (const r of cfg.rules) {
           if (!r || !r.difficulty_id || !r.count) continue
           rules.push({
             type_id: tid,
             difficulty_id: r.difficulty_id,
             count: r.count,
           })
        }
      }
      if (rules.length === 0) {
          ElMessage.warning('请完善题型配置')
          loading.value = false
          return
      }

      resp = await http.post('/ai/generate-questions', {
        subject_id: gen.subject_id,
        chapter_ids: gen.chapter_ids, 
        chapter_weights: finalWeights,
        rules: rules,
        create_user: gen.create_user,
      })
    } else if (activeTab.value === 'paper') {
      if (!sourcePaperId.value) {
        ElMessage.warning('请选择来源试卷')
        loading.value = false
        return
      }
      resp = await http.post('/ai/generate-from-paper', {
        paper_id: sourcePaperId.value,
        subject_id: gen.subject_id,
        chapter_ids: gen.chapter_ids,
        create_user: gen.create_user,
      })
    } else if (activeTab.value === 'file') {
      if (!gen.textbook_id) {
        ElMessage.warning('请选择教材')
        loading.value = false
        return
      }
      if (!uploadFile.value) {
        ElMessage.warning('请上传文件')
        loading.value = false
        return
      }
      const formData = new FormData()
      formData.append('file', uploadFile.value)
      formData.append('subject_id', gen.subject_id)
      // 文档变式模式下，不再使用手动选择的章节
      // formData.append('chapter_ids', gen.chapter_ids.join(','))
      formData.append('create_user', gen.create_user)
      
      resp = await http.post('/ai/generate-from-file', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
    }

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
  if (pollingTimer) {
    clearInterval(pollingTimer)
    pollingTimer = null
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
  if (activeTab.value === 'text') {
    Object.values(gen.configs).forEach(cfg => {
      (cfg.rules || []).forEach(r => total += (r.count || 0))
    })
  } else {
    // 变式模式下，总数由后端决定，初始设为0，等待 job_start 事件更新
    total = 0
  }
  stream.totalCount = total

  outputQueue = ''
  pushLine(`任务已创建：${jobId}`)

  let lastEventId = 0

  pollingTimer = setInterval(async () => {
    try {
      const resp = await http.get(`/ai/jobs/${jobId}`)
      const job = resp.data.job
      if (!job) return

      // 更新总数 (变式模式下)
      if (stream.totalCount === 0 && job.total_count) {
          stream.totalCount = job.total_count
      }

      const events = job.events || []
      const newEvents = events.filter(e => (e.id || 0) > lastEventId)
      newEvents.sort((a, b) => (a.id || 0) - (b.id || 0))

      for (const ev of newEvents) {
        lastEventId = ev.id || lastEventId
        
        if (ev.type === 'ai_delta') {
          const t = ev?.data?.text || ''
          stream.currentStage = '正在生成题目...'
          enqueueOutput(t)
        } else {
          const ts = ev.ts ? `【${ev.ts}】` : ''
          const msg = ev.message ? ` ${ev.message}` : ''
          pushLine(`${ts}${ev.type}${msg}`)
          
          if (ev.type === 'job_start') {
            if (ev.data && ev.data.total_count) {
              stream.totalCount = ev.data.total_count
            }
          } else if (ev.type === 'job_done') {
            stream.status = 'done'
            stream.currentStage = '生成完成'
            stream.progress = 100
            stream.generatedCount = stream.totalCount
            
            stopStream()
            fetchJobDetails(stream.job_id)
            
            setTimeout(() => {
              stream.visible = false
            }, 1500)
          } else if (ev.type === 'job_error') {
            stream.status = 'error'
            stream.currentStage = '生成出错'
            stopStream()
          }
        }
      }
      
      // 如果后端状态已经是 done/error，但前面还没处理到 job_done 事件（极端情况），也强制结束
      if (job.status === 'done' && stream.status !== 'done') {
          // 这里可以选择是否补发 job_done 逻辑，或者直接结束
          // 为保险起见，如果轮询发现 done，且我们还没处理完事件，可以继续轮询直到事件处理完
          // 或者直接认为完成了。
          // 既然上面已经在处理 events，理论上最终会遇到 job_done。
          // 除非 events 丢失。
          // 作为一个兜底，如果 job.status 是 done 且 events 也没新的了，就强制完成
          if (newEvents.length === 0) {
              stream.status = 'done'
              stream.currentStage = '生成完成'
              stream.progress = 100
              stopStream()
              fetchJobDetails(stream.job_id)
              setTimeout(() => { stream.visible = false }, 1500)
          }
      } else if (job.status === 'error' && stream.status !== 'error') {
          if (newEvents.length === 0) {
              stream.status = 'error'
              stream.currentStage = '生成出错'
              stopStream()
          }
      }

    } catch (e) {
      console.error(e)
    }
  }, 1000)
}

function startPolling(jobId) {
  if (pollingTimer) clearInterval(pollingTimer)
  pollingTimer = setInterval(async () => {
    try {
      const resp = await http.get(`/ai/jobs/${jobId}`)
      const job = resp.data.job
      if (job.status === 'done') {
        clearInterval(pollingTimer)
        pollingTimer = null
        await fetchJobDetails(jobId)
        ElMessageBox.alert('后台生成任务已完成！', '提示', {
          confirmButtonText: '查看结果',
          type: 'success'
        })
      } else if (job.status === 'error') {
        clearInterval(pollingTimer)
        pollingTimer = null
        ElMessageBox.alert(`后台生成任务失败：${job.error || '未知错误'}`, '错误', {
          confirmButtonText: '关闭',
          type: 'error'
        })
      }
    } catch (e) {
      console.error('polling error', e)
    }
  }, 3000)
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
  await loadReviewers()
})

onUnmounted(() => {
  stopStream()
  if (pollingTimer) {
    clearInterval(pollingTimer)
    pollingTimer = null
  }
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
              filterTextbookId = null
              await loadTextbooks()
              if (activeTab === 'paper') await loadPapers()
            }
          "
        >
          <el-option v-for="s in subjects" :key="s.subject_id" :label="s.subject_name" :value="s.subject_id" />
        </el-select>

        <el-select
          v-if="activeTab !== 'paper'"
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
          <el-option v-for="t in textbooks" :key="t.textbook_id" :label="t.textbook_name + (t.author ? ' (' + t.author + ')' : '')" :value="t.textbook_id" />
        </el-select>

        <div v-if="activeTab === 'text'" @click="handleChapterWrapperClick" class="chapter-select-wrapper">
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
            :disabled="isChapterSelectionDisabled"
            @change="handleChapterChange"
          />
        </div>
      </div>

      <el-tabs v-model="activeTab" type="border-card" style="margin-top: 16px" @tab-click="() => { if(activeTab === 'paper' && papers.length === 0) loadPapers() }">
        <el-tab-pane label="AI 出题" name="text">
          <div class="formRow">
            <el-select
              v-model="gen.type_ids"
              multiple
              collapse-tags
              collapse-tags-tooltip
              clearable
              placeholder="选择题型（多选）"
              style="width: 100%"
              @change="handleTypeChange"
            >
              <el-option v-for="t in types" :key="t.type_id" :label="t.type_name" :value="t.type_id" />
            </el-select>
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
        </el-tab-pane>

        <el-tab-pane label="试卷变式" name="paper">
          <div style="margin-bottom: 12px; display: flex; gap: 8px">
            <el-select
              v-model="filterTextbookId"
              clearable
              placeholder="筛选教材"
              style="width: 200px"
              @change="loadPapers"
            >
              <el-option v-for="t in textbooks" :key="t.textbook_id" :label="t.textbook_name + (t.author ? ' (' + t.author + ')' : '')" :value="t.textbook_id" />
            </el-select>
            <el-select
              v-model="filterReviewer"
              clearable
              placeholder="筛选审核人"
              style="width: 150px"
              @change="loadPapers"
            >
              <el-option v-for="r in reviewers" :key="r" :label="r" :value="r" />
            </el-select>
            <el-button :icon="Refresh" circle @click="loadPapers" />
          </div>

          <el-select 
            v-model="sourcePaperId" 
            placeholder="请选择参考试卷" 
            style="width: 100%"
            filterable
          >
            <el-option 
              v-for="p in papers" 
              :key="p.paper_id" 
              :label="p.paper_name" 
              :value="p.paper_id" 
            />
          </el-select>
          <div class="tip-text">系统将分析选中试卷的题型、难度与风格以及相关联的章节，为您选中的试卷生成类似的变式题目。</div>
        </el-tab-pane>

        <el-tab-pane label="文档变式" name="file">
          <el-upload
            class="upload-demo"
            drag
            action=""
            :auto-upload="false"
            :limit="1"
            :on-change="handleFileChange"
            :file-list="fileList"
            accept=".pdf,.doc,.docx"
          >
            <el-icon class="el-icon--upload"><upload-filled /></el-icon>
            <div class="el-upload__text">拖拽文件到此处或 <em>点击上传</em></div>
            <template #tip>
              <div class="el-upload__tip">
                支持 PDF/Word 文件。系统将分析文档内容，为目标章节生成相关题目。
              </div>
            </template>
          </el-upload>
        </el-tab-pane>
      </el-tabs>

      <!-- 章节权重配置区域 (Common) -->
      <div v-if="gen.chapter_ids.length > 0 && activeTab === 'text'" class="config-list" style="margin-top: 16px">
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
          <div style="display: flex; gap: 8px">
            <el-button v-if="hasUnsavedChanges" type="success" :loading="saving" @click="saveChanges">保存修改</el-button>
            <el-button link type="primary" @click="router.push('/question-verify')">前往校验页面 &gt;</el-button>
          </div>
        </div>
      </template>
      <el-table :data="generated.items" style="width: 100%" v-loading="generated.loading">
        <el-table-column prop="question_id" label="ID" width="80" />
        <el-table-column prop="subject_name" label="科目" width="120" />
        <el-table-column label="章节" width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tree-select
              v-if="activeTab === 'file'"
              v-model="row.chapter_id"
              :data="chapterTree"
              :props="{ label: 'chapter_name', children: 'children', value: 'chapter_id' }"
              node-key="chapter_id"
              check-strictly
              clearable
              placeholder="请选择章节"
              size="small"
              style="width: 100%"
              @change="() => handleRowChange(row)"
            />
            <span v-else>{{ row.chapter_name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="type_name" label="题型" width="100" />
        <el-table-column label="难度" width="120">
          <template #default="{ row }">
            <el-select 
              v-if="activeTab === 'file'"
              v-model="row.difficulty_id" 
              placeholder="难度" 
              size="small" 
              style="width: 100%"
              @change="() => handleRowChange(row)"
            >
              <el-option v-for="d in difficulties" :key="d.difficulty_id" :label="d.difficulty_name" :value="d.difficulty_id" />
            </el-select>
            <span v-else>{{ row.difficulty_name }}</span>
          </template>
        </el-table-column>
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