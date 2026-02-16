<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch, nextTick, h } from 'vue'
import { useMessage, useDialog, NButton, NTag } from 'naive-ui'
import { SearchOutline, AddOutline, RefreshOutline, TrashOutline, CheckmarkOutline, ExpandOutline, PlayOutline, CloseOutline, FunnelOutline } from '@vicons/ionicons5'
import { http } from '../api/http'
import { getToken, getUser } from '../auth'

const message = useMessage()
const dialogApi = useDialog()
const loading = ref(false)
const error = ref('')
const saved = ref(null)

const subjects = ref([])
const textbooks = ref([])
const chapterTree = ref([])
const types = ref([])
const difficulties = ref([])
const selectedMainChapters = ref([]) // 选中的大章节ID列表

const filters = reactive({
  q: '',
  subject_id: null,
  textbook_id: null,
  publisher: null,
  chapter_ids: [],
  type_ids: [],
  difficulty_ids: [],
  review_status: 1,
  page: 1,
  page_size: 20,
})

const available = reactive({ items: [], total: 0 })
const checkedRowKeys = ref([])

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

const detailDialog = reactive({ visible: false, item: null })

function openDetail(row) {
  detailDialog.item = row
  detailDialog.visible = true
}

const publisherOptions = computed(() => {
  const set = new Set()
  for (const t of textbooks.value) {
    if (t.publisher) set.add(t.publisher)
  }
  return Array.from(set).map(p => ({ label: p, value: p }))
})

const pickedTotalScore = computed(() => picked.value.reduce((sum, it) => sum + Number(it.question_score || 0), 0))

function typeName(type_id) {
  const t = types.value.find(x => x.type_id === type_id)
  return t ? t.type_name : String(type_id ?? '')
}

function difficultyName(difficulty_id) {
  const d = difficulties.value.find(x => x.difficulty_id === difficulty_id)
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
  if (!filters.subject_id) {
    textbooks.value = []
    chapterTree.value = []
    return
  }
  const resp = await http.get('/textbooks', {
    params: { subject_id: filters.subject_id },
  })
  textbooks.value = resp.data.items || []
  // 切换科目时清空章节
  chapterTree.value = []
}

async function loadChapters() {
  if (!filters.textbook_id) { chapterTree.value = []; return }
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

function renumber() {
  picked.value.forEach((it, idx) => { it.question_sort = idx + 1 })
}

// 将章节树扁平化为一维数组，带层级信息
function flattenChapters(tree, level = 1) {
  const result = []
  for (const node of tree) {
    result.push({ ...node, level })
    if (node.children && node.children.length > 0) {
      result.push(...flattenChapters(node.children, level + 1))
    }
  }
  return result
}

// 计算当前可见的小章节（按大章节分组）
const visibleSubChapterGroups = computed(() => {
  const groups = []
  for (const chapter of chapterTree.value) {
    if (selectedMainChapters.value.includes(chapter.chapter_id)) {
      if (chapter.children && chapter.children.length > 0) {
        groups.push({
          parent: chapter,
          children: chapter.children
        })
      }
    }
  }
  return groups
})

// 切换大章节选择
function toggleMainChapter(chapter) {
  const idx = selectedMainChapters.value.indexOf(chapter.chapter_id)
  if (idx >= 0) {
    // 取消选择大章节，同时移除其下所有子章节的选中状态
    selectedMainChapters.value.splice(idx, 1)
    if (chapter.children && chapter.children.length > 0) {
      const childIds = chapter.children.map(c => c.chapter_id)
      filters.chapter_ids = filters.chapter_ids.filter(id => !childIds.includes(id))
    }
  } else {
    // 选择大章节，同时默认选中所有子章节
    selectedMainChapters.value.push(chapter.chapter_id)
    if (chapter.children && chapter.children.length > 0) {
      for (const child of chapter.children) {
        if (!filters.chapter_ids.includes(child.chapter_id)) {
          filters.chapter_ids.push(child.chapter_id)
        }
      }
    }
  }
  search()
}

// 切换小章节选择
function toggleSubChapter(chapterId) {
  const idx = filters.chapter_ids.indexOf(chapterId)
  if (idx >= 0) {
    filters.chapter_ids.splice(idx, 1)
  } else {
    filters.chapter_ids.push(chapterId)
  }
  search()
}

// 切换题型选择
function toggleType(typeId) {
  const idx = filters.type_ids.indexOf(typeId)
  if (idx >= 0) {
    filters.type_ids.splice(idx, 1)
  } else {
    filters.type_ids.push(typeId)
  }
  search()
}

// 切换难度选择
function toggleDifficulty(difficultyId) {
  const idx = filters.difficulty_ids.indexOf(difficultyId)
  if (idx >= 0) {
    filters.difficulty_ids.splice(idx, 1)
  } else {
    filters.difficulty_ids.push(difficultyId)
  }
  search()
}

// 获取难度对应的颜色类名
function getDifficultyClass(difficultyId, difficultyName) {
  const selected = filters.difficulty_ids.includes(difficultyId)
  const name = difficultyName?.toLowerCase() || ''
  if (name.includes('简单') || name.includes('easy')) {
    return selected ? 'difficulty-easy-selected' : 'difficulty-easy'
  } else if (name.includes('中等') || name.includes('medium') || name.includes('普通')) {
    return selected ? 'difficulty-medium-selected' : 'difficulty-medium'
  } else if (name.includes('困难') || name.includes('hard') || name.includes('难')) {
    return selected ? 'difficulty-hard-selected' : 'difficulty-hard'
  }
  return selected ? 'difficulty-default-selected' : ''
}

function addSelected() {
  const existing = new Set(picked.value.map(x => x.question_id))
  const toAdd = available.items.filter(x => checkedRowKeys.value.includes(x.question_id) && !existing.has(x.question_id))
  if (toAdd.length === 0) { message.warning('没有可加入的题目'); return }
  for (const q of toAdd) {
    picked.value.push({
      question_id: q.question_id,
      question_sort: picked.value.length + 1,
      question_score: q.question_score ?? 0,
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
}

function removePicked(index) {
  picked.value.splice(index, 1)
  renumber()
}

function clearPicked() {
  picked.value = []
}

function onDragStart(index) { dragIndex.value = index }

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
  if (!filters.subject_id) { message.error('请先选择科目'); return false }
  if (picked.value.length === 0) { message.error('请先选择题目加入试卷'); return false }
  const sorts = picked.value.map(x => Number(x.question_sort))
  if (sorts.some(x => !Number.isInteger(x) || x < 1)) { message.error('题号必须是 >= 1 的整数'); return false }
  const set = new Set(sorts)
  if (set.size !== sorts.length) { message.error('题号存在重复，请调整后再保存'); return false }
  return true
}

async function savePaper() {
  if (!validatePicked()) return
  loading.value = true
  error.value = ''
  saved.value = null
  try {
    const items = picked.value.map(x => ({
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
    message.success(`已保存试卷 paper_id=${resp.data.paper_id}`)
  } catch (e) {
    error.value = e?.message || '保存失败'
  } finally {
    loading.value = false
  }
}

// AI Generation
const aiDialog = reactive({ visible: false, subject_id: null, textbook_id: null, description: '' })
const aiDialogTextbooks = ref([])

function openAiDialog() {
  aiDialog.visible = true
  aiDialog.subject_id = filters.subject_id || null
  aiDialog.textbook_id = filters.textbook_id || null
  aiDialog.description = ''
  loadAiDialogTextbooks()
}

async function loadAiDialogTextbooks() {
  const resp = await http.get('/textbooks', {
    params: aiDialog.subject_id ? { subject_id: aiDialog.subject_id } : {},
  })
  aiDialogTextbooks.value = resp.data.items || []
}

async function startAiGeneration() {
  if (!aiDialog.subject_id || !aiDialog.textbook_id || !aiDialog.description) {
    message.error('请填写完整信息')
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
    message.error(e?.message || '请求失败')
    loading.value = false
  }
}

// Stream
const stream = reactive({ visible: false, job_id: null, status: 'idle', lines: [], output: '', progress: 0, currentStage: '' })
const streamBodyRef = ref(null)
let typingTimer = null
let pollingTimer = null
let outputQueue = ''

function pushLine(text) {
  stream.lines.push(text)
  if (stream.lines.length > 2000) stream.lines.splice(0, stream.lines.length - 2000)
  requestAnimationFrame(() => { if (streamBodyRef.value) streamBodyRef.value.scrollTop = streamBodyRef.value.scrollHeight })
}

function stopTyping() {
  if (typingTimer) { clearInterval(typingTimer); typingTimer = null }
  outputQueue = ''
}

function enqueueOutput(text) {
  if (!text) return
  outputQueue += text
  if (!typingTimer) {
    typingTimer = setInterval(() => {
      if (!outputQueue) { clearInterval(typingTimer); typingTimer = null; return }
      const chunk = outputQueue.slice(0, 5)
      outputQueue = outputQueue.slice(5)
      stream.output += chunk
      requestAnimationFrame(() => { if (streamBodyRef.value) streamBodyRef.value.scrollTop = streamBodyRef.value.scrollHeight })
    }, 16)
  }
}

function stopStream() {
  if (pollingTimer) { clearInterval(pollingTimer); pollingTimer = null }
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
          stream.currentStage = 'AI思考中...'
          enqueueOutput(ev?.data?.text || '')
          if (stream.progress < 80) stream.progress = Math.min(80, stream.progress + 0.5)
        } else {
          const ts = ev.ts ? `【${ev.ts}】` : ''
          const msg = ev.message ? ` ${ev.message}` : ''
          pushLine(`${ts}${ev.type}${msg}`)
          if (ev.message) stream.currentStage = ev.message
          switch (ev.type) {
            case 'job_start': stream.progress = 5; break
            case 'meta_fetch': stream.progress = 10; break
            case 'ai_analyze': stream.progress = 20; break
            case 'ai_thinking': stream.progress = 30; break
            case 'ai_parsed': stream.progress = 85; break
            case 'db_query': stream.progress = 90; break
          }
          if (ev.type === 'job_done') {
            stream.status = 'done'; stream.currentStage = '完成'; stream.progress = 100
            stopStream()
            if (ev.data?.questions) applyAiResult(ev.data)
            setTimeout(() => { stream.visible = false }, 2000)
          } else if (ev.type === 'job_error') {
            stream.status = 'error'; stream.currentStage = '出错'; stopStream()
          }
        }
      }
    } catch (e) { console.error(e) }
  }, 1000)
}

function applyAiResult(result) {
  if (result.paper_name) paper.paper_name = result.paper_name
  if (result.paper_desc) paper.paper_desc = result.paper_desc
  if (result.exam_duration) paper.exam_duration = result.exam_duration
  if (result.is_closed_book !== undefined) paper.is_closed_book = result.is_closed_book
  if (aiDialog.subject_id) {
    filters.subject_id = aiDialog.subject_id
    loadTextbooks()
    if (aiDialog.textbook_id) { filters.textbook_id = aiDialog.textbook_id; loadChapters() }
  }
  picked.value = []
  const questions = result.questions || []
  if (questions.length === 0) { message.warning('未找到符合条件的题目'); return }
  for (const q of questions) {
    picked.value.push({
      question_id: q.question_id, question_sort: picked.value.length + 1, question_score: q.question_score ?? 2,
      question_content: q.question_content, question_answer: q.question_answer, question_analysis: q.question_analysis,
      type_id: q.type_id, difficulty_id: q.difficulty_id, chapter_id: q.chapter_id,
    })
  }
  renumber()
  showPaperDrawer.value = true
  message.success(`AI组卷完成，共生成 ${questions.length} 题`)
}

onMounted(async () => {
  await loadDicts()
  await loadTextbooks()
  await search()
})

onUnmounted(() => { stopStream() })

// Computed options
const subjectOptions = computed(() => subjects.value.map(s => ({ label: s.subject_name, value: s.subject_id })))
const textbookOptions = computed(() => textbooks.value.map(t => ({ label: t.textbook_name + (t.author ? '-' + t.author : ''), value: t.textbook_id })))
const typeOptions = computed(() => types.value.map(t => ({ label: t.type_name, value: t.type_id })))
const difficultyOptions = computed(() => difficulties.value.map(d => ({ label: d.difficulty_name, value: d.difficulty_id })))
const aiDialogTextbookOptions = computed(() => aiDialogTextbooks.value.map(t => ({ label: t.textbook_name + (t.author ? '-' + t.author : ''), value: t.textbook_id })))

function treeToOptions(tree) {
  return tree.map(node => ({
    label: node.chapter_name, value: node.chapter_id,
    children: node.children && node.children.length > 0 ? treeToOptions(node.children) : undefined
  }))
}
const chapterCascaderOptions = computed(() => treeToOptions(chapterTree.value))

const tableColumns = [
  { type: 'selection' },
  { title: 'ID', key: 'question_id', width: 90 },
  { title: '章节', key: 'chapter_name', width: 150, ellipsis: { tooltip: true } },
  { title: '题型', key: 'type_id', width: 110, render: row => typeName(row.type_id) },
  { title: '难度', key: 'difficulty_id', width: 110, render: row => difficultyName(row.difficulty_id) },
  {
    title: '题干', key: 'question_content', ellipsis: { tooltip: true },
    render: row => h('div', { style: 'cursor: pointer', onClick: () => openDetail(row) }, row.question_content?.substring(0, 80))
  }
]

function handlePageChange(page) { filters.page = page; search() }
function handlePageSizeChange(pageSize) { filters.page_size = pageSize; filters.page = 1; search() }
</script>

<template>
  <div class="page">
    <n-alert v-if="error" type="error" :title="error" />
    <n-card>
      <template #header>
        <div class="header">
          <div>题目筛选</div>
          <div class="actions">
            <n-button @click="openAiDialog" type="warning">
              <template #icon><n-icon><PlayOutline /></n-icon></template>
              AI智能组卷
            </n-button>
            <n-button :loading="loading" @click="search">
              <template #icon><n-icon><SearchOutline /></n-icon></template>
              查询
            </n-button>
            <n-button type="primary" :loading="loading" @click="addSelected">
              <template #icon><n-icon><AddOutline /></n-icon></template>
              加入试卷
            </n-button>
            <n-button @click="showPaperDrawer = true">已选 ({{ picked.length }})</n-button>
          </div>
        </div>
      </template>
      <div class="filter-section">
        <div class="filter-section-header filter-section-toggle" @click="filterCollapsed = !filterCollapsed">
          <n-icon size="16" color="#64748b"><FunnelOutline /></n-icon>
          <span>条件筛选</span>
          <n-icon size="16" style="margin-left: 4px;transition:transform 0.2s;" :style="{transform: filterCollapsed ? 'rotate(-90deg)' : 'rotate(0deg)'}"><ExpandOutline /></n-icon>
        </div>
        <template v-if="!filterCollapsed">
          <!-- 第一行：基础筛选 -->
          <div class="filter-row">
            <div class="filter-label">关键词</div>
            <div class="filter-content">
              <n-input v-model:value="filters.q" placeholder="题干/解析" style="width: 200px" clearable @keyup.enter="search" />
            </div>
          </div>

          <div class="filter-row">
            <div class="filter-label">科目</div>
            <div class="filter-content filter-tags">
              <n-tag
                v-for="s in subjects"
                :key="s.subject_id"
                :bordered="false"
                :class="['filter-tag', filters.subject_id === s.subject_id ? 'tag-selected' : '']"
                @click="async () => {
                  filters.subject_id = filters.subject_id === s.subject_id ? null : s.subject_id;
                  filters.textbook_id = null;
                  filters.chapter_ids = [];
                  await loadTextbooks();
                  await loadChapters();
                  await search()
                }"
              >
                {{ s.subject_name }}
              </n-tag>
            </div>
          </div>

          <div class="filter-row">
            <div class="filter-label">教材</div>
            <div class="filter-content filter-tags">
              <template v-if="textbooks.length > 0">
                <n-tag
                  v-for="t in textbooks"
                  :key="t.textbook_id"
                  :bordered="false"
                  :class="['filter-tag', filters.textbook_id === t.textbook_id ? 'tag-selected' : '']"
                  @click="async () => {
                    filters.textbook_id = filters.textbook_id === t.textbook_id ? null : t.textbook_id;
                    filters.chapter_ids = [];
                    selectedMainChapters = [];
                    await loadChapters();
                    await search()
                  }"
                >
                  {{ t.textbook_name }}{{ t.author ? ' - ' + t.author : '' }}
                </n-tag>
              </template>
              <span v-else class="empty-hint">{{ filters.subject_id ? '暂无教材' : '请先选择科目' }}</span>
            </div>
          </div>

          <!-- 大章节选择 -->
          <div class="filter-row">
            <div class="filter-label">章节</div>
            <div class="filter-content filter-tags">
              <template v-if="chapterTree.length > 0">
                <n-tag
                  v-for="chapter in chapterTree"
                  :key="chapter.chapter_id"
                  :bordered="false"
                  :class="['filter-tag', 'chapter-main', selectedMainChapters.includes(chapter.chapter_id) ? 'chapter-main-selected' : '']"
                  @click="toggleMainChapter(chapter)"
                >
                  {{ chapter.chapter_name }}
                </n-tag>
              </template>
              <span v-else class="empty-hint">{{ filters.textbook_id ? '暂无章节' : '请先选择教材' }}</span>
            </div>
          </div>

          <!-- 小章节选择（按大章节分组显示） -->
          <div class="filter-row sub-chapters-row" v-if="visibleSubChapterGroups.length > 0">
            <div class="filter-label">小节</div>
            <div class="filter-content">
              <div class="sub-chapters-container">
                <div v-for="group in visibleSubChapterGroups" :key="group.parent.chapter_id" class="sub-chapter-group">
                  <span class="sub-chapter-group-label">{{ group.parent.chapter_name }}：</span>
                  <div class="sub-chapter-tags">
                    <n-tag
                      v-for="sub in group.children"
                      :key="sub.chapter_id"
                      :bordered="false"
                      :class="['filter-tag', 'chapter-sub', filters.chapter_ids.includes(sub.chapter_id) ? 'chapter-sub-selected' : '']"
                      @click="toggleSubChapter(sub.chapter_id)"
                    >
                      {{ sub.chapter_name }}
                    </n-tag>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="filter-row">
            <div class="filter-label">题型</div>
            <div class="filter-content filter-tags">
              <n-tag
                v-for="t in types"
                :key="t.type_id"
                :bordered="false"
                :class="['filter-tag', filters.type_ids.includes(t.type_id) ? 'tag-selected' : '']"
                @click="toggleType(t.type_id)"
              >
                {{ t.type_name }}
              </n-tag>
            </div>
          </div>

          <div class="filter-row">
            <div class="filter-label">难度</div>
            <div class="filter-content filter-tags">
              <n-tag
                v-for="d in difficulties"
                :key="d.difficulty_id"
                :bordered="false"
                :class="['filter-tag', 'difficulty-tag', getDifficultyClass(d.difficulty_id, d.difficulty_name)]"
                @click="toggleDifficulty(d.difficulty_id)"
              >
                {{ d.difficulty_name }}
              </n-tag>
            </div>
          </div>
        </template>
      </div>

      <n-data-table :columns="tableColumns" :data="available.items" :loading="loading" :max-height="560" :row-key="row => row.question_id" v-model:checked-row-keys="checkedRowKeys" />

      <div class="pager">
        <n-pagination v-model:page="filters.page" v-model:page-size="filters.page_size" :item-count="available.total" :page-sizes="[10, 20, 50, 100]" show-size-picker @update:page="handlePageChange" @update:page-size="handlePageSizeChange" />
      </div>
    </n-card>

    <n-modal v-model:show="detailDialog.visible" preset="card" title="题目详情" style="width: 600px">
      <div v-if="detailDialog.item">
        <n-descriptions :column="1" bordered>
          <n-descriptions-item label="题干"><div style="white-space: pre-wrap">{{ detailDialog.item.question_content }}</div></n-descriptions-item>
          <n-descriptions-item label="答案"><div style="white-space: pre-wrap">{{ detailDialog.item.question_answer }}</div></n-descriptions-item>
          <n-descriptions-item label="解析"><div style="white-space: pre-wrap">{{ detailDialog.item.question_analysis }}</div></n-descriptions-item>
        </n-descriptions>
      </div>
      <template #footer><n-button @click="detailDialog.visible = false">关闭</n-button></template>
    </n-modal>

    <n-drawer v-model:show="showPaperDrawer" :width="isDrawerFullscreen ? '100%' : 500" placement="right">
      <n-drawer-content title="已选题目与配置">
        <template #header-extra>
          <n-button text @click="isDrawerFullscreen = !isDrawerFullscreen"><template #icon><n-icon><ExpandOutline /></n-icon></template></n-button>
        </template>

        <div class="drawer-top-actions">
          <h3>已选题目（{{ picked.length }}）</h3>
          <div class="actions">
            <n-button size="small" @click="renumber"><template #icon><n-icon><RefreshOutline /></n-icon></template>重新编号</n-button>
            <n-button size="small" type="error" @click="clearPicked"><template #icon><n-icon><TrashOutline /></n-icon></template>清空</n-button>
          </div>
        </div>

        <n-form label-placement="left" label-width="80px" class="paper-form">
          <n-form-item label="试卷名"><n-input v-model:value="paper.paper_name" /></n-form-item>
          <n-form-item label="时长"><n-input-number v-model:value="paper.exam_duration" :min="1" :max="600" style="width: 100%" /></n-form-item>
          <n-form-item label="闭卷"><n-switch v-model:value="paper.is_closed_book" /></n-form-item>
          <n-form-item label="说明"><n-input v-model:value="paper.paper_desc" type="textarea" :rows="2" /></n-form-item>
        </n-form>

        <div class="total">总分：{{ pickedTotalScore }}</div>
        <div v-if="saved" class="hint">已保存：paper_id={{ saved.paper_id }}，共{{ saved.question_count }}题，总分{{ saved.total_score }}</div>

        <div class="picked-list">
          <div v-if="picked.length === 0" class="empty">从左侧筛选后勾选题目加入</div>
          <div v-for="(it, index) in picked" :key="it.question_id" class="picked-row" draggable="true" @dragstart="onDragStart(index)" @dragover.prevent @drop="onDrop(index)">
            <div class="row-left"><div class="drag-handle">≡</div></div>
            <div class="row-main">
              <div class="info-header">
                <span class="tag">{{ typeName(it.type_id) }}</span>
                <span class="tag">{{ difficultyName(it.difficulty_id) }}</span>
                <span class="qid">#{{ it.question_id }}</span>
              </div>
              <div class="info-body">
                <div class="q-field"><span class="label">【题干】</span><span class="text">{{ it.question_content }}</span></div>
                <div class="q-field" v-if="it.question_answer"><span class="label">【答案】</span><span class="text">{{ it.question_answer }}</span></div>
              </div>
            </div>
            <div class="row-right">
              <div class="control-item"><span class="control-label">序号</span><n-input-number v-model:value="it.question_sort" :min="1" size="small" style="width: 80px" /></div>
              <div class="control-item"><span class="control-label">分值</span><n-input-number v-model:value="it.question_score" :min="0" :step="0.5" size="small" style="width: 80px" /></div>
              <n-button text type="error" size="small" @click="removePicked(index)">移除</n-button>
            </div>
          </div>
        </div>

        <template #footer>
          <div style="display: flex; justify-content: flex-end; gap: 8px;">
            <n-button @click="showPaperDrawer = false">继续选择</n-button>
            <n-button type="primary" :loading="loading" @click="savePaper"><template #icon><n-icon><CheckmarkOutline /></n-icon></template>保存试卷</n-button>
          </div>
        </template>
      </n-drawer-content>
    </n-drawer>

    <n-modal v-model:show="aiDialog.visible" preset="card" title="AI智能组卷" style="width: 500px">
      <n-form label-placement="left" label-width="80px">
        <n-form-item label="科目">
          <n-select v-model:value="aiDialog.subject_id" :options="subjectOptions" placeholder="请选择科目" :disabled="!!filters.subject_id"
            @update:value="async () => { aiDialog.textbook_id = null; await loadAiDialogTextbooks() }" />
        </n-form-item>
        <n-form-item label="教材">
          <n-select v-model:value="aiDialog.textbook_id" :options="aiDialogTextbookOptions" placeholder="请选择教材" :disabled="!aiDialog.subject_id || !!filters.textbook_id" />
        </n-form-item>
        <n-form-item label="需求描述">
          <n-input v-model:value="aiDialog.description" type="textarea" :rows="6" placeholder="请描述您的组卷需求..." />
        </n-form-item>
      </n-form>
      <template #footer>
        <div style="display: flex; justify-content: flex-end; gap: 8px;">
          <n-button @click="aiDialog.visible = false">取消</n-button>
          <n-button type="primary" @click="startAiGeneration" :loading="loading">开始生成</n-button>
        </div>
      </template>
    </n-modal>

    <div v-if="stream.visible" class="streamPanel">
      <div class="streamHeader">
        <div class="streamTitle"><span>AI组卷过程</span><span class="streamMeta">ID: {{ stream.job_id }}（{{ stream.status }}）</span></div>
        <div class="streamActions">
          <n-button size="small" @click="stream.output = ''; stream.lines = []"><template #icon><n-icon><TrashOutline /></n-icon></template>清空</n-button>
          <n-button size="small" @click="stream.visible = false"><template #icon><n-icon><CloseOutline /></n-icon></template>关闭</n-button>
        </div>
      </div>
      <div class="streamProgress">
        <div class="progress-info"><span class="stage-text">{{ stream.currentStage }}</span></div>
        <n-progress :percentage="stream.progress" :height="8" :show-indicator="false" />
      </div>
      <div ref="streamBodyRef" class="streamBody">
        <div v-if="stream.lines.length > 0" class="streamLines"><div v-for="(l, i) in stream.lines" :key="i">{{ l }}</div></div>
        <div v-else class="streamHint">等待事件流…</div>
        <div v-if="stream.output" class="streamOutput"><div class="streamOutputTitle">模型输出（实时）</div><pre class="streamOutputPre">{{ stream.output }}</pre></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page { display: flex; flex-direction: column; gap: 12px; }
.header { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.actions { display: flex; gap: 10px; flex-wrap: wrap; }
.pager { display: flex; justify-content: flex-end; margin-top: 12px; }

:deep(.n-button) {
  border-radius: 14px;
}

:deep(.n-data-table) {
  border-radius: 14px;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.35);
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.08);
}

:deep(.n-data-table .n-data-table-th) {
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.98), rgba(241, 245, 249, 0.9));
  font-weight: 600;
  color: #334155;
}

:deep(.n-data-table .n-data-table-td),
:deep(.n-data-table .n-data-table-th) {
  padding: 12px 14px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.9);
}

:deep(.n-data-table .n-data-table-tr:nth-child(even) .n-data-table-td) {
  background: rgba(248, 250, 252, 0.7);
}

:deep(.n-data-table .n-data-table-tr:hover .n-data-table-td) {
  background: rgba(226, 232, 240, 0.6);
}

/* 标签式筛选区域样式 */
.filter-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
  padding: 16px;
  background: var(--n-color-embedded);
  border-radius: 12px;
}

.filter-section-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #64748b;
  padding-bottom: 8px;
  margin-bottom: 4px;
  border-bottom: 1px solid rgba(100, 116, 139, 0.15);
}

.filter-section-toggle {
  cursor: pointer;
  user-select: none;
  display: flex;
  align-items: center;
}

.filter-section-toggle:hover {
  background: rgba(100,116,139,0.06);
  border-radius: 8px;
}

.filter-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.filter-label {
  flex-shrink: 0;
  width: 60px;
  font-size: 13px;
  font-weight: 600;
  color: var(--n-text-color-2);
  line-height: 28px;
  text-align: right;
}

.filter-content {
  flex: 1;
  display: flex;
  align-items: center;
}

.filter-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.filter-tag {
  cursor: pointer;
  transition: all 0.2s ease;
  border-radius: 10px !important;
  padding: 4px 14px !important;
  font-size: 13px !important;
  background: rgba(100, 116, 139, 0.08) !important;
  color: #475569 !important;
  border: 1px solid rgba(100, 116, 139, 0.2) !important;
}

.filter-tag:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
}

/* 统一选中样式 - 深蓝色渐变 */
.tag-selected {
  background: linear-gradient(135deg, #1a5fb4 0%, #2563eb 100%) !important;
  color: white !important;
  border: none !important;
  box-shadow: 0 2px 8px rgba(26, 95, 180, 0.4) !important;
}

.empty-hint {
  font-size: 13px;
  color: #94a3b8;
  font-style: italic;
}

/* 小节分组容器 */
.sub-chapters-row .filter-content {
  align-items: flex-start;
}

.sub-chapters-container {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}

.sub-chapter-group {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.sub-chapter-group-label {
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 600;
  color: #1a5fb4;
  line-height: 26px;
  min-width: 100px;
}

.sub-chapter-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

/* 大章节 - 深蓝色 */
.chapter-main {
  font-weight: 600 !important;
  background: rgba(32, 128, 240, 0.1) !important;
  color: #1a5fb4 !important;
  border: 1px solid rgba(32, 128, 240, 0.3) !important;
}

.chapter-main-selected {
  background: linear-gradient(135deg, #1a5fb4 0%, #2563eb 100%) !important;
  color: white !important;
  border: none !important;
  box-shadow: 0 2px 8px rgba(26, 95, 180, 0.4) !important;
}

/* 子章节 - 浅蓝色 */
.chapter-sub {
  font-size: 12px !important;
  padding: 3px 10px !important;
  background: rgba(96, 165, 250, 0.08) !important;
  color: #3b82f6 !important;
  border: 1px solid rgba(96, 165, 250, 0.25) !important;
}

.chapter-sub-selected {
  background: linear-gradient(135deg, #60a5fa 0%, #93c5fd 100%) !important;
  color: white !important;
  border: none !important;
  box-shadow: 0 2px 6px rgba(96, 165, 250, 0.35) !important;
}

/* 难度颜色 */
.difficulty-tag {
  font-weight: 500 !important;
}

.difficulty-easy {
  color: #18a058 !important;
  border-color: #18a058 !important;
  background: rgba(24, 160, 88, 0.08) !important;
}

.difficulty-easy-selected {
  background: linear-gradient(135deg, #18a058 0%, #36ad6a 100%) !important;
  color: white !important;
  border: none !important;
}

.difficulty-medium {
  color: #f0a020 !important;
  border-color: #f0a020 !important;
  background: rgba(240, 160, 32, 0.08) !important;
}

.difficulty-medium-selected {
  background: linear-gradient(135deg, #f0a020 0%, #fcb040 100%) !important;
  color: white !important;
  border: none !important;
}

.difficulty-hard {
  color: #d03050 !important;
  border-color: #d03050 !important;
  background: rgba(208, 48, 80, 0.08) !important;
}

.difficulty-hard-selected {
  background: linear-gradient(135deg, #d03050 0%, #e88080 100%) !important;
  color: white !important;
  border: none !important;
}

.difficulty-default-selected {
  background: linear-gradient(135deg, #2080f0 0%, #409eff 100%) !important;
  color: white !important;
  border: none !important;
}

.paper-form { margin-bottom: 10px; }
.total { margin-bottom: 8px; font-weight: 600; }
.hint { margin-bottom: 10px; color: var(--n-text-color-3); font-size: 13px; }
.drawer-top-actions { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
.drawer-top-actions h3 { margin: 0; font-size: 16px; font-weight: 600; }
.picked-list { display: flex; flex-direction: column; gap: 10px; border-top: 1px solid var(--n-border-color); padding-top: 10px; }
.empty { color: var(--n-text-color-3); font-size: 13px; }
.picked-row { display: flex; gap: 10px; padding: 12px; border: 1px solid var(--n-border-color); border-radius: 12px; }
.row-left { display: flex; align-items: center; justify-content: center; width: 24px; }
.drag-handle { cursor: grab; color: var(--n-text-color-3); font-size: 18px; }
.row-main { flex: 1; display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.info-header { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.qid { font-weight: 600; }
.tag { font-size: 12px; padding: 2px 6px; background: var(--n-fill-color); border-radius: 8px; }
.info-body { display: flex; flex-direction: column; gap: 6px; }
.q-field { font-size: 13px; line-height: 1.5; word-break: break-all; }
.label { font-weight: 600; margin-right: 4px; }
.text { white-space: pre-wrap; }
.row-right { display: flex; flex-direction: column; gap: 8px; width: 100px; border-left: 1px solid var(--n-border-color); padding-left: 10px; justify-content: center; }
.control-item { display: flex; flex-direction: column; gap: 2px; align-items: flex-end; }
.control-label { font-size: 12px; color: var(--n-text-color-3); }
.streamPanel {
  position: fixed;
  right: 18px;
  top: 86px;
  width: 520px;
  height: 70vh;
  border: 1px solid var(--n-border-color);
  border-radius: 12px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.15);
  display: flex;
  flex-direction: column;
  z-index: 2000;
  overflow: hidden;
  background-color: transparent;
}

.streamPanel::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 0;
  backdrop-filter: blur(26px) saturate(130%);
  -webkit-backdrop-filter: blur(26px) saturate(130%);
  background: rgba(255, 255, 255, 0.55);
  pointer-events: none;
}

.streamHeader, .streamProgress, .streamBody {
  position: relative;
  z-index: 1;
}
</style>
