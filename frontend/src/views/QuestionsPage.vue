<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Plus, Edit, Delete, Upload, Download } from '@element-plus/icons-vue'
import { http } from '../api/http'

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
    create_user: 'manual',
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

async function remove(row) {
  try {
    await ElMessageBox.confirm(`确认删除题目ID=${row.question_id}？`, '提示', { type: 'warning' })
    await http.delete(`/questions/${row.question_id}`)
    await search()
  } catch (e) {
    if (e?.message) ElMessage.error(e.message)
  }
}

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
          <el-option v-for="t in textbooks" :key="t.textbook_id" :label="t.textbook_name" :value="t.textbook_id" />
        </el-select>

        <el-tree-select
          v-model="filter.chapter_id"
          :data="chapterTree"
          :props="{ label: 'chapter_name', children: 'children', value: 'chapter_id' }"
          node-key="chapter_id"
          multiple
          show-checkbox
          check-strictly
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
        <el-button type="info" plain @click="downloadTemplate" :icon="Download">下载模板</el-button>
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
          accept=".docx"
          :http-request="importWord"
          style="display: inline-flex; margin-right: 10px"
        >
          <el-button :icon="Upload">Word导入</el-button>
        </el-upload>
        <el-button type="primary" @click="openCreate" :icon="Plus">新增题目</el-button>
      </div>
    </div>

    <el-alert v-if="error" :title="error" type="error" show-icon />

    <el-card>
      <el-table :data="data.items" :loading="loading" height="560">
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
        <el-table-column prop="question_score" label="分值" width="90" />
        <el-table-column prop="review_status" label="状态" width="90" />
        <el-table-column label="题干" min-width="320">
          <template #default="{ row }">
            <div class="contentCell">{{ row.question_content }}</div>
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
            <el-option v-for="t in dialogTextbooks" :key="t.textbook_id" :label="t.textbook_name" :value="t.textbook_id" />
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
        <el-button type="primary" @click="submit">保存</el-button>
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
}
</style>
