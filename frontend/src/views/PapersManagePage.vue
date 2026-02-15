<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Delete, Download, Check, FullScreen, View, Rank, Search } from '@element-plus/icons-vue'
import { http } from '../api/http'
import { getUser } from '../auth'
import ExportPreview from '../components/ExportPreview.vue'

const loading = ref(false)
const route = useRoute()
const mode = computed(() => route.meta.mode || 'export') // 'export' or 'review'

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
  publisher: '',
})

const publisherOptions = computed(() => {
  const set = new Set()
  for (const t of textbooks.value) {
    if (t.publisher) set.add(t.publisher)
  }
  return Array.from(set)
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
        const reviewer = user ? user.name : 'admin' // Fallback if no user
        
        const now = new Date()
        const review_time = now.getFullYear() + '-' +
            String(now.getMonth() + 1).padStart(2, '0') + '-' +
            String(now.getDate()).padStart(2, '0') + ' ' +
            String(now.getHours()).padStart(2, '0') + ':' +
            String(now.getMinutes()).padStart(2, '0') + ':' +
            String(now.getSeconds()).padStart(2, '0')
        
        await http.put(`/papers/${selectedPaperId.value}`, {
            ...paperForm, // Keep other fields
            review_status: status,
            reviewer: reviewer,
            review_time: review_time
        })
        ElMessage.success(status === 1 ? '已通过审核' : '已驳回')
        await loadPaperDetail(selectedPaperId.value)
        await loadPapers()
    } catch (e) {
        ElMessage.error(e?.message || '审核操作失败')
    }
}

const downloadBase = computed(() => http.defaults.baseURL || 'http://localhost:5000/api')

async function loadPapers() {
  loading.value = true
  error.value = ''
  try {
    const params = {}
    if (filters.subject_id) params.subject_id = filters.subject_id
    if (filters.textbook_id) params.textbook_id = filters.textbook_id
    if (filters.publisher) params.publisher = filters.publisher
    
    // “试卷编辑/导出”只显示审核通过的模块 (mode='export')
    // “试卷审核”只显示审核未通过的模块 (mode='review')
    if (mode.value === 'export') {
      params.review_status = 1
    } else {
      params.review_status = 0 // Pending
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
  // Prevent double-fetching or fetching while main list is loading
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
  paperForm.review_status = paper.value.review_status || 0 // Default to 0 (Pending)
  // await loadExports(paperId) // History disabled
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
    // If status changed to Approved/Rejected, set reviewer and time
    // But we should probably only do this if the user explicitly clicks a "Review" button
    // For now, let's keep basic save separate from review, OR update everything if status changed.
    // To keep it simple, we include review_status in paperForm, so it gets updated.
    
    // We'll handle reviewer info in a separate function 'submitReview' or here if we bind review_status.
    // Let's assume paperForm.review_status is bound to the review controls.
    
    await http.put(`/papers/${selectedPaperId.value}`, payload)
    ElMessage.success('已保存')
    await loadPaperDetail(selectedPaperId.value)
    await loadPapers()
  } catch (e) {
    ElMessage.error(e?.message || '保存失败')
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
    ElMessage.success('已保存题目顺序/分值')
    await loadPaperDetail(selectedPaperId.value)
  } catch (e) {
    ElMessage.error(e?.message || '保存失败')
  }
}

async function removePaper(row, event) {
  if (event) event.stopPropagation()
  try {
    await ElMessageBox.confirm(`确认删除试卷：${row.paper_name}？`, '提示', { type: 'warning' })
    await http.delete(`/papers/${row.paper_id}`)
    if (selectedPaperId.value === row.paper_id) {
      selectedPaperId.value = null
      showPaperDrawer.value = false // Close drawer if deleted current
    }
    await loadPapers()
    ElMessage.success('已删除')
  } catch (e) {
    if (e?.message) ElMessage.error(e.message)
  }
}

function handleDownload(resp, defaultName) {
    const blob = new Blob([resp.data], { type: resp.headers['content-type'] })
    let downloadName = defaultName
    const disposition = resp.headers['content-disposition']
    if (disposition) {
      if (disposition.includes('filename=')) {
        downloadName = disposition.split('filename=')[1].split(';')[0].replace(/['"]/g, '')
      }
      if (disposition.includes("filename*=")) {
         const match = disposition.match(/filename\*=UTF-8''(.+)/)
         if (match && match[1]) {
           try {
             downloadName = decodeURIComponent(match[1])
           } catch (e) {
             console.warn('Decode filename failed', e)
           }
         }
      }
    }
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.style.display = 'none'
    link.href = url
    link.setAttribute('download', downloadName)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
}

async function exportWord() {
  if (!selectedPaperId.value) return
  try {
    const resp = await http.post(`/papers/${selectedPaperId.value}/export/word`, {
      include_answer: false,
    }, { responseType: 'blob' })
    handleDownload(resp, (paper.value?.paper_name || 'paper') + '.docx')
    ElMessage.success('已导出Word')
  } catch (e) {
    ElMessage.error(e?.message || '导出失败')
  }
}

async function exportPdf() {
  if (!selectedPaperId.value) return
  try {
    const resp = await http.post(`/papers/${selectedPaperId.value}/export/pdf`, {
      include_answer: false,
    }, { responseType: 'blob' })
    handleDownload(resp, (paper.value?.paper_name || 'paper') + '.pdf')
    ElMessage.success('已导出PDF')
  } catch (e) {
    ElMessage.error(e?.message || '导出失败')
  }
}

async function loadExports(paperId) {
  const resp = await http.get(`/papers/${paperId}/exports`)
  exportsList.value = resp.data.items || []
}

async function openDownload(paperId, versionId, filename = null) {
  try {
    const res = await http.get(`/papers/${paperId}/exports/${versionId}/download`, {
      responseType: 'blob',
    })
    
    let downloadName = filename
    if (!downloadName) {
      const disposition = res.headers['content-disposition']
      if (disposition) {
        // Simple fallback extraction
        if (disposition.includes('filename=')) {
          downloadName = disposition.split('filename=')[1].split(';')[0].replace(/['"]/g, '')
        }
        // Try UTF-8 specific
        if (disposition.includes("filename*=")) {
           const match = disposition.match(/filename\*=UTF-8''(.+)/)
           if (match && match[1]) {
             try {
               downloadName = decodeURIComponent(match[1])
             } catch (e) {
               console.warn('Decode filename failed', e)
             }
           }
        }
      }
    }
    if (!downloadName) {
      downloadName = `paper_export_${paperId}.docx`
    }

    const blob = new Blob([res.data], { type: res.headers['content-type'] })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.style.display = 'none'
    link.href = url
    link.setAttribute('download', downloadName)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error(e?.message || '下载失败')
  }
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
  
  // Recalculate sort order immediately
  questions.value.forEach((q, idx) => {
    q.question_sort = idx + 1
  })
  
  draggingIndex.value = -1
}

function handleRowClick(row) {
  // If clicking the currently selected row, manually trigger reload
  // because current-change event won't fire for the same row.
  // We only check if NOT loading, to allow refresh.
  if (!loading.value && selectedPaperId.value === row.paper_id) {
    loadPaperDetail(row.paper_id)
  }
}

function handleSelectionChange(selection) {
  selectedPaperIds.value = selection.map(item => item.paper_id)
}

async function batchDelete() {
  if (selectedPaperIds.value.length === 0) return
  
  try {
    await ElMessageBox.confirm(`确认批量删除选中的 ${selectedPaperIds.value.length} 份试卷？`, '提示', {
      type: 'warning',
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
      confirmButtonClass: 'el-button--danger'
    })
    
    await http.post('/papers/batch-delete', { ids: selectedPaperIds.value })
    
    // Check if currently viewed paper is deleted
    if (selectedPaperId.value && selectedPaperIds.value.includes(selectedPaperId.value)) {
      selectedPaperId.value = null
      await loadPaperDetail(null)
    }
    
    await loadPapers()
    selectedPaperIds.value = [] // Clear selection
    ElMessage.success('批量删除成功')
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e?.message || '操作失败')
    }
  }
}

onMounted(async () => {
  await loadDicts()
  await loadTextbooks()
  await loadPapers()
})

watch(
  () => route.path,
  () => {
    // Reload when route changes (e.g. from /papers to /paper-review)
    loadPapers()
  }
)
</script>

<template>
  <div class="page">
    <el-alert v-if="error" :title="error" type="error" show-icon />

      <el-card class="card" :header="mode === 'export' ? '试卷列表' : '待审核试卷'">
        <template #header>
          <div class="header">
            <div class="filters">
              <el-select
                v-model="filters.subject_id"
                clearable
                placeholder="科目"
                style="width: 160px"
                @change="
                  async () => {
                    filters.textbook_id = null
                    await loadTextbooks()
                    await loadPapers()
                  }
                "
              >
                <el-option v-for="s in subjects" :key="s.subject_id" :label="s.subject_name" :value="s.subject_id" />
              </el-select>

              <el-select
                v-model="filters.textbook_id"
                clearable
                placeholder="教材"
                style="width: 200px"
                @change="loadPapers"
              >
                <el-option v-for="t in textbooks" :key="t.textbook_id" :label="t.textbook_name + (t.author ? '-' + t.author : '')" :value="t.textbook_id" />
              </el-select>

              <el-select v-model="filters.publisher" clearable placeholder="出版社" style="width: 160px" @change="loadPapers">
                <el-option v-for="p in publisherOptions" :key="p" :label="p" :value="p" />
              </el-select>
              
              <el-button @click="loadPapers" :icon="Search">查询</el-button>
            </div>
            <div class="actions">
              <el-button type="danger" plain @click="batchDelete" :disabled="selectedPaperIds.length === 0" :icon="Delete">批量删除</el-button>
              <el-button :loading="loading" @click="loadPapers" :icon="Refresh">刷新</el-button>
            </div>
          </div>
        </template>
        <el-table
          :data="papers"
          :loading="loading"
          highlight-current-row
          height="620"
          @row-click="handleRowClick"
          @selection-change="handleSelectionChange"
          @current-change="
            async (row) => {
              if (row) {
                selectedPaperId = row.paper_id
                await loadPaperDetail(selectedPaperId)
              }
            }
          "
        >
          <el-table-column type="selection" width="55" />
          <el-table-column prop="paper_id" label="ID" width="90" />
          <el-table-column prop="paper_name" label="名称" min-width="200" />
          <el-table-column prop="total_score" label="总分" width="90" />
          <el-table-column prop="review_status" label="状态" width="100">
             <template #default="{ row }">
                 <el-tag v-if="row.review_status === 1" type="success">已通过</el-tag>
                 <el-tag v-else-if="row.review_status === 2" type="danger">未通过</el-tag>
                 <el-tag v-else type="danger">待审核</el-tag>
             </template>
          </el-table-column>
          <el-table-column prop="reviewer" label="审核人" width="100" />
          <el-table-column prop="review_time" label="审核时间" width="160">
             <template #default="{ row }">
                 <span v-if="row.review_time">{{ new Date(row.review_time).toLocaleString() }}</span>
                 <span v-else>-</span>
             </template>
          </el-table-column>
          <el-table-column fixed="right" label="操作" width="100">
            <template #default="{ row }">
              <el-button link type="danger" @click="(e) => removePaper(row, e)" :icon="Delete">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-drawer v-model="showPaperDrawer" :size="isDrawerFullscreen ? '100%' : '600px'" direction="rtl">
        <template #header>
          <div class="drawer-header-custom">
            <span class="drawer-title">{{ mode === 'export' ? '试卷编辑与导出' : '试卷审核' }}</span>
            <div class="header-actions">
              <el-button v-if="mode === 'export'" :disabled="!selectedPaperId || paper?.review_status !== 1" @click="showPreview = true" :icon="View" size="small">导出预览</el-button>
              <el-button link @click="isDrawerFullscreen = !isDrawerFullscreen" :icon="FullScreen" title="切换全屏" />
            </div>
          </div>
        </template>

        <div v-if="!selectedPaperId" class="placeholder">选择左侧试卷进行编辑与导出</div>

        <div v-else class="detail">
          <el-form label-width="90px" class="paperForm">
            <el-form-item label="试卷名称">
              <el-input v-model="paperForm.paper_name" />
            </el-form-item>
            <el-form-item label="考试时长">
              <el-input-number v-model="paperForm.exam_duration" :min="0" style="width: 100%" />
            </el-form-item>
            <el-form-item label="闭卷">
              <el-select v-model="paperForm.is_closed_book" placeholder="选择" style="width: 100%">
                <el-option label="未知" :value="null" />
                <el-option label="闭卷" :value="1" />
                <el-option label="开卷" :value="0" />
              </el-select>
            </el-form-item>
            <el-form-item label="描述">
              <el-input v-model="paperForm.paper_desc" type="textarea" :rows="3" />
            </el-form-item>
          </el-form>
          <div class="inlineActions">
            <el-button type="primary" @click="savePaper" :icon="Check">保存试卷信息</el-button>
          </div>

          <el-divider />
          
          <div class="review-section">
             <div class="subTitle">试卷审核</div>
             <div class="review-status">
                 当前状态：
                 <el-tag v-if="paper?.review_status === 1" type="success">已通过</el-tag>
                 <el-tag v-else-if="paper?.review_status === 2" type="danger">未通过</el-tag>
                 <el-tag v-else type="danger">待审核</el-tag>
             </div>
             <div class="review-actions">
                 <el-button type="success" @click="submitReview(1)" :disabled="paper?.review_status === 1">通过审核</el-button>
             </div>
             <div v-if="paper?.reviewer" class="review-info">
                 审核人：{{ paper.reviewer }} &nbsp;&nbsp; 审核时间：{{ new Date(paper.review_time).toLocaleString() }}
             </div>
          </div>

          <el-divider />

          <div class="inlineActions">
            <div class="subTitle">
              题目顺序与分值
              <span class="drag-hint">
                <el-icon><Rank /></el-icon>
                可拖动调整顺序
              </span>
            </div>
            <el-button type="primary" @click="saveQuestions" :icon="Check">保存顺序/分值</el-button>
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
                  <el-input-number v-model="q.question_sort" :min="1" size="small" style="width: 100px" />
                </div>
                <div class="control-item">
                  <span class="label">分值</span>
                  <el-input-number v-model="q.question_score" :min="0" :step="0.5" size="small" style="width: 100px" />
                </div>
              </div>
            </div>
          </div>

          <el-divider />

        </div>
      </el-drawer>
      
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

.card {
  width: 100%;
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

.header-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.filters {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.actions {
  display: flex;
  gap: 10px;
}

.placeholder {
  color: var(--el-text-color-secondary);
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
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  padding: 10px;
  background-color: var(--el-bg-color-overlay);
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
  background-color: var(--el-fill-color-light);
  border: 1px dashed var(--el-color-primary);
}

.q-main {
  flex: 1;
}

.q-content {
  font-size: 14px;
  color: var(--el-text-color-primary);
  line-height: 1.5;
  white-space: pre-wrap;
}

.q-id {
  font-weight: bold;
  color: var(--el-color-primary);
  margin-right: 5px;
}

.q-controls {
  display: flex;
  gap: 20px;
  align-items: center;
  background-color: var(--el-fill-color-light);
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
  color: var(--el-text-color-secondary);
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
  color: var(--el-text-color-secondary);
  margin-left: 12px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.content {
  max-height: 80px;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  white-space: pre-wrap;
}
.review-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  background-color: var(--el-fill-color-light);
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
  color: var(--el-text-color-secondary);
}
</style>

