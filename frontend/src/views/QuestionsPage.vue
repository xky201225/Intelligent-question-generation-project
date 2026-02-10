<script setup>
import { onMounted, reactive, ref, h } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Plus, Edit, Delete, Upload, Download, VideoPlay, Close } from '@element-plus/icons-vue'
import { http } from '../api/http'
import { getToken, getUser } from '../auth'

const loading = ref(false)
const error = ref('')

const subjects = ref([])
const types = ref([])
const difficulties = ref([])
const textbooks = ref([])
const chapters = ref([])
const chapterTree = ref([])

const filter = reactive({
  q: '',
  subject_id: null,
  textbook_id: null,
  chapter_id: [],
  type_id: null,
  difficulty_id: null,
  review_status: 1,
  page: 1,
  page_size: 20,
})

const data = reactive({
  items: [],
  total: 0,
})

const selectedIds = ref([])

const dialog = reactive({
  visible: false,
  mode: 'create',
  form: {
    question_id: null,
    subject_id: null,
    chapter_id: null,
    type_id: null,
    difficulty_id: null,
    question_content: '',
    question_answer: '',
    question_analysis: '',
    question_score: null,
    review_status: 1,
    create_user: 'manual',
    reviewer: '',
  },
})

const dialogTextbookId = ref(null)
const dialogTextbooks = ref([])
const dialogChapterTree = ref([])

async function loadDialogTextbooks() {
  const resp = await http.get('/textbooks', {
    params: dialog.form.subject_id ? { subject_id: dialog.form.subject_id } : {},
  })
  dialogTextbooks.value = resp.data.items || []
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
    params: filter.subject_id ? { subject_id: filter.subject_id } : {},
  })
  textbooks.value = resp.data.items || []
}

async function loadChapters() {
  if (!filter.textbook_id) {
    chapters.value = []
    chapterTree.value = []
    return
  }
  const resp = await http.get(`/textbooks/${filter.textbook_id}/chapters`)
  chapters.value = resp.data.items || []
  chapterTree.value = resp.data.tree || []
}

async function loadDialogChapters() {
  if (!dialogTextbookId.value) {
    dialogChapterTree.value = []
    return
  }
  const resp = await http.get(`/textbooks/${dialogTextbookId.value}/chapters`)
  dialogChapterTree.value = resp.data.tree || []
}

async function search() {
  loading.value = true
  error.value = ''
  try {
    const params = {
      page: filter.page,
      page_size: filter.page_size,
      q: filter.q || undefined,
      subject_id: filter.subject_id || undefined,
      chapter_id: Array.isArray(filter.chapter_id) && filter.chapter_id.length > 0 ? filter.chapter_id.join(',') : undefined,
      type_id: filter.type_id || undefined,
      difficulty_id: filter.difficulty_id || undefined,
      review_status: filter.review_status === null ? undefined : filter.review_status,
    }
    const resp = await http.get('/questions', { params })
    data.items = resp.data.items || []
    data.total = resp.data.total || 0
  } catch (e) {
    error.value = e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function downloadTemplate() {
  const link = document.createElement('a')
  link.href = '/question_import_template.xlsx'
  link.download = '题目导入模板.xlsx'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

async function importExcel(options) {
  const file = options.file
  const form = new FormData()
  form.append('file', file)
  if (filter.subject_id) form.append('subject_id', String(filter.subject_id))
  if (filter.chapter_id) form.append('chapter_id', String(filter.chapter_id))
  if (filter.type_id) form.append('type_id', String(filter.type_id))
  if (filter.difficulty_id) form.append('difficulty_id', String(filter.difficulty_id))
  form.append('create_user', 'import')
  try {
    const resp = await http.post('/questions/import/excel', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    ElMessage.success(`导入完成：新增${resp.data.inserted}，跳过${resp.data.skipped}`)
    await search()
  } catch (e) {
    ElMessage.error(e?.message || '导入失败')
  } finally {
    options.onSuccess && options.onSuccess()
  }
}

async function importWord(options) {
  const file = options.file
  const form = new FormData()
  form.append('file', file)
  if (filter.subject_id) form.append('subject_id', String(filter.subject_id))
  if (filter.chapter_id) form.append('chapter_id', String(filter.chapter_id))
  if (filter.type_id) form.append('type_id', String(filter.type_id))
  if (filter.difficulty_id) form.append('difficulty_id', String(filter.difficulty_id))
  form.append('create_user', 'import')
  try {
    const resp = await http.post('/questions/import/word', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    ElMessage.success(`导入完成：新增${resp.data.inserted}，跳过${resp.data.skipped}`)
    await search()
  } catch (e) {
    ElMessage.error(e?.message || '导入失败')
  } finally {
    options.onSuccess && options.onSuccess()
  }
}

function openCreate() {
  dialog.mode = 'create'
  const user = getUser()
  dialog.form = {
    question_id: null,
    subject_id: filter.subject_id || null,
    chapter_id: Array.isArray(filter.chapter_id) ? (filter.chapter_id[0] || null) : filter.chapter_id || null,
    type_id: filter.type_id || null,
    difficulty_id: filter.difficulty_id || null,
    question_content: '',
    question_answer: '',
    question_analysis: '',
    question_score: null,
    create_user: user ? user.name : 'manual',
    reviewer: '',
  }
  dialogTextbookId.value = filter.textbook_id || null
  loadDialogTextbooks()
  loadDialogChapters()
  dialog.visible = true
}

async function openEdit(row) {
  dialog.mode = 'edit'
  dialog.form = {
    question_id: row.question_id,
    subject_id: row.subject_id,
    chapter_id: row.chapter_id,
    type_id: row.type_id,
    difficulty_id: row.difficulty_id,
    question_content: row.question_content,
    question_answer: row.question_answer,
    question_analysis: row.question_analysis,
    question_score: row.question_score,
    review_status: row.review_status,
    create_user: row.create_user || 'manual',
    reviewer: row.reviewer || '',
  }
  dialogTextbookId.value = null
  dialogTextbooks.value = []
  dialogChapterTree.value = []
  try {
    if (row.chapter_id) {
      const meta = await http.get(`/textbooks/chapters/${row.chapter_id}`)
      dialogTextbookId.value = meta.data?.item?.textbook_id || null
      dialog.form.subject_id = row.subject_id
      await loadDialogTextbooks()
      await loadDialogChapters()
    }
  } catch {
    // ignore
  }
  dialog.visible = true
}

async function approve() {
  try {
    const user = getUser()
    await http.post('/ai/verify', {
      question_id: dialog.form.question_id,
      action: 'approve',
      reviewer: user ? user.name : 'manual'
    })
    ElMessage.success('已审核通过')
    dialog.visible = false
    await search()
  } catch (e) {
    ElMessage.error(e?.message || '审核失败')
  }
}

async function submit() {
  try {
    if (
      !dialog.form.subject_id ||
      !dialog.form.chapter_id ||
      !dialog.form.type_id ||
      !dialog.form.difficulty_id ||
      !dialog.form.question_content
    ) {
      ElMessage.error('科目/章节/题型/难度/题干必填')
      return
    }
    if (dialog.mode === 'create') {
      await http.post('/questions', { ...dialog.form })
    } else {
      await http.put(`/questions/${dialog.form.question_id}`, {
        subject_id: dialog.form.subject_id,
        chapter_id: dialog.form.chapter_id,
        type_id: dialog.form.type_id,
        difficulty_id: dialog.form.difficulty_id,
        question_content: dialog.form.question_content,
        question_answer: dialog.form.question_answer,
        question_analysis: dialog.form.question_analysis,
        question_score: dialog.form.question_score,
      })
    }
    dialog.visible = false
    await search()
  } catch (e) {
    ElMessage.error(e?.message || '保存失败')
  }
}

async function checkAndDelete(ids, isBatch = false) {
  try {
    const checkResp = await http.post('/questions/check-dependencies', { ids })
    const deps = checkResp.data.dependencies || []
    
    if (deps.length > 0) {
      const message = h('div', null, [
        h('p', { style: 'margin-bottom: 10px; color: #E6A23C; font-weight: bold;' }, 
          '⚠️ 警告：检测到选中的题目被以下试卷引用：'),
        h('ul', { style: 'max-height: 200px; overflow-y: auto; padding-left: 20px; margin-bottom: 10px;' }, 
          deps.map(d => h('li', `Q${d.question_id} 在 "${d.paper_name}" (第 ${d.question_sort} 题)`))
        ),
        h('p', { style: 'color: #F56C6C;' }, '如果删除，将会从这些试卷中同步移除该题目！'),
        h('p', '是否确认继续删除？')
      ])
      
      await ElMessageBox.confirm(message, '关联删除警告', {
        type: 'warning',
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        confirmButtonClass: 'el-button--danger'
      })
    } else {
      const count = ids.length
      const text = isBatch ? `确认删除选中的 ${count} 个题目？` : `确认删除题目ID=${ids[0]}？`
      await ElMessageBox.confirm(text, '提示', { type: 'warning' })
    }

    // Perform delete
    if (isBatch) {
      await http.post('/questions/batch-delete', { ids })
      ElMessage.success('批量删除成功')
    } else {
      await http.delete(`/questions/${ids[0]}`)
      ElMessage.success('删除成功')
    }
    await search()
    // Clear selection if batch delete
    if (isBatch) {
      selectedIds.value = []
    }
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') {
      ElMessage.error(e?.message || '操作失败')
    }
  }
}

async function remove(row) {
  await checkAndDelete([row.question_id], false)
}

async function batchDelete() {
  if (selectedIds.value.length === 0) return
  await checkAndDelete(selectedIds.value, true)
}

function onSelectionChange(selection) {
  selectedIds.value = selection.map((x) => x.question_id)
}


const aiConfigDialog = reactive({
  visible: false,
  file: null,
  form: {
    subject_id: null,
    textbook_id: null,
  }
})

const aiReviewDialog = reactive({
  visible: false,
  items: [],
  loading: false
})

function onAiFileChange(file) {
  if (!file) return
  // Reset form
  aiConfigDialog.form.subject_id = filter.subject_id || null
  aiConfigDialog.form.textbook_id = filter.textbook_id || null
  aiConfigDialog.file = file.raw
  aiConfigDialog.visible = true
  
  // Trigger load if subject selected
  if (aiConfigDialog.form.subject_id) {
    loadDialogTextbooksForAi()
  }
}

const aiDialogTextbooks = ref([])
async function loadDialogTextbooksForAi() {
  const resp = await http.get('/textbooks', {
    params: aiConfigDialog.form.subject_id ? { subject_id: aiConfigDialog.form.subject_id } : {},
  })
  aiDialogTextbooks.value = resp.data.items || []
}

async function startParsing() {
  if (!aiConfigDialog.form.subject_id || !aiConfigDialog.form.textbook_id) {
    ElMessage.error('请选择科目和教材')
    return
  }
  
  const file = aiConfigDialog.file
  const form = new FormData()
  form.append('file', file)
  form.append('subject_id', String(aiConfigDialog.form.subject_id))
  // form.append('textbook_id', String(aiConfigDialog.form.textbook_id)) // 后端可能不需要，或者只是为了上下文
  // 注意：后端目前没有接收 textbook_id，但接收 subject_id, chapter_id 等。
  // 用户说“选择完之后手动的为AI解析出来的题目依次设置...章节”
  // 所以解析时不需要传章节，也不需要传题型/难度（或者传默认值）
  
  // 传默认值避免后端校验失败（虽然我已经注释了校验，但为了保险）
  form.append('chapter_id', '0') 
  form.append('type_id', '0')
  form.append('difficulty_id', '0')
  form.append('create_user', 'ai_import')
  
  aiConfigDialog.visible = false
  
  try {
    const resp = await http.post('/ai/parse-word', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    startStream(resp.data.job_id)
  } catch (e) {
    ElMessage.error(e?.message || '启动解析失败')
  }
}

// ---------------------------------------------------------------------

// Stream related
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
const streamBodyRef = ref(null)
let eventSource = null
let typingTimer = null
let pollingTimer = null
let outputQueue = ''

function pushLine(text) {
  stream.lines.push(text)
  if (stream.lines.length > 2000) {
    stream.lines.splice(0, stream.lines.length - 2000)
  }
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
      const backlog = outputQueue.length
      const step = Math.min(60, Math.max(1, Math.floor(backlog / 120)))
      const chunk = outputQueue.slice(0, step)
      outputQueue = outputQueue.slice(step)

      stream.output += chunk
      if (stream.output.length > 200000) {
        stream.output = stream.output.slice(stream.output.length - 200000)
      }
      
      // Update progress
      if (stream.totalCount > 0) {
        const matches = stream.output.match(/"question_analysis"/g)
        const count = matches ? matches.length : 0
        stream.generatedCount = Math.max(stream.generatedCount, count)
        stream.progress = Math.min(100, Math.floor((stream.generatedCount / stream.totalCount) * 100))
      }

      requestAnimationFrame(() => {
          if (streamBodyRef.value) streamBodyRef.value.scrollTop = streamBodyRef.value.scrollHeight
      })
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
          stream.currentStage = '正在解析...'
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
            stream.currentStage = '解析完成'
            stream.progress = 100
            stopStream()
            
            const items = job.items || []
            if (items.length === 0) {
                 ElMessage.warning('未能解析出题目')
            } else {
                 openReviewDialog(items)
            }
            setTimeout(() => { stream.visible = false }, 1000)
          } else if (ev.type === 'job_error') {
            stream.status = 'error'
            stream.currentStage = '解析出错'
            stopStream()
          } else if (ev.type === 'progress') {
             if (ev.data && ev.data.inserted) {
                 stream.generatedCount = ev.data.inserted
             }
          }
        }
      }
    } catch (e) {
      console.error(e)
    }
  }, 1000)
}

// AI Review Logic
const aiReviewChapterTree = ref([])

const detailDialog = reactive({
  visible: false,
  item: null
})

function openDetail(row) {
  detailDialog.item = row
  detailDialog.visible = true
}

async function openReviewDialog(items) {
  aiReviewDialog.items = items.map(it => ({
      ...it,
      // Ensure IDs are mapped if backend returned defaults
      subject_id: aiConfigDialog.form.subject_id, // Use selected subject
      // chapter/type/difficulty might be 0 or None from backend
      chapter_id: it.chapter_id || null,
      type_id: it.type_id || null,
      difficulty_id: it.difficulty_id || null,
      // Add UI state
      _error: false
  }))
  
  // Load chapter tree for the selected textbook
  if (aiConfigDialog.form.textbook_id) {
      const resp = await http.get(`/textbooks/${aiConfigDialog.form.textbook_id}/chapters`)
      aiReviewChapterTree.value = resp.data.tree || []
  }
  
  aiReviewDialog.visible = true
}

async function saveParsedQuestions() {
    // Validate
    let hasError = false
    for (const item of aiReviewDialog.items) {
        if (!item.chapter_id || !item.type_id || !item.difficulty_id) {
            item._error = true
            hasError = true
        } else {
            item._error = false
        }
    }
    
    if (hasError) {
        ElMessage.error('请为所有题目设置章节、题型和难度（标红项）')
        return
    }
    
    aiReviewDialog.loading = true
    try {
        const resp = await http.post('/questions/batch-create', { items: aiReviewDialog.items })
        ElMessage.success(`成功入库 ${resp.data.inserted_count} 道题目`)
        aiReviewDialog.visible = false
        // Switch to pending review tab
        filter.review_status = 0
        search()
    } catch (e) {
        ElMessage.error(e?.message || '保存失败')
    } finally {
        aiReviewDialog.loading = false
    }
}

// Batch set functions
const batchSet = reactive({
    chapter_id: null,
    type_id: null,
    difficulty_id: null
})

function applyBatchSet() {
    for (const item of aiReviewDialog.items) {
        if (batchSet.chapter_id) item.chapter_id = batchSet.chapter_id
        if (batchSet.type_id) item.type_id = batchSet.type_id
        if (batchSet.difficulty_id) item.difficulty_id = batchSet.difficulty_id
    }
    ElMessage.success('已应用批量设置')
}

// Removed old importWordAi
// async function importWordAi(options) { ... } 

onMounted(async () => {
  await loadDicts()
  await loadTextbooks()
  await search()
})
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <div class="filters">
        <el-input v-model="filter.q" placeholder="关键词（题干/解析）" style="width: 220px" clearable @keyup.enter="search" />
        <el-select
          v-model="filter.subject_id"
          clearable
          placeholder="科目"
          style="width: 160px"
          @change="
            async () => {
              filter.textbook_id = null
              filter.chapter_id = []
              await loadTextbooks()
              await search()
            }
          "
        >
          <el-option v-for="s in subjects" :key="s.subject_id" :label="s.subject_name" :value="s.subject_id" />
        </el-select>

        <el-select
          v-model="filter.textbook_id"
          clearable
          placeholder="教材"
          style="width: 220px"
          @change="
            async () => {
              filter.chapter_id = []
              await loadChapters()
            }
          "
          @current-change="search"
        >
          <el-option v-for="t in textbooks" :key="t.textbook_id" :label="t.textbook_name + (t.author ? '-' + t.author : '')" :value="t.textbook_id" />
        </el-select>

        <el-tree-select
          v-model="filter.chapter_id"
          :data="chapterTree"
          :props="{ label: 'chapter_name', children: 'children', value: 'chapter_id' }"
          node-key="chapter_id"
          multiple
          show-checkbox
          collapse-tags
          collapse-tags-tooltip
          clearable
          placeholder="章节（多选）"
          style="width: 220px"
          @change="search"
        />

        <el-select v-model="filter.type_id" clearable placeholder="题型" style="width: 120px" @change="search">
          <el-option v-for="t in types" :key="t.type_id" :label="t.type_name" :value="t.type_id" />
        </el-select>

        <el-select v-model="filter.difficulty_id" clearable placeholder="难度" style="width: 120px" @change="search">
          <el-option v-for="d in difficulties" :key="d.difficulty_id" :label="d.difficulty_name" :value="d.difficulty_id" />
        </el-select>

        <el-select v-model="filter.review_status" clearable placeholder="审核状态" style="width: 120px" @change="search">
          <el-option label="已通过" :value="1" />
          <el-option label="待审核" :value="0" />
          <el-option label="已拒绝" :value="2" />
        </el-select>

        <el-button type="default" @click="search" :icon="Search">查询</el-button>
      </div>

      <div class="rightActions">
        <el-button type="danger" plain @click="batchDelete" :disabled="selectedIds.length === 0" :icon="Delete">批量删除</el-button>
        <el-button type="success" @click="downloadTemplate" :icon="Download">下载模板</el-button>
        <el-upload
          action=""
          :show-file-list="false"
          accept=".xlsx,.xls"
          :http-request="importExcel"
          style="display: inline-flex; margin-right: 10px"
        >
          <el-button :icon="Upload">Excel导入</el-button>
        </el-upload>
        <el-upload
          action=""
          :show-file-list="false"
          accept=".docx,.pdf"
          :auto-upload="false"
          :on-change="onAiFileChange"
          style="display: inline-flex; margin-right: 10px"
        >
          <el-button :icon="VideoPlay" type="warning" plain>AI智能导入</el-button>
        </el-upload>
        <el-button type="primary" @click="openCreate" :icon="Plus">新增题目</el-button>
      </div>
    </div>

    <el-alert v-if="error" :title="error" type="error" show-icon />

    <el-card>
      <el-table :data="data.items" :loading="loading" height="560" @selection-change="onSelectionChange">
        <el-table-column type="selection" width="55" />
        <el-table-column prop="question_id" label="ID" width="100" />
        <el-table-column label="科目" width="140">
          <template #default="{ row }">
            {{ row.subject_name || row.subject_id }}
          </template>
        </el-table-column>
        <el-table-column label="章节" width="220">
          <template #default="{ row }">
            {{ row.chapter_name || row.chapter_id }}
          </template>
        </el-table-column>
        <el-table-column label="题型" width="140">
          <template #default="{ row }">
            {{ row.type_name || row.type_id }}
          </template>
        </el-table-column>
        <el-table-column label="难度" width="120">
          <template #default="{ row }">
            {{ row.difficulty_name || row.difficulty_id }}
          </template>
        </el-table-column>
        <el-table-column label="题干" min-width="320">
          <template #default="{ row }">
            <div class="contentCell" @click="openDetail(row)" title="点击查看详情">{{ row.question_content }}</div>
          </template>
        </el-table-column>
        <el-table-column fixed="right" label="操作" width="180">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)" :icon="Edit">编辑</el-button>
            <el-button link type="danger" @click="remove(row)" :icon="Delete">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pager">
        <el-pagination
          v-model:current-page="filter.page"
          v-model:page-size="filter.page_size"
          :total="data.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @size-change="
            () => {
              filter.page = 1
              search()
            }
          "
          @current-change="search"
        />
      </div>
    </el-card>

    <el-dialog v-model="dialog.visible" :title="dialog.mode === 'create' ? '新增题目' : '编辑题目'" width="720px">
      <el-form label-width="90px">
        <el-form-item label="科目">
          <el-select
            v-model="dialog.form.subject_id"
            placeholder="科目"
            style="width: 100%"
            filterable
            @change="
              async () => {
                dialogTextbookId = null
                dialog.form.chapter_id = null
                dialogChapterTree = []
                await loadDialogTextbooks()
              }
            "
          >
            <el-option v-for="s in subjects" :key="s.subject_id" :label="s.subject_name" :value="s.subject_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="教材">
          <el-select
            v-model="dialogTextbookId"
            placeholder="教材"
            style="width: 100%"
            filterable
            clearable
            @change="
              async () => {
                dialog.form.chapter_id = null
                await loadDialogChapters()
              }
            "
          >
            <el-option v-for="t in dialogTextbooks" :key="t.textbook_id" :label="t.textbook_name + (t.author ? '-' + t.author : '')" :value="t.textbook_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="章节">
          <el-tree-select
            v-model="dialog.form.chapter_id"
            :data="dialogChapterTree"
            :props="{ label: 'chapter_name', children: 'children', value: 'chapter_id' }"
            node-key="chapter_id"
            check-strictly
            clearable
            placeholder="章节"
            style="width: 100%"
            :disabled="!dialogTextbookId"
          />
        </el-form-item>
        <el-form-item label="题型">
          <el-select v-model="dialog.form.type_id" placeholder="题型" style="width: 100%" filterable>
            <el-option v-for="t in types" :key="t.type_id" :label="t.type_name" :value="t.type_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="难度">
          <el-select v-model="dialog.form.difficulty_id" placeholder="难度" style="width: 100%" filterable>
            <el-option v-for="d in difficulties" :key="d.difficulty_id" :label="d.difficulty_name" :value="d.difficulty_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="分值">
          <el-input-number v-model="dialog.form.question_score" :min="0" :step="0.5" style="width: 100%" />
        </el-form-item>
        <el-form-item label="题干">
          <el-input v-model="dialog.form.question_content" type="textarea" :rows="5" />
        </el-form-item>
        <el-form-item label="答案">
          <el-input v-model="dialog.form.question_answer" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="解析">
          <el-input v-model="dialog.form.question_analysis" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="审核人" v-if="dialog.mode === 'edit'">
          <el-input v-model="dialog.form.reviewer" disabled />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button v-if="dialog.mode === 'edit' && dialog.form.review_status === 0" type="success" @click="approve">审核通过</el-button>
        <el-button type="primary" @click="submit">保存</el-button>
      </template>
    </el-dialog>

    <!-- AI Config Dialog -->
    <el-dialog v-model="aiConfigDialog.visible" title="AI导入设置" width="500px">
      <el-form label-width="80px">
        <el-form-item label="已选文件">
          <div>{{ aiConfigDialog.file?.name }}</div>
        </el-form-item>
        <el-form-item label="科目">
          <el-select
            v-model="aiConfigDialog.form.subject_id"
            placeholder="请选择科目"
            style="width: 100%"
            @change="
              async () => {
                aiConfigDialog.form.textbook_id = null
                await loadDialogTextbooksForAi()
              }
            "
          >
            <el-option v-for="s in subjects" :key="s.subject_id" :label="s.subject_name" :value="s.subject_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="教材">
          <el-select
            v-model="aiConfigDialog.form.textbook_id"
            placeholder="请选择教材"
            style="width: 100%"
          >
            <el-option v-for="t in aiDialogTextbooks" :key="t.textbook_id" :label="t.textbook_name + (t.author ? '-' + t.author : '')" :value="t.textbook_id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="aiConfigDialog.visible = false">取消</el-button>
        <el-button type="primary" @click="startParsing">开始解析</el-button>
      </template>
    </el-dialog>

    <!-- AI Review Dialog -->
    <el-dialog v-model="aiReviewDialog.visible" title="AI解析结果确认" width="90%" :close-on-click-modal="false">
        <div style="margin-bottom: 10px; padding: 10px; background: #f5f7fa; border-radius: 4px; display: flex; align-items: center; gap: 10px;">
            <span style="font-weight: bold; font-size: 14px;">批量设置：</span>
            <el-select v-model="batchSet.type_id" placeholder="题型" style="width: 120px" clearable>
                <el-option v-for="t in types" :key="t.type_id" :label="t.type_name" :value="t.type_id" />
            </el-select>
            <el-select v-model="batchSet.difficulty_id" placeholder="难度" style="width: 120px" clearable>
                <el-option v-for="d in difficulties" :key="d.difficulty_id" :label="d.difficulty_name" :value="d.difficulty_id" />
            </el-select>
            <el-tree-select
                v-model="batchSet.chapter_id"
                :data="aiReviewChapterTree"
                :props="{ label: 'chapter_name', children: 'children', value: 'chapter_id' }"
                node-key="chapter_id"
                check-strictly
                placeholder="章节"
                style="width: 200px"
                clearable
            />
            <el-button type="primary" link @click="applyBatchSet">应用到所有</el-button>
        </div>

        <el-table :data="aiReviewDialog.items" height="500px" border stripe>
            <el-table-column type="index" label="#" width="50" />
            <el-table-column label="题干" min-width="300">
                <template #default="{ row }">
                    <el-input v-model="row.question_content" type="textarea" :autosize="{ minRows: 2, maxRows: 10 }" />
                </template>
            </el-table-column>
            <el-table-column label="答案" width="150">
                <template #default="{ row }">
                    <el-input v-model="row.question_answer" type="textarea" :autosize="{ minRows: 2, maxRows: 10 }" />
                </template>
            </el-table-column>
            <el-table-column label="解析" width="200">
                <template #default="{ row }">
                    <el-input v-model="row.question_analysis" type="textarea" :autosize="{ minRows: 2, maxRows: 10 }" />
                </template>
            </el-table-column>
            <el-table-column label="分值" width="120">
                <template #default="{ row }">
                    <el-input-number v-model="row.question_score" :min="0" :step="0.5" controls-position="right" style="width: 100%" />
                </template>
            </el-table-column>
            
            <!-- Configurable Fields -->
            <el-table-column label="题型" width="130">
                <template #default="{ row }">
                    <el-select v-model="row.type_id" :class="{ 'is-error': row._error && !row.type_id }" placeholder="请选择">
                        <el-option v-for="t in types" :key="t.type_id" :label="t.type_name" :value="t.type_id" />
                    </el-select>
                </template>
            </el-table-column>
            <el-table-column label="难度" width="110">
                <template #default="{ row }">
                    <el-select v-model="row.difficulty_id" :class="{ 'is-error': row._error && !row.difficulty_id }" placeholder="请选择">
                        <el-option v-for="d in difficulties" :key="d.difficulty_id" :label="d.difficulty_name" :value="d.difficulty_id" />
                    </el-select>
                </template>
            </el-table-column>
            <el-table-column label="章节" width="200">
                <template #default="{ row }">
                    <el-tree-select
                        v-model="row.chapter_id"
                        :data="aiReviewChapterTree"
                        :props="{ label: 'chapter_name', children: 'children', value: 'chapter_id' }"
                        node-key="chapter_id"
                        check-strictly
                        :class="{ 'is-error': row._error && !row.chapter_id }"
                        style="width: 100%"
                        placeholder="请选择"
                    />
                </template>
            </el-table-column>
            
            <el-table-column label="操作" width="60" fixed="right">
                <template #default="{ $index }">
                    <el-button link type="danger" :icon="Delete" @click="aiReviewDialog.items.splice($index, 1)"></el-button>
                </template>
            </el-table-column>
        </el-table>
        
        <template #footer>
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span>共 {{ aiReviewDialog.items.length }} 题</span>
                <div>
                    <el-button @click="aiReviewDialog.visible = false">取消</el-button>
                    <el-button type="primary" :loading="aiReviewDialog.loading" @click="saveParsedQuestions">确认入库</el-button>
                </div>
            </div>
        </template>
    </el-dialog>

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

    <div v-if="stream.visible" class="streamPanel">
      <div class="streamHeader">
        <div class="streamTitle">
          <span>AI解析过程</span>
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
          <span class="count-text">已解析入库 {{ stream.generatedCount }} 题</span>
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

.toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.rightActions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
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

.is-error :deep(.el-input__wrapper) {
    box-shadow: 0 0 0 1px var(--el-color-danger) inset;
}
</style>
