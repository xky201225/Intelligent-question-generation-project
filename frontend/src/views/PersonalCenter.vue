<script setup>
import { ref, reactive, computed, h, onMounted } from 'vue'
import { useMessage, useDialog, NButton, NTag, NIcon } from 'naive-ui'
import { SearchOutline, EyeOutline, ExpandOutline, CheckmarkOutline, TrashOutline, ReorderFourOutline, FunnelOutline, CaretDownOutline } from '@vicons/ionicons5'
import { http } from '../api/http'
import { getUser } from '../auth'
import ExportPreview from '../components/ExportPreview.vue'

const message = useMessage()
const dialog = useDialog()
const user = getUser()
const reviewer = user ? user.name : ''

const activeTab = ref('questions')

const qLoading = ref(false)
const qError = ref('')
const qFilter = reactive({
  q: '',
  subject_id: null,
  textbook_id: null,
  chapter_id: [],
  type_id: [],
  difficulty_id: [],
  page: 1,
  page_size: 20
})
const qData = reactive({ items: [], total: 0 })
const checkedQIds = ref([])
const filterCollapsed = ref(true)
const paperFilterCollapsed = ref(true)

const subjects = ref([])
const difficulties = ref([])
const textbooks = ref([])
const paperTextbooks = ref([])
const chapters = ref([])
const chapterTree = ref([])
const selectedMainChapters = ref([])

async function loadMyQuestions() {
  qLoading.value = true
  qError.value = ''
  try {
    const params = {
      reviewer,
      q: qFilter.q || undefined,
      subject_id: qFilter.subject_id || undefined,
      textbook_id: qFilter.textbook_id || undefined,
      chapter_id: Array.isArray(qFilter.chapter_id) && qFilter.chapter_id.length > 0 ? qFilter.chapter_id.join(',') : undefined,
      type_id: Array.isArray(qFilter.type_id) && qFilter.type_id.length > 0 ? qFilter.type_id.join(',') : undefined,
      difficulty_id: Array.isArray(qFilter.difficulty_id) && qFilter.difficulty_id.length > 0 ? qFilter.difficulty_id.join(',') : undefined,
      page: qFilter.page,
      page_size: qFilter.page_size
    }
    const resp = await http.get('/questions', { params })
    qData.items = resp.data.items || []
    qData.total = resp.data.total || 0
  } catch (e) {
    qError.value = e?.message || '加载失败'
  } finally {
    qLoading.value = false
  }
}

const qDialog = reactive({
  visible: false,
  form: {
    question_id: null,
    subject_id: null,
    chapter_id: null,
    type_id: null,
    difficulty_id: null,
    question_content: '',
    question_answer: '',
    question_analysis: '',
    question_score: null
  }
})

const types = ref([])
const typeOptions = computed(() => types.value.map(t => ({ label: t.type_name, value: t.type_id })))
const subjectOptions = computed(() => subjects.value.map(s => ({ label: s.subject_name, value: s.subject_id })))
const difficultyOptions = computed(() => difficulties.value.map(d => ({ label: d.difficulty_name, value: d.difficulty_id })))

// Dialog textbook/chapter resources
const dialogTextbookId = ref(null)
const dialogTextbooks = ref([])
const dialogChapterTree = ref([])
const dialogTextbookOptions = computed(() => dialogTextbooks.value.map(t => ({ label: t.textbook_name + (t.author ? '-' + t.author : ''), value: t.textbook_id })))

async function loadDialogTextbooks() {
  const resp = await http.get('/textbooks', {
    params: qDialog.form.subject_id ? { subject_id: qDialog.form.subject_id } : {},
  })
  dialogTextbooks.value = resp.data.items || []
}

async function loadDialogChapters() {
  if (!dialogTextbookId.value) {
    dialogChapterTree.value = []
    return
  }
  const resp = await http.get(`/textbooks/${dialogTextbookId.value}/chapters`)
  dialogChapterTree.value = resp.data.tree || []
}

function treeToOptions(tree) {
  return tree.map(node => ({
    label: node.chapter_name,
    value: node.chapter_id,
    children: node.children && node.children.length > 0 ? treeToOptions(node.children) : undefined
  }))
}
const dialogChapterCascaderOptions = computed(() => treeToOptions(dialogChapterTree.value))
async function loadDicts() {
  const [s, t, d] = await Promise.all([
    http.get('/dicts/subjects'),
    http.get('/dicts/question-types'),
    http.get('/dicts/difficulties')
  ])
  subjects.value = s.data.items || []
  types.value = t.data.items || []
  difficulties.value = d.data.items || []
}

async function loadTextbooks() {
  if (!qFilter.subject_id) {
    textbooks.value = []
    chapterTree.value = []
    return
  }
  const resp = await http.get('/textbooks', { params: { subject_id: qFilter.subject_id } })
  textbooks.value = resp.data.items || []
  chapterTree.value = []
}

async function loadPaperTextbooks() {
  if (!paperFilter.subject_id) {
    paperTextbooks.value = []
    return
  }
  const resp = await http.get('/textbooks', { params: { subject_id: paperFilter.subject_id } })
  paperTextbooks.value = resp.data.items || []
}

async function loadChapters() {
  if (!qFilter.textbook_id) {
    chapters.value = []
    chapterTree.value = []
    return
  }
  const resp = await http.get(`/textbooks/${qFilter.textbook_id}/chapters`)
  chapters.value = resp.data.items || []
  chapterTree.value = resp.data.tree || []
}

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

function toggleMainChapter(chapter) {
  const idx = selectedMainChapters.value.indexOf(chapter.chapter_id)
  if (idx >= 0) {
    selectedMainChapters.value.splice(idx, 1)
    if (chapter.children && chapter.children.length > 0) {
      const childIds = chapter.children.map(c => c.chapter_id)
      qFilter.chapter_id = qFilter.chapter_id.filter(id => !childIds.includes(id))
    }
  } else {
    selectedMainChapters.value.push(chapter.chapter_id)
    if (chapter.children && chapter.children.length > 0) {
      for (const child of chapter.children) {
        if (!qFilter.chapter_id.includes(child.chapter_id)) {
          qFilter.chapter_id.push(child.chapter_id)
        }
      }
    }
  }
  loadMyQuestions()
}

function toggleSubChapter(chapterId) {
  const idx = qFilter.chapter_id.indexOf(chapterId)
  if (idx >= 0) {
    qFilter.chapter_id.splice(idx, 1)
  } else {
    qFilter.chapter_id.push(chapterId)
  }
  loadMyQuestions()
}

function toggleTypeId(typeId) {
  const idx = qFilter.type_id.indexOf(typeId)
  if (idx >= 0) {
    qFilter.type_id.splice(idx, 1)
  } else {
    qFilter.type_id.push(typeId)
  }
  loadMyQuestions()
}

function toggleDifficultyId(difficultyId) {
  const idx = qFilter.difficulty_id.indexOf(difficultyId)
  if (idx >= 0) {
    qFilter.difficulty_id.splice(idx, 1)
  } else {
    qFilter.difficulty_id.push(difficultyId)
  }
  loadMyQuestions()
}

function getDifficultyClass(difficultyId, difficultyName) {
  const selected = qFilter.difficulty_id.includes(difficultyId)
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

function openQEdit(row) {
  qDialog.form = {
    question_id: row.question_id,
    subject_id: row.subject_id,
    chapter_id: row.chapter_id,
    type_id: row.type_id,
    difficulty_id: row.difficulty_id,
    question_content: row.question_content,
    question_answer: row.question_answer,
    question_analysis: row.question_analysis,
    question_score: row.question_score
  }
  dialogTextbookId.value = null
  dialogTextbooks.value = []
  dialogChapterTree.value = []
  // 推断教材：根据章节获取所属教材
  ;(async () => {
    try {
      if (row.chapter_id) {
        const meta = await http.get(`/textbooks/chapters/${row.chapter_id}`)
        dialogTextbookId.value = meta.data?.item?.textbook_id || null
        qDialog.form.subject_id = row.subject_id
        await loadDialogTextbooks()
        await loadDialogChapters()
      }
    } catch {}
  })()
  qDialog.visible = true
}

async function saveQ() {
  try {
    await http.put(`/questions/${qDialog.form.question_id}`, { ...qDialog.form })
    message.success('已保存')
    qDialog.visible = false
    await loadMyQuestions()
  } catch (e) {
    message.error(e?.message || '保存失败')
  }
}

async function removeQ(row) {
  dialog.warning({
    title: '提示',
    content: `确认删除题目ID=${row.question_id}？`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await http.delete(`/questions/${row.question_id}`)
        message.success('删除成功')
        await loadMyQuestions()
      } catch (e) {
        message.error(e?.message || '删除失败')
      }
    }
  })
}

const detailDialog = reactive({
  visible: false,
  item: null
})
function openDetail(row) {
  detailDialog.item = row
  detailDialog.visible = true
}

const qColumns = [
  { type: 'selection' },
  { title: 'ID', key: 'question_id', width: 80 },
  { title: '科目', key: 'subject_name', width: 120 },
  { title: '章节', key: 'chapter_name', width: 180, ellipsis: { tooltip: true } },
  { title: '题型', key: 'type_name', width: 100 },
  { title: '难度', key: 'difficulty_name', width: 80 },
  { title: '状态', key: 'review_status', width: 90, render(row) {
    if (row.review_status === 1) return h(NTag, { type: 'success' }, { default: () => '已通过' })
    if (row.review_status === 2) return h(NTag, { type: 'error' }, { default: () => '未通过' })
    return h(NTag, { type: 'warning' }, { default: () => '待审核' })
  }},
  {
    title: '题干',
    key: 'question_content',
    ellipsis: { tooltip: true },
    render(row) {
      return h('div', {
        style: { cursor: 'pointer', color: 'var(--n-text-color)' },
        onClick: () => openDetail(row)
      }, row.question_content?.substring(0, 100))
    }
  },
  { title: '操作', key: 'actions', width: 140, render(row) {
    return h('div', { style: { display: 'flex', gap: '6px' } }, [
      h(NButton, { size: 'small', onClick: () => openQEdit(row) }, { default: () => '编辑' }),
      h(NButton, { size: 'small', type: 'error', onClick: () => removeQ(row) }, { default: () => '删除' })
    ])
  }}
]

async function batchDeleteQuestions() {
  if (checkedQIds.value.length === 0) return
  dialog.warning({
    title: '提示',
    content: `确认删除选中的 ${checkedQIds.value.length} 个题目？`,
    positiveText: '确认删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await http.post('/questions/batch-delete', { ids: checkedQIds.value })
        message.success('批量删除成功')
        checkedQIds.value = []
        await loadMyQuestions()
      } catch (e) {
        message.error(e?.message || '操作失败')
      }
    }
  })
}

const pLoading = ref(false)
const pError = ref('')
const papers = ref([])
const selectedPaperId = ref(null)
const paper = ref(null)
const questions = ref([])
const showPaperDrawer = ref(false)
const isDrawerFullscreen = ref(false)
const showPreview = ref(false)
const paperFilter = reactive({
  subject_id: null,
  textbook_id: null
})

async function loadMyPapers() {
  pLoading.value = true
  pError.value = ''
  try {
    const params = {
      reviewer,
      include_export_count: 1
    }
    if (paperFilter.subject_id) params.subject_id = paperFilter.subject_id
    if (paperFilter.textbook_id) params.textbook_id = paperFilter.textbook_id
    const resp = await http.get('/papers', { params })
    papers.value = resp.data.items || []
  } catch (e) {
    pError.value = e?.message || '加载失败'
  } finally {
    pLoading.value = false
  }
}

async function loadPaperDetail(paperId) {
  if (!paperId) {
    paper.value = null
    questions.value = []
    return
  }
  pLoading.value = true
  pError.value = ''
  try {
    const resp = await http.get(`/papers/${paperId}`)
    paper.value = resp.data.paper
    questions.value = resp.data.questions || []
    paperForm.paper_name = paper.value.paper_name || ''
    paperForm.paper_desc = paper.value.paper_desc || ''
    paperForm.exam_duration = paper.value.exam_duration
    showPaperDrawer.value = true
  } catch (e) {
    pError.value = e?.message || '加载失败'
  } finally {
    pLoading.value = false
  }
}

const tableColumns = [
  { title: 'ID', key: 'paper_id', width: 90 },
  { title: '名称', key: 'paper_name' },
  { title: '状态', key: 'review_status', width: 100, render(row) {
    if (row.review_status === 1) return h(NTag, { type: 'success' }, { default: () => '已通过' })
    if (row.review_status === 2) return h(NTag, { type: 'error' }, { default: () => '未通过' })
    return h(NTag, { type: 'warning' }, { default: () => '待审核' })
  }},
  { title: '审核时间', key: 'review_time', width: 160, render(row) {
    return row.review_time ? new Date(row.review_time).toLocaleString() : '-'
  }},
  { title: '下载量', key: 'export_count', width: 90 },
  { title: '操作', key: 'actions', width: 120, render(row) {
    return h(NButton, { size: 'small', onClick: () => { selectedPaperId.value = row.paper_id; loadPaperDetail(row.paper_id) } }, { default: () => '编辑/导出' })
  }}
]

function normalizeSort() {
  const arr = [...questions.value]
  arr.sort((a, b) => (a.question_sort || 0) - (b.question_sort || 0))
  arr.forEach((q, idx) => { q.question_sort = idx + 1 })
  questions.value = arr
}

async function saveQuestions() {
  if (!selectedPaperId.value) return
  try {
    normalizeSort()
    await http.put(`/papers/${selectedPaperId.value}/questions`, {
      items: questions.value.map(q => ({ question_id: q.question_id, question_sort: q.question_sort, question_score: q.question_score }))
    })
    message.success('已保存题目顺序/分值')
    await loadPaperDetail(selectedPaperId.value)
  } catch (e) {
    message.error(e?.message || '保存失败')
  }
}

const paperForm = reactive({
  paper_name: '',
  paper_desc: '',
  exam_duration: null,
  is_closed_book: null
})

async function savePaper() {
  if (!selectedPaperId.value) return
  try {
    await http.put(`/papers/${selectedPaperId.value}`, { ...paperForm })
    message.success('已保存')
    await loadPaperDetail(selectedPaperId.value)
    await loadMyPapers()
  } catch (e) {
    message.error(e?.message || '保存失败')
  }
}

onMounted(async () => {
  try {
    await loadDicts()
  } catch {}
  await loadMyQuestions()
  await loadPaperTextbooks()
  await loadMyPapers()
})
</script>

<template>
  <div class="page">
    <n-tabs v-model:value="activeTab" type="line">
      <n-tab-pane name="questions" tab="我审核的题目">
        <n-card>
          <template #header>
            <div class="header">
              <div>题目列表</div>
              <div class="actions">
                <n-button type="error" :disabled="checkedQIds.length === 0" @click="batchDeleteQuestions">
                  <template #icon><n-icon><TrashOutline /></n-icon></template>
                  批量删除
                </n-button>
              </div>
            </div>
          </template>
          <div class="filter-section">
            <div class="filter-section-header filter-section-toggle" @click="filterCollapsed = !filterCollapsed">
              <n-icon size="16" color="#64748b"><FunnelOutline /></n-icon>
              <span>条件筛选</span>
              <n-icon size="16" style="margin-left: 4px;transition:transform 0.2s;" :style="{transform: filterCollapsed ? 'rotate(-90deg)' : 'rotate(0deg)'}"><CaretDownOutline /></n-icon>
            </div>
            <template v-if="!filterCollapsed">
              <div class="filter-row">
                <div class="filter-label">关键词</div>
                <div class="filter-content">
                  <n-input v-model:value="qFilter.q" placeholder="题干/解析" style="width: 200px" clearable @keyup.enter="loadMyQuestions" />
                </div>
              </div>

              <div class="filter-row">
                <div class="filter-label">科目</div>
                <div class="filter-content filter-tags">
                  <n-tag
                    v-for="s in subjects"
                    :key="s.subject_id"
                    :bordered="false"
                    :class="['filter-tag', qFilter.subject_id === s.subject_id ? 'tag-selected' : '']"
                    @click="async () => {
                      qFilter.subject_id = qFilter.subject_id === s.subject_id ? null : s.subject_id;
                      qFilter.textbook_id = null;
                      qFilter.chapter_id = [];
                      selectedMainChapters.value = [];
                      await loadTextbooks();
                      await loadMyQuestions()
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
                      :class="['filter-tag', qFilter.textbook_id === t.textbook_id ? 'tag-selected' : '']"
                      @click="async () => {
                        qFilter.textbook_id = qFilter.textbook_id === t.textbook_id ? null : t.textbook_id;
                        qFilter.chapter_id = [];
                        selectedMainChapters.value = [];
                        await loadChapters()
                      await loadMyQuestions()
                      }"
                    >
                      {{ t.textbook_name }}{{ t.author ? ' - ' + t.author : '' }}
                    </n-tag>
                  </template>
                  <span v-else class="empty-hint">{{ qFilter.subject_id ? '暂无教材' : '请先选择科目' }}</span>
                </div>
              </div>

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
                  <span v-else class="empty-hint">{{ qFilter.textbook_id ? '暂无章节' : '请先选择教材' }}</span>
                </div>
              </div>

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
                          :class="['filter-tag', 'chapter-sub', qFilter.chapter_id.includes(sub.chapter_id) ? 'chapter-sub-selected' : '']"
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
                    :class="['filter-tag', qFilter.type_id.includes(t.type_id) ? 'tag-selected' : '']"
                    @click="toggleTypeId(t.type_id)"
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
                    @click="toggleDifficultyId(d.difficulty_id)"
                  >
                    {{ d.difficulty_name }}
                  </n-tag>
                  <n-button size="small" style="margin-left: 12px" @click="loadMyQuestions">
                    <template #icon><n-icon><SearchOutline /></n-icon></template>
                    查询
                  </n-button>
                </div>
              </div>
            </template>
          </div>
          <n-data-table
            :columns="qColumns"
            :data="qData.items"
            :loading="qLoading"
            :row-key="row => row.question_id"
            v-model:checked-row-keys="checkedQIds"
            :max-height="560"
          />
          <div class="pager">
            <n-pagination
              v-model:page="qFilter.page"
              v-model:page-size="qFilter.page_size"
              :item-count="qData.total"
              :page-sizes="[10,20,50,100]"
              show-size-picker
              @update:page="loadMyQuestions"
              @update:page-size="() => { qFilter.page = 1; loadMyQuestions() }"
            />
          </div>
        </n-card>

        <n-modal v-model:show="qDialog.visible" preset="card" title="编辑题目" style="width: 720px">
          <n-form label-placement="left" label-width="90px">
            <n-form-item label="科目">
              <n-select
                v-model:value="qDialog.form.subject_id"
                :options="subjectOptions"
                placeholder="科目"
                filterable
                @update:value="async () => {
                  dialogTextbookId.value = null
                  qDialog.form.chapter_id = null
                  dialogChapterTree.value = []
                  await loadDialogTextbooks()
                }"
              />
            </n-form-item>
            <n-form-item label="教材">
              <n-select
                v-model:value="dialogTextbookId"
                :options="dialogTextbookOptions"
                placeholder="教材"
                filterable
                clearable
                @update:value="async () => {
                  qDialog.form.chapter_id = null
                  await loadDialogChapters()
                }"
              />
            </n-form-item>
            <n-form-item label="章节">
              <n-cascader
                v-model:value="qDialog.form.chapter_id"
                :options="dialogChapterCascaderOptions"
                check-strategy="child"
                clearable
                placeholder="章节"
                :disabled="!dialogTextbookId"
              />
            </n-form-item>
            <n-form-item label="题型">
              <n-select v-model:value="qDialog.form.type_id" :options="typeOptions" placeholder="题型" filterable />
            </n-form-item>
            <n-form-item label="难度">
              <n-select v-model:value="qDialog.form.difficulty_id" :options="difficultyOptions" placeholder="难度" filterable />
            </n-form-item>
            <n-form-item label="题干">
              <n-input v-model:value="qDialog.form.question_content" type="textarea" :rows="5" />
            </n-form-item>
            <n-form-item label="答案">
              <n-input v-model:value="qDialog.form.question_answer" type="textarea" :rows="2" />
            </n-form-item>
            <n-form-item label="解析">
              <n-input v-model:value="qDialog.form.question_analysis" type="textarea" :rows="3" />
            </n-form-item>
            <n-form-item label="分值">
              <n-input-number v-model:value="qDialog.form.question_score" :min="0" :step="0.5" style="width: 100%" />
            </n-form-item>
          </n-form>
          <template #footer>
            <div style="display:flex;justify-content:flex-end;gap:8px;">
              <n-button @click="qDialog.visible = false">取消</n-button>
              <n-button type="primary" @click="saveQ">保存</n-button>
            </div>
          </template>
        </n-modal>

        <n-modal v-model:show="detailDialog.visible" preset="card" title="题目详情" style="width: 600px">
          <div v-if="detailDialog.item">
            <n-descriptions :column="1" bordered>
              <n-descriptions-item label="题干">
                <div style="white-space: pre-wrap">{{ detailDialog.item.question_content }}</div>
              </n-descriptions-item>
              <n-descriptions-item label="答案">
                <div style="white-space: pre-wrap">{{ detailDialog.item.question_answer }}</div>
              </n-descriptions-item>
              <n-descriptions-item label="解析">
                <div style="white-space: pre-wrap">{{ detailDialog.item.question_analysis }}</div>
              </n-descriptions-item>
            </n-descriptions>
          </div>
          <template #footer>
            <n-button @click="detailDialog.visible = false">关闭</n-button>
          </template>
        </n-modal>
      </n-tab-pane>

      <n-tab-pane name="papers" tab="我审核的试卷">
        <n-card>
          <template #header>
            <div class="header">
              <div>试卷列表</div>
            </div>
          </template>
          <div class="filter-section">
            <div class="filter-section-header filter-section-toggle" @click="paperFilterCollapsed = !paperFilterCollapsed">
              <n-icon size="16" color="#64748b"><FunnelOutline /></n-icon>
              <span>条件筛选</span>
              <n-icon size="16" style="margin-left: 4px;transition:transform 0.2s;" :style="{transform: paperFilterCollapsed ? 'rotate(-90deg)' : 'rotate(0deg)'}"><CaretDownOutline /></n-icon>
            </div>
            <template v-if="!paperFilterCollapsed">
              <div class="filter-row">
                <div class="filter-label">科目</div>
                <div class="filter-content filter-tags">
                  <n-tag
                    v-for="s in subjects"
                    :key="s.subject_id"
                    :bordered="false"
                    :class="['filter-tag', paperFilter.subject_id === s.subject_id ? 'tag-selected' : '']"
                    @click="async () => {
                      paperFilter.subject_id = paperFilter.subject_id === s.subject_id ? null : s.subject_id;
                      paperFilter.textbook_id = null;
                      await loadPaperTextbooks();
                      await loadMyPapers()
                    }"
                  >
                    {{ s.subject_name }}
                  </n-tag>
                </div>
              </div>

              <div class="filter-row">
                <div class="filter-label">教材</div>
                <div class="filter-content filter-tags">
                  <template v-if="paperTextbooks.length > 0">
                    <n-tag
                      v-for="t in paperTextbooks"
                      :key="t.textbook_id"
                      :bordered="false"
                      :class="['filter-tag', paperFilter.textbook_id === t.textbook_id ? 'tag-selected' : '']"
                      @click="async () => {
                        paperFilter.textbook_id = paperFilter.textbook_id === t.textbook_id ? null : t.textbook_id;
                        await loadMyPapers()
                      }"
                    >
                      {{ t.textbook_name }}{{ t.author ? ' - ' + t.author : '' }}
                    </n-tag>
                  </template>
                  <span v-else class="empty-hint">{{ paperFilter.subject_id ? '暂无教材' : '请先选择科目' }}</span>
                </div>
              </div>
            </template>
          </div>
          <n-data-table
            :columns="tableColumns"
            :data="papers"
            :loading="pLoading"
            :row-key="row => row.paper_id"
            :max-height="620"
          />
        </n-card>

        <n-drawer v-model:show="showPaperDrawer" :width="isDrawerFullscreen ? '100%' : 800" placement="right">
          <n-drawer-content>
            <template #header>
              <div style="display:flex;justify-content:space-between;align-items:center;width:100%;">
                <span>试卷编辑与导出</span>
                <div class="header-actions">
                  <n-button :disabled="!selectedPaperId || paper?.review_status !== 1" size="small" @click="showPreview = true">
                    <template #icon><n-icon><EyeOutline /></n-icon></template>
                    导出预览
                  </n-button>
                  <n-button text @click="isDrawerFullscreen = !isDrawerFullscreen">
                    <template #icon><n-icon><ExpandOutline /></n-icon></template>
                  </n-button>
                </div>
              </div>
            </template>

            <div v-if="paper" class="detail">
              <n-form label-placement="left" label-width="90px" class="paperForm">
                <n-form-item label="试卷名称">
                  <n-input v-model:value="paperForm.paper_name" />
                </n-form-item>
                <n-form-item label="考试时长">
                  <n-input-number v-model:value="paperForm.exam_duration" :min="0" style="width: 100%" />
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
                <div v-for="(q, index) in questions" :key="q.question_id" class="question-card">
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
            </div>
          </n-drawer-content>
        </n-drawer>

        <ExportPreview v-model:visible="showPreview" :paper="paper" :questions="questions" />
      </n-tab-pane>
    </n-tabs>
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
.actions {
  display: flex;
  gap: 10px;
  align-items: center;
}
.hint {
  font-size: 12px;
  color: var(--n-text-color-3);
}
.filter-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  background: var(--n-color-embedded);
  border-radius: 12px;
  margin-bottom: 16px;
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
  line-height: 1;
}
.filter-section-toggle {
  cursor: pointer;
  user-select: none;
  display: flex;
  align-items: center;
  min-height: 32px;
  padding: 6px 8px;
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
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
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
}
.q-main { flex: 1; }
.q-content { font-size: 14px; line-height: 1.5; white-space: pre-wrap; }
.q-id { font-weight: bold; color: var(--n-primary-color); margin-right: 5px; }
.q-controls { display: flex; gap: 20px; align-items: center; padding: 8px; border-radius: 4px; }
.control-item { display: flex; align-items: center; gap: 8px; }
.label { font-size: 12px; color: var(--n-text-color-3); }
.inlineActions { display: flex; align-items: center; justify-content: space-between; }
.subTitle { font-weight: 600; display: flex; align-items: center; }
.drag-hint { font-size: 12px; font-weight: normal; color: var(--n-text-color-3); margin-left: 12px; display: inline-flex; align-items: center; gap: 4px; }
</style>
