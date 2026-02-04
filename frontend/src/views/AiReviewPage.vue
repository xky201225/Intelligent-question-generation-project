<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { http } from '../api/http'

const loading = ref(false)
const error = ref('')

const subjects = ref([])
const types = ref([])
const difficulties = ref([])
const textbooks = ref([])
const chapters = ref([])

const gen = reactive({
  subject_id: null,
  textbook_id: null,
  chapter_id: null,
  type_id: null,
  difficulty_id: null,
  count: 5,
  create_user: 'ai',
})

const pending = reactive({
  items: [],
  page: 1,
  page_size: 20,
})

const editDialog = reactive({
  visible: false,
  form: {
    question_id: null,
    subject_id: null,
    chapter_id: null,
    type_id: null,
    difficulty_id: null,
    question_score: null,
    question_content: '',
    question_answer: '',
    question_analysis: '',
  },
})

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
    return
  }
  const resp = await http.get(`/textbooks/${gen.textbook_id}/chapters`)
  chapters.value = resp.data.items || []
}

async function generate() {
  loading.value = true
  error.value = ''
  try {
    await http.post('/ai/generate-questions', {
      subject_id: gen.subject_id,
      chapter_id: gen.chapter_id,
      type_id: gen.type_id,
      difficulty_id: gen.difficulty_id,
      count: gen.count,
      create_user: gen.create_user,
    })
    ElMessage.success('已提交生成')
    await loadPending()
  } catch (e) {
    error.value = e?.message || '生成失败'
  } finally {
    loading.value = false
  }
}

async function loadPending() {
  const params = {
    page: pending.page,
    page_size: pending.page_size,
    subject_id: gen.subject_id || undefined,
    chapter_id: gen.chapter_id || undefined,
  }
  const resp = await http.get('/ai/pending', { params })
  pending.items = resp.data.items || []
}

async function approve(row) {
  try {
    await http.post('/ai/verify', {
      question_id: row.question_id,
      action: 'approve',
      reviewer: 'reviewer',
    })
    ElMessage.success('已通过')
    await loadPending()
  } catch (e) {
    ElMessage.error(e?.message || '操作失败')
  }
}

async function reject(row) {
  try {
    await http.post('/ai/verify', {
      question_id: row.question_id,
      action: 'reject',
      reviewer: 'reviewer',
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
    chapter_id: row.chapter_id,
    type_id: row.type_id,
    difficulty_id: row.difficulty_id,
    question_score: row.question_score,
    question_content: row.question_content,
    question_answer: row.question_answer,
    question_analysis: row.question_analysis,
  }
  editDialog.visible = true
}

async function updateAndApprove() {
  try {
    await http.post('/ai/verify', {
      question_id: editDialog.form.question_id,
      action: 'update_and_approve',
      reviewer: 'reviewer',
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
  await loadTextbooks()
  await loadPending()
})
</script>

<template>
  <div class="page">
    <el-card>
      <template #header>
        <div class="header">
          <div>AI 出题</div>
          <el-button type="primary" :loading="loading" @click="generate">生成</el-button>
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
              gen.chapter_id = null
              await loadTextbooks()
              await loadPending()
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
              gen.chapter_id = null
              await loadChapters()
            }
          "
        >
          <el-option v-for="t in textbooks" :key="t.textbook_id" :label="t.textbook_name" :value="t.textbook_id" />
        </el-select>

        <el-select v-model="gen.chapter_id" clearable placeholder="章节" style="width: 260px" @change="loadPending">
          <el-option v-for="c in chapters" :key="c.chapter_id" :label="c.chapter_name" :value="c.chapter_id" />
        </el-select>

        <el-select v-model="gen.type_id" clearable placeholder="题型" style="width: 160px">
          <el-option v-for="t in types" :key="t.type_id" :label="t.type_name" :value="t.type_id" />
        </el-select>

        <el-select v-model="gen.difficulty_id" clearable placeholder="难度" style="width: 160px">
          <el-option v-for="d in difficulties" :key="d.difficulty_id" :label="d.difficulty_name" :value="d.difficulty_id" />
        </el-select>

        <el-input-number v-model="gen.count" :min="1" :max="50" style="width: 160px" />
      </div>
    </el-card>

    <el-card>
      <template #header>
        <div class="header">
          <div>待校验题目</div>
          <el-button :loading="loading" @click="loadPending">刷新</el-button>
        </div>
      </template>

      <el-table :data="pending.items" :loading="loading" height="560">
        <el-table-column prop="question_id" label="ID" width="100" />
        <el-table-column prop="subject_id" label="科目ID" width="100" />
        <el-table-column prop="chapter_id" label="章节ID" width="100" />
        <el-table-column prop="type_id" label="题型ID" width="100" />
        <el-table-column prop="difficulty_id" label="难度ID" width="100" />
        <el-table-column label="题干" min-width="360">
          <template #default="{ row }">
            <div class="content">{{ row.question_content }}</div>
          </template>
        </el-table-column>
        <el-table-column fixed="right" label="操作" width="220">
          <template #default="{ row }">
            <el-button link type="primary" @click="approve(row)">通过</el-button>
            <el-button link @click="openEdit(row)">修改通过</el-button>
            <el-button link type="danger" @click="reject(row)">拒绝</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="editDialog.visible" title="修改并通过" width="760px">
      <el-form label-width="90px">
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
        <el-button @click="editDialog.visible = false">取消</el-button>
        <el-button type="primary" @click="updateAndApprove">保存并通过</el-button>
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

.formRow {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
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

