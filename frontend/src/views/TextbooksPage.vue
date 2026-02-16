<script setup>
import { computed, onMounted, reactive, ref, watch, h } from 'vue'
import { useMessage, useDialog } from 'naive-ui'
import { RefreshOutline, AddOutline, SettingsOutline, CreateOutline, TrashOutline, CloudUploadOutline, SparklesOutline, CheckmarkOutline, CloseOutline, DownloadOutline } from '@vicons/ionicons5'
import { http } from '../api/http'

const message = useMessage()
const dialog = useDialog()
const loading = ref(false)
const error = ref('')

const subjects = ref([])
const filter = reactive({ subject_id: null })

const textbooks = ref([])
const selectedTextbook = ref(null)

const filterTextbookId = ref(null)
const selectedPublisher = ref(null)

const filteredTextbooks = computed(() => {
  return textbooks.value.filter(t => {
    const matchId = !filterTextbookId.value || t.textbook_id === filterTextbookId.value
    const matchPub = !selectedPublisher.value || t.publisher === selectedPublisher.value
    return matchId && matchPub
  })
})

// 用于表格显示的教材列表（选中单个教材时只显示该教材）
const displayedTextbooks = computed(() => {
  if (filterTextbookId.value) {
    return filteredTextbooks.value.filter(t => t.textbook_id === filterTextbookId.value)
  }
  return filteredTextbooks.value
})

const publisherOptions = computed(() => {
  const set = new Set()
  for (const t of textbooks.value) {
    if (t.publisher) set.add(t.publisher)
  }
  return Array.from(set).map(p => ({ label: p, value: p }))
})

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
    message.error(e?.message || '概要加载失败')
  } finally {
    summaryLoading.value = false
  }
}

async function saveChapterSummary() {
  if (!selectedChapterId.value) {
    message.warning('请先选择一个章节节点')
    return
  }
  summaryLoading.value = true
  try {
    await http.put(`/textbooks/chapters/${selectedChapterId.value}/summary`, {
      summary: chapterSummary.value,
    })
    message.success('已保存')
  } catch (e) {
    message.error(e?.message || '保存失败')
  } finally {
    summaryLoading.value = false
  }
}

async function generateChapterSummary() {
  if (!selectedChapterId.value) {
    message.warning('请先选择一个章节节点')
    return
  }
  summaryLoading.value = true
  try {
    const resp = await http.post(`/textbooks/chapters/${selectedChapterId.value}/summary/generate`)
    chapterSummary.value = resp.data.summary || ''
    message.success('已生成')
  } catch (e) {
    message.error(e?.message || '生成失败')
  } finally {
    summaryLoading.value = false
  }
}

async function importChaptersExcel({ file }) {
  if (!selectedTextbook.value) {
    message.warning('请先选择一个教材')
    return
  }
  const form = new FormData()
  form.append('file', file.file)
  try {
    const resp = await http.post(`/textbooks/${selectedTextbook.value.textbook_id}/chapters/import/excel`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    message.success(`导入完成：新增${resp.data.inserted}，跳过${resp.data.skipped}`)
    await loadChapters(selectedTextbook.value.textbook_id)
  } catch (e) {
    message.error(e?.message || '导入失败')
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
    message.error(e?.message || '章节加载失败')
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
      message.error('subject_id 和教材名称必填')
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
    message.error(e?.message || '保存失败')
  }
}

async function removeTextbook(row) {
  dialog.warning({
    title: '提示',
    content: `确认删除教材：${row.textbook_name}？`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await http.delete(`/textbooks/${row.textbook_id}`)
        if (selectedTextbook.value?.textbook_id === row.textbook_id) {
          selectedTextbook.value = null
          await loadChapters(null)
        }
        await loadTextbooks()
      } catch (e) {
        message.error(e?.message || '删除失败')
      }
    }
  })
}

function openCreateChapter(mode) {
  if (!selectedTextbook.value) {
    message.warning('请先选择一个教材')
    return
  }
  if (mode === 'child' && !selectedChapter.value) {
    message.warning('请先选择一个章节节点')
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
    message.warning('请先选择一个章节节点')
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
      message.error('章节名称与层级必填')
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
    message.error(e?.message || '保存失败')
  }
}

async function removeChapter() {
  if (!selectedChapter.value) {
    message.warning('请先选择一个章节节点')
    return
  }
  dialog.warning({
    title: '提示',
    content: `确认删除章节：${selectedChapter.value.chapter_name}？`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await http.delete(`/textbooks/chapters/${selectedChapter.value.chapter_id}`)
        await loadChapters(selectedTextbook.value.textbook_id)
      } catch (e) {
        message.error(e?.message || '删除失败')
      }
    }
  })
}

const showChapterTreeDrawer = ref(false)
const showSummaryDialog = ref(false)

async function handleSelectTextbook(row) {
  selectedTextbook.value = row
  await loadChapters(row?.textbook_id)
  showChapterTreeDrawer.value = true
}

async function handleNodeSelect(keys) {
  if (keys.length === 0) return
  selectedChapterId.value = keys[0]
  await loadChapterSummary(keys[0])
  showSummaryDialog.value = true
}

onMounted(async () => {
  await loadSubjects()
  await loadTextbooks()
})

const subjectOptions = computed(() => subjects.value.map(s => ({ label: s.subject_name, value: s.subject_id })))
const textbookOptions = computed(() => textbooks.value.map(t => ({ label: t.textbook_name + (t.author ? '-' + t.author : ''), value: t.textbook_id })))

const tableColumns = [
  { title: 'ID', key: 'textbook_id', width: 90 },
  {
    title: '名称',
    key: 'textbook_name',
    render(row) {
      return h('span', null, [
        row.textbook_name,
        row.author ? h('span', { style: { color: '#999', marginLeft: '4px' } }, `(${row.author})`) : null
      ])
    }
  },
  { title: '作者', key: 'author', width: 140 },
  { title: '出版社', key: 'publisher', width: 140 },
  {
    title: '操作',
    key: 'actions',
    width: 300,
    render(row) {
      return h('div', { style: { display: 'flex', gap: '8px' } }, [
        h('n-button', { size: 'small', onClick: () => handleSelectTextbook(row) }, { default: () => '管理章节' }),
        h('n-button', { size: 'small', onClick: () => openEditTextbook(row) }, { default: () => '编辑' }),
        h('n-button', { size: 'small', type: 'error', onClick: () => removeTextbook(row) }, { default: () => '删除' })
      ])
    }
  }
]
</script>

<template>
  <div class="page">
    <n-card title="教材列表">
      <template #header-extra>
        <div class="header-actions">
          <n-button :loading="loading" @click="loadTextbooks">
            <template #icon><n-icon><RefreshOutline /></n-icon></template>
            刷新
          </n-button>
          <n-button type="primary" @click="openCreateTextbook">
            <template #icon><n-icon><AddOutline /></n-icon></template>
            新增教材
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
              :class="['filter-tag', filter.subject_id === s.subject_id ? 'tag-selected' : '']"
              @click="() => { filter.subject_id = filter.subject_id === s.subject_id ? null : s.subject_id; filterTextbookId = null; loadTextbooks() }"
            >
              {{ s.subject_name }}
            </n-tag>
          </div>
        </div>

        <div class="filter-row" v-if="filteredTextbooks.length > 0">
          <div class="filter-label">教材</div>
          <div class="filter-content filter-tags">
            <n-tag
              v-for="t in filteredTextbooks.slice(0, 20)"
              :key="t.textbook_id"
              :bordered="false"
              :class="['filter-tag', filterTextbookId === t.textbook_id ? 'tag-selected' : '']"
              @click="() => { filterTextbookId = filterTextbookId === t.textbook_id ? null : t.textbook_id }"
            >
              {{ t.textbook_name }}{{ t.author ? ' - ' + t.author : '' }}
            </n-tag>
            <span v-if="filteredTextbooks.length > 20" class="more-hint">还有 {{ filteredTextbooks.length - 20 }} 个...</span>
          </div>
        </div>

        <div class="filter-row" v-if="publisherOptions.length > 0">
          <div class="filter-label">出版社</div>
          <div class="filter-content filter-tags">
            <n-tag
              v-for="p in publisherOptions"
              :key="p.value"
              :bordered="false"
              :class="['filter-tag', selectedPublisher === p.value ? 'tag-selected' : '']"
              @click="() => { selectedPublisher = selectedPublisher === p.value ? null : p.value }"
            >
              {{ p.label }}
            </n-tag>
          </div>
        </div>
      </div>

      <n-data-table
        :columns="tableColumns"
        :data="displayedTextbooks"
        :loading="loading"
        :max-height="500"
        striped
      />
    </n-card>

    <n-alert v-if="error" type="error" :title="error" />

    <!-- 章节树 Drawer -->
    <n-drawer v-model:show="showChapterTreeDrawer" :width="600">
      <n-drawer-content :title="selectedTextbook ? `[${selectedTextbook.textbook_name}] 章节管理` : '章节管理'">
        <div class="drawer-header-actions">
          <n-button size="small" @click="downloadTemplate">
            <template #icon><n-icon><DownloadOutline /></n-icon></template>
            下载模板
          </n-button>
          <n-upload :custom-request="importChaptersExcel" accept=".xlsx,.xls" :show-file-list="false">
            <n-button size="small">
              <template #icon><n-icon><CloudUploadOutline /></n-icon></template>
              Excel导入章节
            </n-button>
          </n-upload>
          <n-button size="small" @click="openCreateChapter('root')">
            <template #icon><n-icon><AddOutline /></n-icon></template>
            新增根章节
          </n-button>
          <n-button size="small" @click="openCreateChapter('child')">
            <template #icon><n-icon><AddOutline /></n-icon></template>
            新增子章节
          </n-button>
          <n-button size="small" @click="openEditChapter">
            <template #icon><n-icon><CreateOutline /></n-icon></template>
            编辑
          </n-button>
          <n-button size="small" type="error" @click="removeChapter">
            <template #icon><n-icon><TrashOutline /></n-icon></template>
            删除
          </n-button>
        </div>

        <n-tree
          :data="chapterTree"
          key-field="chapter_id"
          label-field="chapter_name"
          children-field="children"
          selectable
          default-expand-all
          @update:selected-keys="handleNodeSelect"
          class="chapter-tree"
        />
      </n-drawer-content>
    </n-drawer>

    <!-- 章节概要 Dialog -->
    <n-modal v-model:show="showSummaryDialog" preset="card" :title="selectedChapter ? `[${selectedChapter.chapter_name}] 章节概要` : '章节概要'" style="width: 600px">
      <div class="summaryBox">
        <div class="summaryHeader">
          <div></div>
          <div class="summaryActions">
            <n-button size="small" :loading="summaryLoading" @click="generateChapterSummary">
              <template #icon><n-icon><SparklesOutline /></n-icon></template>
              AI生成
            </n-button>
            <n-button size="small" type="primary" :loading="summaryLoading" @click="saveChapterSummary">
              <template #icon><n-icon><CheckmarkOutline /></n-icon></template>
              保存
            </n-button>
          </div>
        </div>
        <n-input
          v-model:value="chapterSummary"
          type="textarea"
          :rows="12"
          placeholder="章节概要内容..."
        />
      </div>
    </n-modal>

    <n-modal v-model:show="textbookDialog.visible" preset="card" :title="textbookDialog.mode === 'create' ? '新增教材' : '编辑教材'" style="width: 520px">
      <n-form label-placement="left" label-width="90px">
        <n-form-item label="科目">
          <n-select v-model:value="textbookDialog.form.subject_id" :options="subjectOptions" placeholder="选择科目" />
        </n-form-item>
        <n-form-item label="教材名称">
          <n-input v-model:value="textbookDialog.form.textbook_name" />
        </n-form-item>
        <n-form-item label="作者">
          <n-input v-model:value="textbookDialog.form.author" />
        </n-form-item>
        <n-form-item label="出版社">
          <n-input v-model:value="textbookDialog.form.publisher" />
        </n-form-item>
        <n-form-item label="版本">
          <n-input v-model:value="textbookDialog.form.edition" />
        </n-form-item>
      </n-form>
      <template #footer>
        <div style="display: flex; justify-content: flex-end; gap: 8px;">
          <n-button @click="textbookDialog.visible = false">取消</n-button>
          <n-button type="primary" @click="submitTextbook">保存</n-button>
        </div>
      </template>
    </n-modal>

    <n-modal v-model:show="chapterDialog.visible" preset="card" :title="chapterDialog.mode === 'create' ? '新增章节' : '编辑章节'" style="width: 520px">
      <n-form label-placement="left" label-width="90px">
        <n-form-item label="章节名称">
          <n-input v-model:value="chapterDialog.form.chapter_name" />
        </n-form-item>
        <n-form-item label="层级">
          <n-input-number v-model:value="chapterDialog.form.chapter_level" :min="1" :max="10" style="width: 100%" />
        </n-form-item>
        <n-form-item label="父章节ID">
          <n-input-number v-model:value="chapterDialog.form.parent_chapter_id" :min="1" style="width: 100%" />
        </n-form-item>
        <n-form-item label="排序">
          <n-input-number v-model:value="chapterDialog.form.chapter_sort" :min="1" style="width: 100%" />
        </n-form-item>
      </n-form>
      <template #footer>
        <div style="display: flex; justify-content: flex-end; gap: 8px;">
          <n-button @click="chapterDialog.visible = false">取消</n-button>
          <n-button type="primary" @click="submitChapter">保存</n-button>
        </div>
      </template>
    </n-modal>
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

.summaryBox {
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
  border: 1px solid var(--n-border-color);
  padding: 10px;
  border-radius: 4px;
}

.header-actions {
  display: flex;
  gap: 10px;
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

.more-hint {
  font-size: 12px;
  color: var(--n-text-color-3);
}
</style>
