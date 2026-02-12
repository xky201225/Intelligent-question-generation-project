<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Check, Delete, Edit, Refresh, Close } from '@element-plus/icons-vue'
import { http } from '../api/http'
import { getUser } from '../auth'

const loading = ref(false)
const subjects = ref([])
const types = ref([])
const textbooks = ref([])
const chapterTree = ref([])

const pending = reactive({
  items: [],
  page: 1,
  page_size: 20,
  total: 0,
  subject_id: null,
})

const editDialog = reactive({
  visible: false,
  form: {
    question_id: null,
    subject_id: null,
    textbook_id: null,
    chapter_id: null,
    type_id: null,
    difficulty_id: null,
    question_score: null,
    question_content: '',
    question_answer: '',
    question_analysis: '',
  },
})

const detailDialog = reactive({
  visible: false,
  item: null
})

function openDetail(row) {
  detailDialog.item = row
  detailDialog.visible = true
}

async function loadDicts() {
  const [s, t] = await Promise.all([
    http.get('/dicts/subjects'),
    http.get('/dicts/question-types'),
  ])
  subjects.value = s.data.items || []
  types.value = t.data.items || []
}

async function loadTextbooks(subjectId) {
  if (!subjectId) {
    textbooks.value = []
    return
  }
  const resp = await http.get('/textbooks', {
    params: { subject_id: subjectId },
  })
  textbooks.value = resp.data.items || []
}

async function loadChapters(textbookId) {
  if (!textbookId) {
    chapterTree.value = []
    return
  }
  const resp = await http.get(`/textbooks/${textbookId}/chapters`)
  chapterTree.value = resp.data.tree || []
}

async function loadPending() {
  loading.value = true
  try {
    const params = {
      page: pending.page,
      page_size: pending.page_size,
      subject_id: pending.subject_id || undefined,
      review_status: 0, // 强制只查待审核
    }
    const resp = await http.get('/ai/pending', { params })
    pending.items = resp.data.items || []
    pending.total = resp.data.total || 0
  } catch (e) {
    ElMessage.error(e?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function approveAll() {
  try {
    await ElMessageBox.confirm('确定要通过所有待审核题目吗？', '提示', { type: 'warning' })
    const user = getUser()
    const resp = await http.post('/ai/verify/batch', {
      action: 'approve_all_pending',
      reviewer: user ? user.name : 'reviewer',
    })
    ElMessage.success(`已批量通过 ${resp.data.count} 道题目`)
    await loadPending()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e?.message || '操作失败')
    }
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(`确认删除题目ID=${row.question_id}？`, '提示', { type: 'warning' })
    await http.delete(`/questions/${row.question_id}`)
    ElMessage.success('已删除')
    await loadPending()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e?.message || '操作失败')
    }
  }
}

async function approve(row) {
  try {
    const user = getUser()
    await http.post('/ai/verify', {
      question_id: row.question_id,
      action: 'approve',
      reviewer: user ? user.name : 'reviewer',
    })
    ElMessage.success('已通过')
    await loadPending()
  } catch (e) {
    ElMessage.error(e?.message || '操作失败')
  }
}

async function reject(row) {
  try {
    const user = getUser()
    await http.post('/ai/verify', {
      question_id: row.question_id,
      action: 'reject',
      reviewer: user ? user.name : 'reviewer',
    })
    ElMessage.success('已拒绝')
    await loadPending()
  } catch (e) {
    ElMessage.error(e?.message || '操作失败')
  }
}

function openEdit(row) {
  editDialog.form = {
    question_id: row.question_id,
    subject_id: row.subject_id,
    textbook_id: row.textbook_id,
    chapter_id: row.chapter_id,
    type_id: row.type_id,
    difficulty_id: row.difficulty_id,
    question_score: row.question_score,
    question_content: row.question_content,
    question_answer: row.question_answer,
    question_analysis: row.question_analysis,
  }
  // Load dependencies
  if (row.subject_id) loadTextbooks(row.subject_id)
  if (row.textbook_id) loadChapters(row.textbook_id)
  editDialog.visible = true
}

async function updateAndApprove() {
  try {
    const user = getUser()
    await http.post('/ai/verify', {
      question_id: editDialog.form.question_id,
      action: 'update_and_approve',
      reviewer: user ? user.name : 'reviewer',
      fields: { ...editDialog.form },
    })
    editDialog.visible = false
    ElMessage.success('已修改并通过')
    await loadPending()
  } catch (e) {
    ElMessage.error(e?.message || '操作失败')
  }
}

onMounted(async () => {
  await loadDicts()
  await loadPending()
})
</script>

<template>
  <div class="page">
    <el-card>
      <template #header>
        <div class="header">
          <span>待校验题目</span>
          <div style="display: flex; gap: 8px">
            <el-select
              v-model="pending.subject_id"
              clearable
              placeholder="筛选科目"
              style="width: 140px"
              @change="loadPending"
            >
              <el-option v-for="s in subjects" :key="s.subject_id" :label="s.subject_name" :value="s.subject_id" />
            </el-select>
            <el-button type="success" plain @click="approveAll" :icon="Check">一键全部通过</el-button>
            <el-button @click="loadPending" :icon="Refresh">刷新</el-button>
          </div>
        </div>
      </template>

      <el-table :data="pending.items" style="width: 100%" v-loading="loading">
        <el-table-column prop="question_id" label="ID" width="80" />
        <el-table-column prop="subject_name" label="科目" width="120" />
        <el-table-column prop="chapter_name" label="章节" width="150" show-overflow-tooltip />
        <el-table-column prop="type_name" label="题型" width="100" />
        <el-table-column prop="difficulty_name" label="难度" width="80" />
        <el-table-column label="题目内容">
          <template #default="{ row }">
            <div class="contentCell" @click="openDetail(row)" title="点击查看详情">{{ row.question_content }}</div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)" :icon="Edit">修改通过</el-button>
            <el-button link type="danger" @click="remove(row)" :icon="Delete">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          v-model:current-page="pending.page"
          v-model:page-size="pending.page_size"
          :total="pending.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadPending"
          @current-change="loadPending"
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

    <el-dialog v-model="editDialog.visible" title="修改并通过" width="760px">
      <el-form label-width="90px">
        <el-form-item label="教材章节">
          <div style="display: flex; gap: 8px; width: 100%">
            <el-select 
              v-model="editDialog.form.textbook_id" 
              placeholder="选择教材" 
              style="flex: 1"
              @change="() => { editDialog.form.chapter_id = null; loadChapters(editDialog.form.textbook_id) }"
            >
              <el-option v-for="t in textbooks" :key="t.textbook_id" :label="t.textbook_name" :value="t.textbook_id" />
            </el-select>
            <el-tree-select
              v-model="editDialog.form.chapter_id"
              :data="chapterTree"
              :props="{ label: 'chapter_name', children: 'children', value: 'chapter_id' }"
              node-key="chapter_id"
              placeholder="选择章节"
              style="flex: 1"
              check-strictly
            />
          </div>
        </el-form-item>
        <el-form-item label="题型">
          <el-select v-model="editDialog.form.type_id" placeholder="请选择题型" style="width: 100%">
            <el-option v-for="t in types" :key="t.type_id" :label="t.type_name" :value="t.type_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="题干">
          <el-input v-model="editDialog.form.question_content" type="textarea" :rows="5" />
        </el-form-item>
        <el-form-item label="答案">
          <el-input v-model="editDialog.form.question_answer" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="解析">
          <el-input v-model="editDialog.form.question_analysis" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="分值">
          <el-input-number v-model="editDialog.form.question_score" :min="0" :step="0.5" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialog.visible = false" :icon="Close">取消</el-button>
        <el-button type="primary" @click="updateAndApprove" :icon="Check">保存并通过</el-button>
      </template>
    </el-dialog>
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

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
</style>