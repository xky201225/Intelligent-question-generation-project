<script setup>
import { computed, onMounted, reactive, ref, watch, h } from 'vue'
import { useRoute } from 'vue-router'
import { useMessage, useDialog, NButton, NTag, NIcon } from 'naive-ui'
import { RefreshOutline, TrashOutline, DownloadOutline, CheckmarkOutline, ExpandOutline, EyeOutline, ReorderFourOutline, SearchOutline } from '@vicons/ionicons5'
import { http } from '../api/http'
import { getUser } from '../auth'
import ExportPreview from '../components/ExportPreview.vue'

const message = useMessage()
const dialog = useDialog()
const loading = ref(false)
const route = useRoute()
const mode = computed(() => route.meta.mode || 'export')

const error = ref('')
const showPaperDrawer = ref(false)
const isDrawerFullscreen = ref(false)
const showPreview = ref(false)

const papers = ref([])
const subjects = ref([])
const textbooks = ref([])

const filters = reactive({
  subject_id: null,
  textbook_id: null,
  publisher: null,
})

const publisherOptions = computed(() => {
  const set = new Set()
  for (const t of textbooks.value) {
    if (t.publisher) set.add(t.publisher)
  }
  return Array.from(set).map(p => ({ label: p, value: p }))
})

const selectedPaperIds = ref([])
const selectedPaperId = ref(null)
const paper = ref(null)
const questions = ref([])
const exportsList = ref([])
const draggingIndex = ref(-1)

const paperForm = reactive({
  paper_name: '',
  paper_desc: '',
  exam_duration: null,
  is_closed_book: null,
  review_status: 0,
})

async function loadDicts() {
  try {
    const res = await http.get('/dicts/subjects')
    subjects.value = res.data.items || []
  } catch (e) {
    console.error(e)
  }
}

async function loadTextbooks() {
  try {
    const params = {}
    if (filters.subject_id) params.subject_id = filters.subject_id
    const res = await http.get('/textbooks', { params })
    textbooks.value = res.data.items || []
  } catch (e) {
    console.error(e)
  }
}

async function submitReview(status) {
    if (!selectedPaperId.value) return
    try {
        const user = getUser()
        const reviewer = user ? user.name : 'admin'

        const now = new Date()
        const review_time = now.getFullYear() + '-' +
            String(now.getMonth() + 1).padStart(2, '0') + '-' +
            String(now.getDate()).padStart(2, '0') + ' ' +
            String(now.getHours()).padStart(2, '0') + ':' +
            String(now.getMinutes()).padStart(2, '0') + ':' +
            String(now.getSeconds()).padStart(2, '0')
        
        await http.put(`/papers/${selectedPaperId.value}`, {
            ...paperForm,
            review_status: status,
            reviewer: reviewer,
            review_time: review_time
        })
        message.success(status === 1 ? '已通过审核' : '已驳回')
        await loadPaperDetail(selectedPaperId.value)
        await loadPapers()
    } catch (e) {
        message.error(e?.message || '审核操作失败')
    }
}

async function loadPapers() {
  loading.value = true
  error.value = ''
  try {
    const params = {}
    if (filters.subject_id) params.subject_id = filters.subject_id
    if (filters.textbook_id) params.textbook_id = filters.textbook_id
    if (filters.publisher) params.publisher = filters.publisher
    
    if (mode.value === 'export') {
      params.review_status = 1
    } else {
      params.review_status = 0
    }
    
    const resp = await http.get('/papers', { params })
    papers.value = resp.data.items || []
  } catch (e) {
    error.value = e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function loadPaperDetail(paperId) {
  if (!paperId) {
    paper.value = null
    questions.value = []
    exportsList.value = []
    return
  }
  if (loading.value) return

  loading.value = true
  error.value = ''
  try {
    const resp = await http.get(`/papers/${paperId}`)
    paper.value = resp.data.paper
    questions.value = resp.data.questions || []
    paperForm.paper_name = paper.value.paper_name || ''
    paperForm.paper_desc = paper.value.paper_desc || ''
    paperForm.exam_duration = paper.value.exam_duration
    paperForm.is_closed_book = paper.value.is_closed_book
    paperForm.review_status = paper.value.review_status || 0
    showPaperDrawer.value = true
  } catch (e) {
    error.value = e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function savePaper() {
  if (!selectedPaperId.value) return
  try {
    const payload = { ...paperForm }
    await http.put(`/papers/${selectedPaperId.value}`, payload)
    message.success('已保存')
    await loadPaperDetail(selectedPaperId.value)
    await loadPapers()
  } catch (e) {
    message.error(e?.message || '保存失败')
  }
}

function normalizeSort() {
  const arr = [...questions.value]
  arr.sort((a, b) => (a.question_sort || 0) - (b.question_sort || 0))
  arr.forEach((q, idx) => {
    q.question_sort = idx + 1
  })
  questions.value = arr
}

async function saveQuestions() {
  if (!selectedPaperId.value) return
  try {
    normalizeSort()
    await http.put(`/papers/${selectedPaperId.value}/questions`, {
      items: questions.value.map((q) => ({
        question_id: q.question_id,
        question_sort: q.question_sort,
        question_score: q.question_score,
      })),
    })
    message.success('已保存题目顺序/分值')
    await loadPaperDetail(selectedPaperId.value)
  } catch (e) {
    message.error(e?.message || '保存失败')
  }
}

async function removePaper(row) {
  dialog.warning({
    title: '提示',
    content: `确认删除试卷：${row.paper_name}？`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await http.delete(`/papers/${row.paper_id}`)
        if (selectedPaperId.value === row.paper_id) {
          selectedPaperId.value = null
          showPaperDrawer.value = false
        }
        await loadPapers()
        message.success('已删除')
      } catch (e) {
        message.error(e?.message || '删除失败')
      }
    }
  })
}

function onDragStart(index) {
  draggingIndex.value = index
}

function onDragOver(e) {
  e.preventDefault()
}

function onDrop(index) {
  if (draggingIndex.value === -1 || draggingIndex.value === index) return
  
  const movedItem = questions.value[draggingIndex.value]
  questions.value.splice(draggingIndex.value, 1)
  questions.value.splice(index, 0, movedItem)
  
  questions.value.forEach((q, idx) => {
    q.question_sort = idx + 1
  })
  
  draggingIndex.value = -1
}

function handleRowClick(row) {
  if (!loading.value) {
    selectedPaperId.value = row.paper_id
    loadPaperDetail(row.paper_id)
  }
}

async function batchDelete() {
  if (selectedPaperIds.value.length === 0) return
  
  dialog.warning({
    title: '提示',
    content: `确认批量删除选中的 ${selectedPaperIds.value.length} 份试卷？`,
    positiveText: '确认删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await http.post('/papers/batch-delete', { ids: selectedPaperIds.value })

        if (selectedPaperId.value && selectedPaperIds.value.includes(selectedPaperId.value)) {
          selectedPaperId.value = null
          await loadPaperDetail(null)
        }

        await loadPapers()
        selectedPaperIds.value = []
        message.success('批量删除成功')
      } catch (e) {
        message.error(e?.message || '操作失败')
      }
    }
  })
}

onMounted(async () => {
  await loadDicts()
  await loadTextbooks()
  await loadPapers()
})

watch(
  () => route.path,
  () => {
    loadPapers()
  }
)

const subjectOptions = computed(() => subjects.value.map(s => ({ label: s.subject_name, value: s.subject_id })))
const textbookOptions = computed(() => textbooks.value.map(t => ({ label: t.textbook_name + (t.author ? '-' + t.author : ''), value: t.textbook_id })))

const closedBookOptions = [
  { label: '未知', value: null },
  { label: '闭卷', value: 1 },
  { label: '开卷', value: 0 }
]

const tableColumns = [
  { type: 'selection' },
  { title: 'ID', key: 'paper_id', width: 90 },
  { title: '名称', key: 'paper_name' },
  { title: '总分', key: 'total_score', width: 90 },
  {
    title: '状态',
    key: 'review_status',
    width: 100,
    render(row) {
      if (row.review_status === 1) return h(NTag, { type: 'success' }, { default: () => '已通过' })
      if (row.review_status === 2) return h(NTag, { type: 'error' }, { default: () => '未通过' })
      return h(NTag, { type: 'warning' }, { default: () => '待审核' })
    }
  },
  { title: '审核人', key: 'reviewer', width: 100 },
  {
    title: '审核时间',
    key: 'review_time',
    width: 160,
    render(row) {
      return row.review_time ? new Date(row.review_time).toLocaleString() : '-'
    }
  },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    render(row) {
      return h(NButton, { size: 'small', type: 'error', onClick: (e) => { e.stopPropagation(); removePaper(row) } }, { default: () => '删除' })
    }
  }
]
</script>

<template>
  <div class="page">
    <n-alert v-if="error" type="error" :title="error" />

    <n-card :title="mode === 'export' ? '试卷列表' : '待审核试卷'">
      <template #header-extra>
        <div class="header-actions">
          <n-button @click="loadPapers">
            <template #icon><n-icon><SearchOutline /></n-icon></template>
            查询
          </n-button>
          <n-button type="error" :disabled="selectedPaperIds.length === 0" @click="batchDelete">
            <template #icon><n-icon><TrashOutline /></n-icon></template>
            批量删除
          </n-button>
          <n-button :loading="loading" @click="loadPapers">
            <template #icon><n-icon><RefreshOutline /></n-icon></template>
            刷新
          </n-button>
        </div>
      </template>

      <!-- 筛选区域：标签式布局 -->
      <div class="filter-section">
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
                await loadTextbooks();
                await loadPapers()
              }"
            >
              {{ s.subject_name }}
            </n-tag>
          </div>
        </div>

        <div class="filter-row" v-if="textbooks.length > 0">
          <div class="filter-label">教材</div>
          <div class="filter-content filter-tags">
            <n-tag
              v-for="t in textbooks"
              :key="t.textbook_id"
              :bordered="false"
              :class="['filter-tag', filters.textbook_id === t.textbook_id ? 'tag-selected' : '']"
              @click="async () => {
                filters.textbook_id = filters.textbook_id === t.textbook_id ? null : t.textbook_id;
                await loadPapers()
              }"
            >
              {{ t.textbook_name }}{{ t.author ? ' - ' + t.author : '' }}
            </n-tag>
          </div>
        </div>

        <div class="filter-row" v-if="publisherOptions.length > 0">
          <div class="filter-label">出版社</div>
          <div class="filter-content filter-tags">
            <n-tag
              v-for="p in publisherOptions"
              :key="p.value"
              :bordered="false"
              :class="['filter-tag', filters.publisher === p.value ? 'tag-selected' : '']"
              @click="() => { filters.publisher = filters.publisher === p.value ? null : p.value; loadPapers() }"
            >
              {{ p.label }}
            </n-tag>
          </div>
        </div>
      </div>

      <n-data-table
        :columns="tableColumns"
        :data="papers"
        :loading="loading"
        :max-height="620"
        :row-key="row => row.paper_id"
        v-model:checked-row-keys="selectedPaperIds"
        @update:checked-row-keys="keys => selectedPaperIds = keys"
        :row-props="row => ({ style: 'cursor: pointer', onClick: () => handleRowClick(row) })"
      />
    </n-card>

    <n-drawer v-model:show="showPaperDrawer" :width="isDrawerFullscreen ? '100%' : 600" placement="right">
      <n-drawer-content :title="mode === 'export' ? '试卷编辑与导出' : '试卷审核'">
        <template #header-extra>
          <div class="header-actions">
            <n-button v-if="mode === 'export'" :disabled="!selectedPaperId || paper?.review_status !== 1" size="small" @click="showPreview = true">
              <template #icon><n-icon><EyeOutline /></n-icon></template>
              导出预览
            </n-button>
            <n-button text @click="isDrawerFullscreen = !isDrawerFullscreen">
              <template #icon><n-icon><ExpandOutline /></n-icon></template>
            </n-button>
          </div>
        </template>

        <div v-if="!selectedPaperId" class="placeholder">选择左侧试卷进行编辑与导出</div>

        <div v-else class="detail">
          <n-form label-placement="left" label-width="90px" class="paperForm">
            <n-form-item label="试卷名称">
              <n-input v-model:value="paperForm.paper_name" />
            </n-form-item>
            <n-form-item label="考试时长">
              <n-input-number v-model:value="paperForm.exam_duration" :min="0" style="width: 100%" />
            </n-form-item>
            <n-form-item label="闭卷">
              <n-select v-model:value="paperForm.is_closed_book" :options="closedBookOptions" placeholder="选择" />
            </n-form-item>
            <n-form-item label="描述">
              <n-input v-model:value="paperForm.paper_desc" type="textarea" :rows="3" />
            </n-form-item>
          </n-form>
          <div class="inlineActions">
            <n-button type="primary" @click="savePaper">
              <template #icon><n-icon><CheckmarkOutline /></n-icon></template>
              保存试卷信息
            </n-button>
          </div>

          <n-divider />

          <div class="review-section">
             <div class="subTitle">试卷审核</div>
             <div class="review-status">
                 当前状态：
                 <n-tag v-if="paper?.review_status === 1" type="success">已通过</n-tag>
                 <n-tag v-else-if="paper?.review_status === 2" type="error">未通过</n-tag>
                 <n-tag v-else type="warning">待审核</n-tag>
             </div>
             <div class="review-actions">
                 <n-button type="success" @click="submitReview(1)" :disabled="paper?.review_status === 1">通过审核</n-button>
             </div>
             <div v-if="paper?.reviewer" class="review-info">
                 审核人：{{ paper.reviewer }} &nbsp;&nbsp; 审核时间：{{ new Date(paper.review_time).toLocaleString() }}
             </div>
          </div>

          <n-divider />

          <div class="inlineActions">
            <div class="subTitle">
              题目顺序与分值
              <span class="drag-hint">
                <n-icon><ReorderFourOutline /></n-icon>
                可拖动调整顺序
              </span>
            </div>
            <n-button type="primary" @click="saveQuestions">
              <template #icon><n-icon><CheckmarkOutline /></n-icon></template>
              保存顺序/分值
            </n-button>
          </div>
          <div class="question-list">
            <div 
              v-for="(q, index) in questions" 
              :key="q.question_id" 
              class="question-card"
              draggable="true"
              @dragstart="onDragStart(index)"
              @dragover="onDragOver"
              @drop="onDrop(index)"
              :class="{ 'is-dragging': draggingIndex === index }"
            >
              <div class="q-main">
                <div class="q-content">
                  <span class="q-id">#{{ q.question_id }}</span>
                  {{ q.question_content }}
                </div>
              </div>
              <div class="q-controls">
                <div class="control-item">
                  <span class="label">序号</span>
                  <n-input-number v-model:value="q.question_sort" :min="1" size="small" style="width: 100px" />
                </div>
                <div class="control-item">
                  <span class="label">分值</span>
                  <n-input-number v-model:value="q.question_score" :min="0" :step="0.5" size="small" style="width: 100px" />
                </div>
              </div>
            </div>
          </div>

          <n-divider />
        </div>
      </n-drawer-content>
    </n-drawer>

    <ExportPreview
      v-model:visible="showPreview"
      :paper="paper"
      :questions="questions"
    />
  </div>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.header-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.placeholder {
  color: var(--n-text-color-3);
  font-size: 13px;
}

.detail {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.question-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.question-card {
  border: 1px solid var(--n-border-color);
  border-radius: 4px;
  padding: 10px;
  background-color: var(--n-card-color);
  display: flex;
  flex-direction: column;
  gap: 10px;
  cursor: grab;
  transition: all 0.2s ease;
}

.question-card:active {
  cursor: grabbing;
}

.is-dragging {
  opacity: 0.5;
  border: 1px dashed var(--n-primary-color);
}

.q-main {
  flex: 1;
}

.q-content {
  font-size: 14px;
  line-height: 1.5;
  white-space: pre-wrap;
}

.q-id {
  font-weight: bold;
  color: var(--n-primary-color);
  margin-right: 5px;
}

.q-controls {
  display: flex;
  gap: 20px;
  align-items: center;
  padding: 8px;
  border-radius: 4px;
}

.control-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.label {
  font-size: 12px;
  color: var(--n-text-color-3);
}

.paperForm {
  max-width: 760px;
}

.inlineActions {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.subTitle {
  font-weight: 600;
  display: flex;
  align-items: center;
}

.drag-hint {
  font-size: 12px;
  font-weight: normal;
  color: var(--n-text-color-3);
  margin-left: 12px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.review-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 15px;
  border-radius: 6px;
}

.review-status {
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.review-actions {
  display: flex;
  gap: 10px;
}

.review-info {
  font-size: 12px;
  color: var(--n-text-color-3);
}

/* 标签式筛选区域样式 */
.filter-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  background: var(--n-color-embedded);
  border-radius: 12px;
  margin-bottom: 16px;
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

.tag-selected {
  background: linear-gradient(135deg, #1a5fb4 0%, #2563eb 100%) !important;
  color: white !important;
  border: none !important;
  box-shadow: 0 2px 8px rgba(26, 95, 180, 0.4) !important;
}
</style>
