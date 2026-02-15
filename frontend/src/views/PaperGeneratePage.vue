<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Plus, Refresh, Delete, Check, FullScreen, VideoPlay, Close } from '@element-plus/icons-vue'
import { http } from '../api/http'
import { getToken, getUser } from '../auth'

const loading = ref(false)
const error = ref('')
const saved = ref(null)

const subjects = ref([])
const textbooks = ref([])
const chapterTree = ref([])
const types = ref([])
const difficulties = ref([])

const filters = reactive({
  q: '',
  subject_id: null,
  textbook_id: null,
  author: '',
  publisher: '',
  chapter_ids: [],
  type_ids: [],
  difficulty_ids: [],
  review_status: 1,
  page: 1,
  page_size: 20,
})

const available = reactive({
  items: [],
  total: 0,
})

const availableSelection = ref([])

const paper = reactive({
  paper_name: '未命名试卷',
  exam_duration: 120,
  is_closed_book: false,
  paper_desc: '',
  creator: 'creator',
})

const picked = ref([])
const dragIndex = ref(-1)
const showPaperDrawer = ref(false)
const isDrawerFullscreen = ref(false)

const detailDialog = reactive({
  visible: false,
  item: null
})

const chapterSelectRef = ref(null)
const typeSelectRef = ref(null)
const difficultySelectRef = ref(null)
const maxChapterTags = ref(1)
const maxTypeTags = ref(1)
const maxDifficultyTags = ref(1)
let chapterResizeObserver = null
let typeResizeObserver = null
let difficultyResizeObserver = null
let chapterRecalcRaf = 0
let typeRecalcRaf = 0
let difficultyRecalcRaf = 0

function openDetail(row) {
  detailDialog.item = row
  detailDialog.visible = true
}


const publisherOptions = computed(() => {
  const set = new Set()
  for (const t of textbooks.value) {
    if (t.publisher) set.add(t.publisher)
  }
  return Array.from(set)
})

const pickedTotalScore = computed(() => {
  return picked.value.reduce((sum, it) => sum + Number(it.question_score || 0), 0)
})

function typeName(type_id) {
  const t = types.value.find((x) => x.type_id === type_id)
  return t ? t.type_name : String(type_id ?? '')
}

function difficultyName(difficulty_id) {
  const d = difficulties.value.find((x) => x.difficulty_id === difficulty_id)
  return d ? d.difficulty_name : String(difficulty_id ?? '')
}

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
    params: filters.subject_id ? { subject_id: filters.subject_id } : {},
  })
  textbooks.value = resp.data.items || []
}

async function loadChapters() {
  if (!filters.textbook_id) {
    chapterTree.value = []
    return
  }
  const resp = await http.get(`/textbooks/${filters.textbook_id}/chapters`)
  chapterTree.value = resp.data.tree || []
}

async function search() {
  loading.value = true
  error.value = ''
  try {
    const params = {
      page: filters.page,
      page_size: filters.page_size,
      q: filters.q || undefined,
      subject_id: filters.subject_id || undefined,
      textbook_id: filters.textbook_id || undefined,
      author: filters.author || undefined,
      publisher: filters.publisher || undefined,
      chapter_id: filters.chapter_ids.length > 0 ? filters.chapter_ids.join(',') : undefined,
      type_id: filters.type_ids.length > 0 ? filters.type_ids.join(',') : undefined,
      difficulty_id: filters.difficulty_ids.length > 0 ? filters.difficulty_ids.join(',') : undefined,
      review_status: filters.review_status,
    }
    const resp = await http.get('/questions', { params })
    available.items = resp.data.items || []
    available.total = resp.data.total || 0
  } catch (e) {
    error.value = e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function onAvailableSelectionChange(rows) {
  availableSelection.value = rows || []
}

function renumber() {
  picked.value.forEach((it, idx) => {
    it.question_sort = idx + 1
  })
}

function addSelected() {
  const existing = new Set(picked.value.map((x) => x.question_id))
  const toAdd = (availableSelection.value || []).filter((x) => !existing.has(x.question_id))
  if (toAdd.length === 0) {
    ElMessage.warning('没有可加入的题目')
    return
  }
  for (const q of toAdd) {
    picked.value.push({
      question_id: q.question_id,
      question_sort: picked.value.length + 1,
      question_score: q.question_score ?? 0,
      question_content: q.question_content,
      type_id: q.type_id,
      difficulty_id: q.difficulty_id,
      chapter_id: q.chapter_id,
    })
  }
  renumber()
  showPaperDrawer.value = true
}

function removePicked(index) {
  picked.value.splice(index, 1)
  renumber()
}

function clearPicked() {
  picked.value = []
}

function onDragStart(index) {
  dragIndex.value = index
}

function onDrop(index) {
  const from = dragIndex.value
  if (from < 0 || from === index) return
  const arr = picked.value.slice()
  const [moved] = arr.splice(from, 1)
  arr.splice(index, 0, moved)
  picked.value = arr
  dragIndex.value = -1
  renumber()
}

function validatePicked() {
  if (!filters.subject_id) {
    ElMessage.error('请先选择科目')
    return false
  }
  if (picked.value.length === 0) {
    ElMessage.error('请先选择题目加入试卷')
    return false
  }
  const sorts = picked.value.map((x) => Number(x.question_sort))
  if (sorts.some((x) => !Number.isInteger(x) || x < 1)) {
    ElMessage.error('题号必须是 >= 1 的整数')
    return false
  }
  const set = new Set(sorts)
  if (set.size !== sorts.length) {
    ElMessage.error('题号存在重复，请调整后再保存')
    return false
  }
  return true
}

async function savePaper() {
  if (!validatePicked()) return
  loading.value = true
  error.value = ''
  saved.value = null
  try {
    const items = picked.value.map((x) => ({
      question_id: x.question_id,
      question_sort: x.question_sort,
      question_score: x.question_score,
    }))
    const resp = await http.post('/papers/manual', {
      paper_name: paper.paper_name,
      paper_desc: paper.paper_desc,
      subject_id: filters.subject_id,
      exam_duration: paper.exam_duration,
      is_closed_book: paper.is_closed_book,
      creator: paper.creator,
      items,
    })
    saved.value = resp.data
    ElMessage.success(`已保存试卷 paper_id=${resp.data.paper_id}`)
  } catch (e) {
    error.value = e?.message || '保存失败'
  } finally {
    loading.value = false
  }
}

function getTagsContainer(host) {
  if (!host) return null
  return host.querySelector('.el-select__tags') || host.querySelector('.el-select__selection') || host.querySelector('.el-select__wrapper')
}

async function recalcMaxTags(selectRef, maxRef, selectedLength) {
  if (!selectRef.value) return
  const targetLength = Math.max(1, selectedLength || 0)
  if (maxRef.value !== targetLength) {
    maxRef.value = targetLength
    await nextTick()
  }
  const host = selectRef.value?.$el || selectRef.value
  const tagsContainer = getTagsContainer(host)
  if (!tagsContainer) return
  const tags = Array.from(tagsContainer.querySelectorAll('.el-tag'))
  if (tags.length === 0) return
  const firstTop = tags[0].getBoundingClientRect().top
  const fitCount = tags.filter(tag => Math.abs(tag.getBoundingClientRect().top - firstTop) < 1).length
  const nextMax = Math.max(1, Math.min(fitCount, tags.length))
  if (maxRef.value !== nextMax) {
    maxRef.value = nextMax
  }
}

function scheduleChapterRecalc() {
  if (chapterRecalcRaf) cancelAnimationFrame(chapterRecalcRaf)
  chapterRecalcRaf = requestAnimationFrame(() => {
    recalcMaxTags(chapterSelectRef, maxChapterTags, filters.chapter_ids.length)
  })
}

function scheduleTypeRecalc() {
  if (typeRecalcRaf) cancelAnimationFrame(typeRecalcRaf)
  typeRecalcRaf = requestAnimationFrame(() => {
    recalcMaxTags(typeSelectRef, maxTypeTags, filters.type_ids.length)
  })
}

function scheduleDifficultyRecalc() {
  if (difficultyRecalcRaf) cancelAnimationFrame(difficultyRecalcRaf)
  difficultyRecalcRaf = requestAnimationFrame(() => {
    recalcMaxTags(difficultySelectRef, maxDifficultyTags, filters.difficulty_ids.length)
  })
}


// AI Generation
const aiDialog = reactive({
  visible: false,
  subject_id: null,
  textbook_id: null,
  description: '',
})

function openAiDialog() {
  aiDialog.visible = true
  aiDialog.subject_id = filters.subject_id || null
  aiDialog.textbook_id = filters.textbook_id || null
  aiDialog.description = ''
  loadAiDialogTextbooks()
}

const aiDialogTextbooks = ref([])
async function loadAiDialogTextbooks() {
  const resp = await http.get('/textbooks', {
    params: aiDialog.subject_id ? { subject_id: aiDialog.subject_id } : {},
  })
  aiDialogTextbooks.value = resp.data.items || []
}

async function startAiGeneration() {
  if (!aiDialog.subject_id || !aiDialog.textbook_id || !aiDialog.description) {
    ElMessage.error('请填写完整信息')
    return
  }
  
  aiDialog.visible = false
  loading.value = true
  try {
    const user = getUser()
    const resp = await http.post('/ai/generate-smart-paper', {
      subject_id: aiDialog.subject_id,
      textbook_id: aiDialog.textbook_id,
      description: aiDialog.description,
      create_user: user ? user.name : 'user'
    })
    startStream(resp.data.job_id)
  } catch (e) {
    ElMessage.error(e?.message || '请求失败')
    loading.value = false
  }
}

// Stream
const stream = reactive({
  visible: false,
  job_id: null,
  status: 'idle',
  lines: [],
  output: '',
  progress: 0,
  currentStage: '',
})
const streamBodyRef = ref(null)
let typingTimer = null
let pollingTimer = null
let outputQueue = ''

function pushLine(text) {
  stream.lines.push(text)
  if (stream.lines.length > 2000) stream.lines.splice(0, stream.lines.length - 2000)
  requestAnimationFrame(() => {
      if (streamBodyRef.value) streamBodyRef.value.scrollTop = streamBodyRef.value.scrollHeight
  })
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
      const chunk = outputQueue.slice(0, 5)
      outputQueue = outputQueue.slice(5)
      stream.output += chunk
      requestAnimationFrame(() => {
          if (streamBodyRef.value) streamBodyRef.value.scrollTop = streamBodyRef.value.scrollHeight
      })
    }, 16)
  }
}

function stopStream() {
  if (pollingTimer) {
    clearInterval(pollingTimer)
    pollingTimer = null
  }
  stopTyping()
  loading.value = false
}

function startStream(jobId) {
  stopStream()
  stream.visible = true
  stream.job_id = jobId
  stream.status = 'running'
  stream.lines = []
  stream.output = ''
  stream.progress = 0
  stream.currentStage = '准备中...'
  
  outputQueue = ''
  pushLine(`任务已创建：${jobId}`)

  let lastEventId = 0
  
  pollingTimer = setInterval(async () => {
    try {
      const resp = await http.get(`/ai/jobs/${jobId}`)
      const job = resp.data.job
      if (!job) return
      
      const events = job.events || []
      const newEvents = events.filter(e => (e.id || 0) > lastEventId)
      newEvents.sort((a, b) => (a.id || 0) - (b.id || 0))
      
      for (const ev of newEvents) {
        lastEventId = ev.id || lastEventId
        
        if (ev.type === 'ai_delta') {
          const t = ev?.data?.text || ''
          stream.currentStage = 'AI思考中...'
          enqueueOutput(t)
          if (stream.progress < 80) {
             stream.progress = Math.min(80, stream.progress + 0.5)
          }
        } else {
          const ts = ev.ts ? `【${ev.ts}】` : ''
          const msg = ev.message ? ` ${ev.message}` : ''
          pushLine(`${ts}${ev.type}${msg}`)
          
          if (ev.message) stream.currentStage = ev.message

          // Progress mapping
          switch (ev.type) {
            case 'job_start': stream.progress = 5; break;
            case 'meta_fetch': stream.progress = 10; break;
            case 'ai_analyze': stream.progress = 20; break;
            case 'ai_thinking': stream.progress = 30; break;
            case 'ai_parsed': stream.progress = 85; break;
            case 'db_query': stream.progress = 90; break;
          }
          
          if (ev.type === 'job_done') {
            stream.status = 'done'
            stream.currentStage = '完成'
            stream.progress = 100
            stopStream()
            
            const result = ev.data
            if (result && result.questions) {
                applyAiResult(result)
            }
            setTimeout(() => { stream.visible = false }, 2000)
          } else if (ev.type === 'job_error') {
            stream.status = 'error'
            stream.currentStage = '出错'
            stopStream()
          }
        }
      }
    } catch (e) {
      console.error(e)
    }
  }, 1000)
}

function applyAiResult(result) {
    if (result.paper_name) paper.paper_name = result.paper_name
    if (result.paper_desc) paper.paper_desc = result.paper_desc
    if (result.exam_duration) paper.exam_duration = result.exam_duration
    if (result.is_closed_book !== undefined) paper.is_closed_book = result.is_closed_book
    
    // Sync filters
    if (aiDialog.subject_id) {
        filters.subject_id = aiDialog.subject_id
        // Trigger load
        loadTextbooks()
        // If textbook also selected
        if (aiDialog.textbook_id) {
            filters.textbook_id = aiDialog.textbook_id
            loadChapters()
        }
    }

    picked.value = []
    
    const questions = result.questions || []
    if (questions.length === 0) {
        ElMessage.warning('未找到符合条件的题目')
        return
    }
    
    for (const q of questions) {
        picked.value.push({
          question_id: q.question_id,
          question_sort: picked.value.length + 1,
          question_score: q.question_score ?? 2,
          question_content: q.question_content,
          question_answer: q.question_answer,
          question_analysis: q.question_analysis,
          type_id: q.type_id,
          difficulty_id: q.difficulty_id,
          chapter_id: q.chapter_id,
        })
    }
    
    renumber()
    showPaperDrawer.value = true
    ElMessage.success(`AI组卷完成，共生成 ${questions.length} 题`)
}

onMounted(async () => {
  await loadDicts()
  await loadTextbooks()
  await search()
  await nextTick()
  scheduleChapterRecalc()
  scheduleTypeRecalc()
  scheduleDifficultyRecalc()

  if (window.ResizeObserver) {
    const chapterHost = chapterSelectRef.value?.$el || chapterSelectRef.value
    const typeHost = typeSelectRef.value?.$el || typeSelectRef.value
    const difficultyHost = difficultySelectRef.value?.$el || difficultySelectRef.value
    if (chapterHost) {
      chapterResizeObserver = new ResizeObserver(() => scheduleChapterRecalc())
      chapterResizeObserver.observe(chapterHost)
    }
    if (typeHost) {
      typeResizeObserver = new ResizeObserver(() => scheduleTypeRecalc())
      typeResizeObserver.observe(typeHost)
    }
    if (difficultyHost) {
      difficultyResizeObserver = new ResizeObserver(() => scheduleDifficultyRecalc())
      difficultyResizeObserver.observe(difficultyHost)
    }
  }
})

onUnmounted(() => {
  if (chapterResizeObserver) chapterResizeObserver.disconnect()
  if (typeResizeObserver) typeResizeObserver.disconnect()
  if (difficultyResizeObserver) difficultyResizeObserver.disconnect()
  if (chapterRecalcRaf) cancelAnimationFrame(chapterRecalcRaf)
  if (typeRecalcRaf) cancelAnimationFrame(typeRecalcRaf)
  if (difficultyRecalcRaf) cancelAnimationFrame(difficultyRecalcRaf)
})

watch(() => filters.chapter_ids.length, () => scheduleChapterRecalc(), { flush: 'post' })
watch(() => filters.type_ids.length, () => scheduleTypeRecalc(), { flush: 'post' })
watch(() => filters.difficulty_ids.length, () => scheduleDifficultyRecalc(), { flush: 'post' })
</script>

<template>
  <div class="page">
    <el-alert v-if="error" :title="error" type="error" show-icon />

    <el-card>
          <template #header>
            <div class="header">
              <div>题目筛选</div>
              <div class="actions">
                <el-button @click="openAiDialog" :icon="VideoPlay" type="warning" plain>AI智能组卷</el-button>
                <el-button :loading="loading" @click="search" :icon="Search">查询</el-button>
                <el-button type="primary" :loading="loading" @click="addSelected" :icon="Plus">加入试卷</el-button>
                <el-button @click="showPaperDrawer = true">已选 ({{ picked.length }})</el-button>
              </div>
            </div>
          </template>

          <div class="filters">
            <el-input v-model="filters.q" placeholder="关键词（题干/解析）" style="width: 220px" clearable @keyup.enter="search" :prefix-icon="Search" />

            <el-select
              v-model="filters.subject_id"
              clearable
              placeholder="科目"
              style="width: 160px"
              @change="
                async () => {
                  filters.textbook_id = null
                  filters.chapter_ids = []
                  await loadTextbooks()
                  await loadChapters()
                  await search()
                }
              "
            >
              <el-option v-for="s in subjects" :key="s.subject_id" :label="s.subject_name" :value="s.subject_id" />
            </el-select>

            <el-select
              v-model="filters.textbook_id"
              clearable
              placeholder="教材"
              style="width: 240px"
              @change="
                async () => {
                  filters.chapter_ids = []
                  await loadChapters()
                  await search()
                }
              "
            >
              <el-option v-for="t in textbooks" :key="t.textbook_id" :label="t.textbook_name + (t.author ? ' (' + t.author + ')' : '')" :value="t.textbook_id" />
            </el-select>

            <el-select v-model="filters.publisher" clearable placeholder="出版社" style="width: 180px" @change="search">
              <el-option v-for="p in publisherOptions" :key="p" :label="p" :value="p" />
            </el-select>

            <el-tree-select
              ref="chapterSelectRef"
              v-model="filters.chapter_ids"
              :data="chapterTree"
              :props="{ label: 'chapter_name', children: 'children', value: 'chapter_id' }"
              node-key="chapter_id"
              clearable
              multiple
              show-checkbox
              collapse-tags
              :max-collapse-tags="maxChapterTags"
              collapse-tags-tooltip
              placeholder="章节"
              style="width: 240px"
              @change="search"
            />

            <el-select ref="typeSelectRef" v-model="filters.type_ids" clearable multiple collapse-tags :max-collapse-tags="maxTypeTags" collapse-tags-tooltip placeholder="题型" style="width: 200px" @change="search">
              <el-option v-for="t in types" :key="t.type_id" :label="t.type_name" :value="t.type_id" />
            </el-select>

            <el-select
              ref="difficultySelectRef"
               v-model="filters.difficulty_ids"
               clearable
               multiple
               collapse-tags
               :max-collapse-tags="maxDifficultyTags"
               collapse-tags-tooltip
               placeholder="难度"
               style="width: 200px"
               @change="search"
             >
              <el-option v-for="d in difficulties" :key="d.difficulty_id" :label="d.difficulty_name" :value="d.difficulty_id" />
            </el-select>
          </div>

          <el-table :data="available.items" height="560" @selection-change="onAvailableSelectionChange">
            <el-table-column type="selection" width="48" />
            <el-table-column prop="question_id" label="ID" width="90" />
            <el-table-column label="章节" width="150" show-overflow-tooltip>
              <template #default="{ row }">
                {{ row.chapter_name || row.chapter_id }}
              </template>
            </el-table-column>
            <el-table-column label="题型" width="110">
              <template #default="{ row }">
                {{ typeName(row.type_id) }}
              </template>
            </el-table-column>
            <el-table-column label="难度" width="110">
              <template #default="{ row }">
                {{ difficultyName(row.difficulty_id) }}
              </template>
            </el-table-column>
            <el-table-column label="题干" min-width="360">
              <template #default="{ row }">
                <div class="contentCell" @click="openDetail(row)" title="点击查看详情">{{ row.question_content }}</div>
              </template>
            </el-table-column>
          </el-table>

          <div class="pager">
            <el-pagination
              v-model:current-page="filters.page"
              v-model:page-size="filters.page_size"
              :total="available.total"
              :page-sizes="[10, 20, 50, 100]"
              layout="total, sizes, prev, pager, next"
              @size-change="
                () => {
                  filters.page = 1
                  search()
                }
              "
              @current-change="search"
            />
          </div>
      </el-card>

    <el-dialog v-model="detailDialog.visible" title="题目详情" width="600px">
      <div v-if="detailDialog.item">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="题干">
            <div style="white-space: pre-wrap">{{ detailDialog.item.question_content }}</div>
          </el-descriptions-item>
          <el-descriptions-item label="答案">
            <div style="white-space: pre-wrap">{{ detailDialog.item.question_answer }}</div>
          </el-descriptions-item>
          <el-descriptions-item label="解析">
            <div style="white-space: pre-wrap">{{ detailDialog.item.question_analysis }}</div>
          </el-descriptions-item>
        </el-descriptions>
      </div>
      <template #footer>
        <el-button @click="detailDialog.visible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="showPaperDrawer" :size="isDrawerFullscreen ? '100%' : '500px'" direction="rtl">
      <template #header>
        <div class="drawer-header-custom">
          <span class="drawer-title">已选题目与配置</span>
          <el-button link @click="isDrawerFullscreen = !isDrawerFullscreen" :icon="FullScreen" title="切换全屏" class="fullscreen-btn" />
        </div>
      </template>
      <div class="drawer-inner">
        <div class="drawer-top-actions">
           <h3>已选题目（{{ picked.length }}）</h3>
           <div class="actions">
              <el-button @click="renumber" :icon="Refresh" size="small">重新编号</el-button>
              <el-button type="danger" @click="clearPicked" :icon="Delete" size="small">清空</el-button>
           </div>
        </div>

          <el-form label-width="80px" class="paper-form">
            <el-form-item label="试卷名">
              <el-input v-model="paper.paper_name" />
            </el-form-item>
            <el-form-item label="时长">
              <el-input-number v-model="paper.exam_duration" :min="1" :max="600" style="width: 100%" />
            </el-form-item>
            <el-form-item label="闭卷">
              <el-switch v-model="paper.is_closed_book" />
            </el-form-item>
            <el-form-item label="说明">
              <el-input v-model="paper.paper_desc" type="textarea" :rows="2" />
            </el-form-item>
          </el-form>

          <div class="total">总分：{{ pickedTotalScore }}</div>
          <div v-if="saved" class="hint">已保存：paper_id={{ saved.paper_id }}，共{{ saved.question_count }}题，总分{{ saved.total_score }}</div>

          <div class="picked-list">
            <div v-if="picked.length === 0" class="empty">从左侧筛选后勾选题目加入</div>

            <div
              v-for="(it, index) in picked"
              :key="it.question_id"
              class="picked-row"
              draggable="true"
              @dragstart="onDragStart(index)"
              @dragover.prevent
              @drop="onDrop(index)"
            >
              <div class="row-left">
                <div class="drag-handle">≡</div>
              </div>
              <div class="row-main">
                <div class="info-header">
                  <span class="tag">{{ typeName(it.type_id) }}</span>
                  <span class="tag">{{ difficultyName(it.difficulty_id) }}</span>
                  <span class="qid">#{{ it.question_id }}</span>
                </div>
                <div class="info-body">
                  <div class="q-field">
                    <span class="label">【题干】</span>
                    <span class="text">{{ it.question_content }}</span>
                  </div>
                  <div class="q-field" v-if="it.question_answer">
                    <span class="label">【答案】</span>
                    <span class="text">{{ it.question_answer }}</span>
                  </div>
                  <div class="q-field" v-if="it.question_analysis">
                    <span class="label">【解析】</span>
                    <span class="text">{{ it.question_analysis }}</span>
                  </div>
                </div>
              </div>
              <div class="row-right">
                <div class="control-item">
                  <span class="control-label">序号</span>
                  <el-input-number v-model="it.question_sort" :min="1" :max="9999" size="small" style="width: 100%" />
                </div>
                <div class="control-item">
                  <span class="control-label">分值</span>
                  <el-input-number v-model="it.question_score" :min="0" :step="0.5" size="small" style="width: 100%" />
                </div>
                <div class="control-item">
                  <el-button link type="danger" @click="removePicked(index)" :icon="Delete">移除</el-button>
                </div>
              </div>
            </div>
          </div>
      </div>
      <template #footer>
        <div class="drawer-footer">
           <div class="footer-left">
             <!-- Fullscreen button moved to header -->
           </div>
           <div class="footer-right">
             <el-button @click="showPaperDrawer = false">继续选择</el-button>
             <el-button type="primary" :loading="loading" @click="savePaper" :icon="Check">保存试卷</el-button>
           </div>
        </div>
      </template>
    </el-drawer>
    <el-dialog v-model="aiDialog.visible" title="AI智能组卷" width="500px">
      <el-form label-width="80px">
        <el-form-item label="科目">
          <el-select
            v-model="aiDialog.subject_id"
            placeholder="请选择科目"
            style="width: 100%"
            :disabled="!!filters.subject_id"
            @change="
              async () => {
                aiDialog.textbook_id = null
                await loadAiDialogTextbooks()
              }
            "
          >
            <el-option v-for="s in subjects" :key="s.subject_id" :label="s.subject_name" :value="s.subject_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="教材">
          <el-select
            v-model="aiDialog.textbook_id"
            placeholder="请选择教材"
            style="width: 100%"
            :disabled="!aiDialog.subject_id || !!filters.textbook_id"
          >
            <el-option v-for="t in aiDialogTextbooks" :key="t.textbook_id" :label="t.textbook_name + (t.author ? '-' + t.author : '')" :value="t.textbook_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="需求描述">
            <el-input 
                v-model="aiDialog.description" 
                type="textarea" 
                :rows="6" 
                placeholder="请描述您的组卷需求，例如：&#10;生成一份高等数学期末试卷，包含10道单选题（每题2分），5道填空题（每题4分），2道计算题（每题10分）。难度中等偏难，重点考察微积分和极限。" 
            />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="aiDialog.visible = false">取消</el-button>
        <el-button type="primary" @click="startAiGeneration" :loading="loading">开始生成</el-button>
      </template>
    </el-dialog>

    <div v-if="stream.visible" class="streamPanel">
      <div class="streamHeader">
        <div class="streamTitle">
          <span>AI组卷过程</span>
          <span class="streamMeta">ID: {{ stream.job_id }}（{{ stream.status }}）</span>
        </div>
        <div class="streamActions">
          <el-button size="small" @click="stream.output = ''; stream.lines = []" :icon="Delete">清空</el-button>
          <el-button size="small" @click="stream.visible = false" :icon="Close">关闭</el-button>
        </div>
      </div>

      <div class="streamProgress">
        <div class="progress-info">
          <span class="stage-text">{{ stream.currentStage }}</span>
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
  gap: 10px;
}

.actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.paper-form {
  margin-bottom: 10px;
}

.total {
  margin-bottom: 8px;
  font-weight: 600;
}

.hint {
  margin-bottom: 10px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.contentCell {
  max-height: 80px;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  white-space: pre-wrap;
  cursor: pointer;
}
.contentCell:hover {
  color: var(--el-color-primary);
}

.picked-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  /* max-height removed to allow full height display */
  border-top: 1px solid var(--el-border-color);
  padding-top: 10px;
}

.empty {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.picked-row {
  display: flex;
  gap: 10px;
  padding: 12px;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  background-color: var(--el-bg-color);
  align-items: stretch;
}

.row-left {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  flex-shrink: 0;
  border-right: 1px solid var(--el-border-color-lighter);
  margin-right: 4px;
}

.drag-handle {
  cursor: grab;
  color: var(--el-text-color-secondary);
  font-size: 18px;
  user-select: none;
}

.row-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.info-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.qid {
  font-weight: 600;
  color: var(--el-text-color-regular);
}

.tag {
  font-size: 12px;
  padding: 2px 6px;
  background: var(--el-fill-color-light);
  border-radius: 4px;
  color: var(--el-text-color-secondary);
}

.info-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.q-field {
  font-size: 13px;
  line-height: 1.5;
  color: var(--el-text-color-regular);
  word-break: break-all;
}

.label {
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-right: 4px;
}

.text {
  white-space: pre-wrap;
}

.row-right {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100px;
  flex-shrink: 0;
  border-left: 1px solid var(--el-border-color-lighter);
  padding-left: 10px;
  justify-content: center;
}

.control-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  align-items: flex-end;
}

.control-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.drawer-inner {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow-y: auto;
}

.drawer-top-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.drawer-top-actions h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.drawer-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.footer-left {
  display: flex;
  align-items: center;
}

.footer-right {
  display: flex;
  gap: 10px;
}

.drawer-header-custom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.drawer-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary);
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
</style>
