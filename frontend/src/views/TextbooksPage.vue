<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Plus, Operation, Edit, Delete, Upload, MagicStick, Check, Close, Download } from '@element-plus/icons-vue'
import { http } from '../api/http'

const loading = ref(false)
const error = ref('')

const subjects = ref([])
const filter = reactive({ subject_id: null })

const textbooks = ref([])
const selectedTextbook = ref(null)

const chapters = ref([])
const chapterTree = ref([])
const selectedChapterId = ref(null)

const textbookDialog = reactive({
  visible: false,
  mode: 'create',
  form: { textbook_id: null, subject_id: null, textbook_name: '', author: '', publisher: '', edition: '' },
})

const chapterDialog = reactive({
  visible: false,
  mode: 'create',
  form: { chapter_id: null, chapter_name: '', chapter_level: 1, parent_chapter_id: null, chapter_sort: 1 },
})

const selectedChapter = computed(() => {
  const findNode = (nodes) => {
    for (const n of nodes || []) {
      if (n.chapter_id === selectedChapterId.value) return n
      const hit = findNode(n.children)
      if (hit) return hit
    }
    return null
  }
  return findNode(chapterTree.value)
})

const summaryLoading = ref(false)
const chapterSummary = ref('')

async function loadChapterSummary(chapterId) {
  if (!chapterId) {
    chapterSummary.value = ''
    return
  }
  summaryLoading.value = true
  try {
    const resp = await http.get(`/textbooks/chapters/${chapterId}/summary`)
    chapterSummary.value = resp.data.summary || ''
  } catch (e) {
    ElMessage.error(e?.message || '概要加载失败')
  } finally {
    summaryLoading.value = false
  }
}

async function saveChapterSummary() {
  if (!selectedChapterId.value) {
    ElMessage.warning('请先选择一个章节节点')
    return
  }
  summaryLoading.value = true
  try {
    await http.put(`/textbooks/chapters/${selectedChapterId.value}/summary`, {
      summary: chapterSummary.value,
    })
    ElMessage.success('已保存')
  } catch (e) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    summaryLoading.value = false
  }
}

async function generateChapterSummary() {
  if (!selectedChapterId.value) {
    ElMessage.warning('请先选择一个章节节点')
    return
  }
  summaryLoading.value = true
  try {
    const resp = await http.post(`/textbooks/chapters/${selectedChapterId.value}/summary/generate`)
    chapterSummary.value = resp.data.summary || ''
    ElMessage.success('已生成')
  } catch (e) {
    ElMessage.error(e?.message || '生成失败')
  } finally {
    summaryLoading.value = false
  }
}

async function importChaptersExcel(options) {
  if (!selectedTextbook.value) {
    ElMessage.warning('请先选择一个教材')
    options.onError && options.onError(new Error('未选择教材'))
    return
  }
  const form = new FormData()
  form.append('file', options.file)
  try {
    const resp = await http.post(`/textbooks/${selectedTextbook.value.textbook_id}/chapters/import/excel`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    ElMessage.success(`导入完成：新增${resp.data.inserted}，跳过${resp.data.skipped}`)
    await loadChapters(selectedTextbook.value.textbook_id)
    options.onSuccess && options.onSuccess()
  } catch (e) {
    ElMessage.error(e?.message || '导入失败')
    options.onError && options.onError(e)
  }
}

function downloadTemplate() {
  const link = document.createElement('a')
  link.href = '/chapter_import_template.xlsx'
  link.download = '章节导入模板.xlsx'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

async function loadSubjects() {
  const resp = await http.get('/dicts/subjects')
  subjects.value = resp.data.items || []
}

async function loadTextbooks() {
  loading.value = true
  error.value = ''
  try {
    const resp = await http.get('/textbooks', {
      params: filter.subject_id ? { subject_id: filter.subject_id } : {},
    })
    textbooks.value = resp.data.items || []
  } catch (e) {
    error.value = e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function loadChapters(textbookId) {
  if (!textbookId) {
    chapters.value = []
    chapterTree.value = []
    selectedChapterId.value = null
    return
  }
  try {
    const resp = await http.get(`/textbooks/${textbookId}/chapters`)
    chapters.value = resp.data.items || []
    chapterTree.value = resp.data.tree || []
    selectedChapterId.value = null
  } catch (e) {
    ElMessage.error(e?.message || '章节加载失败')
  }
}

function openCreateTextbook() {
  textbookDialog.mode = 'create'
  textbookDialog.form = {
    textbook_id: null,
    subject_id: filter.subject_id || null,
    textbook_name: '',
    author: '',
    publisher: '',
    edition: '',
  }
  textbookDialog.visible = true
}

function openEditTextbook(row) {
  textbookDialog.mode = 'edit'
  textbookDialog.form = { ...row }
  textbookDialog.visible = true
}

async function submitTextbook() {
  try {
    if (!textbookDialog.form.subject_id || !textbookDialog.form.textbook_name) {
      ElMessage.error('subject_id 和教材名称必填')
      return
    }
    if (textbookDialog.mode === 'create') {
      await http.post('/textbooks', {
        subject_id: textbookDialog.form.subject_id,
        textbook_name: textbookDialog.form.textbook_name,
        author: textbookDialog.form.author,
        publisher: textbookDialog.form.publisher,
        edition: textbookDialog.form.edition,
      })
    } else {
      await http.put(`/textbooks/${textbookDialog.form.textbook_id}`, {
        subject_id: textbookDialog.form.subject_id,
        textbook_name: textbookDialog.form.textbook_name,
        author: textbookDialog.form.author,
        publisher: textbookDialog.form.publisher,
        edition: textbookDialog.form.edition,
      })
    }
    textbookDialog.visible = false
    await loadTextbooks()
  } catch (e) {
    ElMessage.error(e?.message || '保存失败')
  }
}

async function removeTextbook(row) {
  try {
    await ElMessageBox.confirm(`确认删除教材：${row.textbook_name}？`, '提示', { type: 'warning' })
    await http.delete(`/textbooks/${row.textbook_id}`)
    if (selectedTextbook.value?.textbook_id === row.textbook_id) {
      selectedTextbook.value = null
      await loadChapters(null)
    }
    await loadTextbooks()
  } catch (e) {
    if (e?.message) ElMessage.error(e.message)
  }
}

function openCreateChapter(mode) {
  if (!selectedTextbook.value) {
    ElMessage.warning('请先选择一个教材')
    return
  }
  if (mode === 'child' && !selectedChapter.value) {
    ElMessage.warning('请先选择一个章节节点')
    return
  }
  chapterDialog.mode = 'create'
  chapterDialog.form = {
    chapter_id: null,
    chapter_name: '',
    chapter_level: mode === 'child' ? (selectedChapter.value?.chapter_level || 1) + 1 : 1,
    parent_chapter_id: mode === 'child' ? selectedChapter.value.chapter_id : null,
    chapter_sort: 1,
  }
  chapterDialog.visible = true
}

function openEditChapter() {
  if (!selectedChapter.value) {
    ElMessage.warning('请先选择一个章节节点')
    return
  }
  chapterDialog.mode = 'edit'
  chapterDialog.form = {
    chapter_id: selectedChapter.value.chapter_id,
    chapter_name: selectedChapter.value.chapter_name,
    chapter_level: selectedChapter.value.chapter_level,
    parent_chapter_id: selectedChapter.value.parent_chapter_id,
    chapter_sort: selectedChapter.value.chapter_sort,
  }
  chapterDialog.visible = true
}

async function submitChapter() {
  if (!selectedTextbook.value) return
  try {
    if (!chapterDialog.form.chapter_name || chapterDialog.form.chapter_level === null) {
      ElMessage.error('章节名称与层级必填')
      return
    }
    if (chapterDialog.mode === 'create') {
      await http.post(`/textbooks/${selectedTextbook.value.textbook_id}/chapters`, {
        chapter_name: chapterDialog.form.chapter_name,
        chapter_level: chapterDialog.form.chapter_level,
        parent_chapter_id: chapterDialog.form.parent_chapter_id,
        chapter_sort: chapterDialog.form.chapter_sort,
      })
    } else {
      await http.put(`/textbooks/chapters/${chapterDialog.form.chapter_id}`, {
        chapter_name: chapterDialog.form.chapter_name,
        chapter_level: chapterDialog.form.chapter_level,
        parent_chapter_id: chapterDialog.form.parent_chapter_id,
        chapter_sort: chapterDialog.form.chapter_sort,
      })
    }
    chapterDialog.visible = false
    await loadChapters(selectedTextbook.value.textbook_id)
  } catch (e) {
    ElMessage.error(e?.message || '保存失败')
  }
}

async function removeChapter() {
  if (!selectedChapter.value) {
    ElMessage.warning('请先选择一个章节节点')
    return
  }
  try {
    await ElMessageBox.confirm(`确认删除章节：${selectedChapter.value.chapter_name}？`, '提示', { type: 'warning' })
    await http.delete(`/textbooks/chapters/${selectedChapter.value.chapter_id}`)
    await loadChapters(selectedTextbook.value.textbook_id)
  } catch (e) {
    if (e?.message) ElMessage.error(e.message)
  }
}

const showChapterTreeDrawer = ref(false)
const showSummaryDialog = ref(false)

async function handleSelectTextbook(row) {
  selectedTextbook.value = row
  await loadChapters(row?.textbook_id)
  showChapterTreeDrawer.value = true
}

async function handleNodeClick(node) {
  if (!node) return
  selectedChapterId.value = node.chapter_id
  await loadChapterSummary(node.chapter_id)
  showSummaryDialog.value = true
}

watch(selectedChapterId, async (id) => {
  // await loadChapterSummary(id) // Moved to handleNodeClick
})

onMounted(async () => {
  await loadSubjects()
  await loadTextbooks()
})
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <div class="left">
        <el-select v-model="filter.subject_id" clearable placeholder="按科目筛选" style="width: 220px" @change="loadTextbooks">
          <el-option v-for="s in subjects" :key="s.subject_id" :label="s.subject_name" :value="s.subject_id" />
        </el-select>
        <el-button :loading="loading" @click="loadTextbooks" :icon="Refresh">刷新</el-button>
      </div>
      <el-button type="primary" @click="openCreateTextbook" :icon="Plus">新增教材</el-button>
    </div>

    <el-alert v-if="error" :title="error" type="error" show-icon />

    <el-card class="card" header="教材列表">
      <el-table
        :data="textbooks"
        :loading="loading"
        highlight-current-row
        height="calc(100vh - 180px)"
      >
        <el-table-column prop="textbook_id" label="ID" width="90" />
        <el-table-column prop="textbook_name" label="名称" min-width="200" />
        <el-table-column prop="author" label="作者" width="140" />
        <el-table-column fixed="right" label="操作" width="300">
          <template #default="{ row }">
            <el-button link type="primary" @click="handleSelectTextbook(row)" :icon="Operation">管理章节</el-button>
            <el-button link type="primary" @click="openEditTextbook(row)" :icon="Edit">编辑</el-button>
            <el-button link type="danger" @click="removeTextbook(row)" :icon="Delete">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 章节树 Drawer -->
    <el-drawer v-model="showChapterTreeDrawer" :title="selectedTextbook ? `[${selectedTextbook.textbook_name}] 章节管理` : '章节管理'" size="50%">
      <div class="drawer-header-actions">
        <el-button size="small" type="success" @click="downloadTemplate" :icon="Download">下载模板</el-button>
        <el-upload :show-file-list="false" :http-request="importChaptersExcel" accept=".xlsx,.xls">
          <el-button size="small" :icon="Upload">Excel导入章节</el-button>
        </el-upload>
        <el-button size="small" @click="openCreateChapter('root')" :icon="Plus">新增根章节</el-button>
        <el-button size="small" @click="openCreateChapter('child')" :icon="Plus">新增子章节</el-button>
        <el-button size="small" @click="openEditChapter" :icon="Edit">编辑</el-button>
        <el-button size="small" type="danger" @click="removeChapter" :icon="Delete">删除</el-button>
      </div>
      
      <el-tree
        :data="chapterTree"
        node-key="chapter_id"
        :props="{ label: 'chapter_name', children: 'children' }"
        highlight-current
        default-expand-all
        @node-click="handleNodeClick"
        class="chapter-tree"
      />
    </el-drawer>

    <!-- 章节概要 Dialog -->
    <el-dialog v-model="showSummaryDialog" :title="selectedChapter ? `[${selectedChapter.chapter_name}] 章节概要` : '章节概要'" width="600px">
      <div class="summaryBox">
        <div class="summaryHeader">
          <div></div>
          <div class="summaryActions">
            <el-button size="small" :loading="summaryLoading" @click="generateChapterSummary" :icon="MagicStick">AI生成</el-button>
            <el-button size="small" type="primary" :loading="summaryLoading" @click="saveChapterSummary" :icon="Check">保存</el-button>
          </div>
        </div>
        <el-input
          v-model="chapterSummary"
          type="textarea"
          :rows="12"
          placeholder="章节概要内容..."
        />
      </div>
    </el-dialog>

    <el-dialog v-model="textbookDialog.visible" :title="textbookDialog.mode === 'create' ? '新增教材' : '编辑教材'" width="520px">
      <el-form label-width="90px">
        <el-form-item label="科目">
          <el-select v-model="textbookDialog.form.subject_id" placeholder="选择科目" style="width: 100%">
            <el-option v-for="s in subjects" :key="s.subject_id" :label="s.subject_name" :value="s.subject_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="教材名称">
          <el-input v-model="textbookDialog.form.textbook_name" />
        </el-form-item>
        <el-form-item label="作者">
          <el-input v-model="textbookDialog.form.author" />
        </el-form-item>
        <el-form-item label="出版社">
          <el-input v-model="textbookDialog.form.publisher" />
        </el-form-item>
        <el-form-item label="版本">
          <el-input v-model="textbookDialog.form.edition" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="textbookDialog.visible = false">取消</el-button>
        <el-button type="primary" @click="submitTextbook">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="chapterDialog.visible" :title="chapterDialog.mode === 'create' ? '新增章节' : '编辑章节'" width="520px">
      <el-form label-width="90px">
        <el-form-item label="章节名称">
          <el-input v-model="chapterDialog.form.chapter_name" />
        </el-form-item>
        <el-form-item label="层级">
          <el-input-number v-model="chapterDialog.form.chapter_level" :min="1" :max="10" style="width: 100%" />
        </el-form-item>
        <el-form-item label="父章节ID">
          <el-input-number v-model="chapterDialog.form.parent_chapter_id" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="chapterDialog.form.chapter_sort" :min="1" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="chapterDialog.visible = false">取消</el-button>
        <el-button type="primary" @click="submitChapter">保存</el-button>
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
  align-items: center;
  justify-content: space-between;
}

.left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.card {
  width: 100%;
}

.placeholder {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.cardHeader {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.actions {
  display: flex;
  gap: 8px;
}

.summaryBox {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.summaryHeader {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.summaryActions {
  display: flex;
  gap: 8px;
}

.drawer-header-actions {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.chapter-tree {
  border: 1px solid var(--el-border-color);
  padding: 10px;
  border-radius: 4px;
}
</style>
