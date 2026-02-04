<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { http } from '../api/http'

const loading = ref(false)
const error = ref('')

const papers = ref([])
const selectedPaperId = ref(null)
const paper = ref(null)
const questions = ref([])
const exportsList = ref([])

const paperForm = reactive({
  paper_name: '',
  paper_desc: '',
  exam_duration: null,
  is_closed_book: null,
})

const downloadBase = computed(() => http.defaults.baseURL || 'http://localhost:5000/api')

async function loadPapers() {
  loading.value = true
  error.value = ''
  try {
    const resp = await http.get('/papers')
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
    await loadExports(paperId)
  } catch (e) {
    error.value = e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function savePaper() {
  if (!selectedPaperId.value) return
  try {
    await http.put(`/papers/${selectedPaperId.value}`, { ...paperForm })
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

async function removePaper(row) {
  try {
    await ElMessageBox.confirm(`确认删除试卷：${row.paper_name}？`, '提示', { type: 'warning' })
    await http.delete(`/papers/${row.paper_id}`)
    if (selectedPaperId.value === row.paper_id) {
      selectedPaperId.value = null
      await loadPaperDetail(null)
    }
    await loadPapers()
    ElMessage.success('已删除')
  } catch (e) {
    if (e?.message) ElMessage.error(e.message)
  }
}

async function exportWord() {
  if (!selectedPaperId.value) return
  try {
    const resp = await http.post(`/papers/${selectedPaperId.value}/export/word`, {
      include_answer: false,
    })
    ElMessage.success('已导出Word')
    await loadExports(selectedPaperId.value)
    openDownload(selectedPaperId.value, resp.data.version_id)
  } catch (e) {
    ElMessage.error(e?.message || '导出失败')
  }
}

async function exportPdf() {
  if (!selectedPaperId.value) return
  try {
    const resp = await http.post(`/papers/${selectedPaperId.value}/export/pdf`, {
      include_answer: false,
    })
    ElMessage.success('已导出PDF')
    await loadExports(selectedPaperId.value)
    openDownload(selectedPaperId.value, resp.data.version_id)
  } catch (e) {
    ElMessage.error(e?.message || '导出失败')
  }
}

async function loadExports(paperId) {
  const resp = await http.get(`/papers/${paperId}/exports`)
  exportsList.value = resp.data.items || []
}

function openDownload(paperId, versionId) {
  const url = `${downloadBase.value}/papers/${paperId}/exports/${versionId}/download`
  window.open(url, '_blank')
}

onMounted(async () => {
  await loadPapers()
})
</script>

<template>
  <div class="page">
    <el-alert v-if="error" :title="error" type="error" show-icon />

    <div class="grid">
      <el-card class="card" header="试卷列表">
        <template #header>
          <div class="header">
            <div>试卷列表</div>
            <el-button :loading="loading" @click="loadPapers">刷新</el-button>
          </div>
        </template>
        <el-table
          :data="papers"
          :loading="loading"
          highlight-current-row
          height="620"
          @current-change="
            async (row) => {
              selectedPaperId = row?.paper_id || null
              await loadPaperDetail(selectedPaperId)
            }
          "
        >
          <el-table-column prop="paper_id" label="ID" width="90" />
          <el-table-column prop="paper_name" label="名称" min-width="200" />
          <el-table-column prop="total_score" label="总分" width="90" />
          <el-table-column prop="review_status" label="状态" width="90" />
          <el-table-column fixed="right" label="操作" width="100">
            <template #default="{ row }">
              <el-button link type="danger" @click="removePaper(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card class="card" header="试卷编辑与导出">
        <template #header>
          <div class="header">
            <div>试卷编辑与导出</div>
            <div class="actions">
              <el-button :disabled="!selectedPaperId" @click="exportWord">Word导出</el-button>
              <el-button :disabled="!selectedPaperId" @click="exportPdf">PDF导出</el-button>
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
            <el-button type="primary" @click="savePaper">保存试卷信息</el-button>
          </div>

          <el-divider />

          <div class="inlineActions">
            <div class="subTitle">题目顺序与分值</div>
            <el-button type="primary" @click="saveQuestions">保存顺序/分值</el-button>
          </div>
          <el-table :data="questions" height="360">
            <el-table-column prop="question_sort" label="序号" width="90">
              <template #default="{ row }">
                <el-input-number v-model="row.question_sort" :min="1" style="width: 100%" />
              </template>
            </el-table-column>
            <el-table-column prop="question_id" label="题目ID" width="110" />
            <el-table-column prop="question_score" label="分值" width="120">
              <template #default="{ row }">
                <el-input-number v-model="row.question_score" :min="0" :step="0.5" style="width: 100%" />
              </template>
            </el-table-column>
            <el-table-column label="题干" min-width="320">
              <template #default="{ row }">
                <div class="content">{{ row.question_content }}</div>
              </template>
            </el-table-column>
          </el-table>

          <el-divider />

          <div class="subTitle">导出历史</div>
          <el-table :data="exportsList" height="220">
            <el-table-column prop="created_at" label="时间" width="180" />
            <el-table-column prop="type" label="类型" width="90" />
            <el-table-column prop="filename" label="文件" min-width="220" />
            <el-table-column fixed="right" label="操作" width="120">
              <template #default="{ row }">
                <el-button link type="primary" @click="openDownload(selectedPaperId, row.version_id)">下载</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.grid {
  display: grid;
  grid-template-columns: 1fr 1.4fr;
  gap: 16px;
}

.card {
  width: 100%;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
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
}

.content {
  max-height: 80px;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  white-space: pre-wrap;
}
</style>

