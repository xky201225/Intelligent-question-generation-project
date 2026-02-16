<script setup>
import { onMounted, reactive, ref, computed, h } from 'vue'
import { useMessage, useDialog, NButton } from 'naive-ui'
import { CheckmarkOutline, TrashOutline, CreateOutline, RefreshOutline, CloseOutline, FunnelOutline, ExpandOutline } from '@vicons/ionicons5'
import { http } from '../api/http'
import { getUser } from '../auth'

const message = useMessage()
const dialog = useDialog()
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

const filterCollapsed = ref(true)

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
      review_status: 0,
    }
    const resp = await http.get('/ai/pending', { params })
    pending.items = resp.data.items || []
    pending.total = resp.data.total || 0
  } catch (e) {
    message.error(e?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function approveAll() {
  dialog.warning({
    title: '提示',
    content: '确定要通过所有待审核题目吗？',
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const user = getUser()
        const resp = await http.post('/ai/verify/batch', {
          action: 'approve_all_pending',
          reviewer: user ? user.name : 'reviewer',
        })
        message.success(`已批量通过 ${resp.data.count} 道题目`)
        await loadPending()
      } catch (e) {
        message.error(e?.message || '操作失败')
      }
    }
  })
}

async function remove(row) {
  dialog.warning({
    title: '提示',
    content: `确认删除题目ID=${row.question_id}？`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await http.delete(`/questions/${row.question_id}`)
        message.success('已删除')
        await loadPending()
      } catch (e) {
        message.error(e?.message || '操作失败')
      }
    }
  })
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
    message.success('已修改并通过')
    await loadPending()
  } catch (e) {
    message.error(e?.message || '操作失败')
  }
}

onMounted(async () => {
  await loadDicts()
  await loadPending()
})

const subjectOptions = computed(() => subjects.value.map(s => ({ label: s.subject_name, value: s.subject_id })))
const typeOptions = computed(() => types.value.map(t => ({ label: t.type_name, value: t.type_id })))
const textbookOptions = computed(() => textbooks.value.map(t => ({ label: t.textbook_name, value: t.textbook_id })))

function treeToOptions(tree) {
  return tree.map(node => ({
    label: node.chapter_name,
    value: node.chapter_id,
    children: node.children && node.children.length > 0 ? treeToOptions(node.children) : undefined
  }))
}
const chapterCascaderOptions = computed(() => treeToOptions(chapterTree.value))

const tableColumns = [
  { title: 'ID', key: 'question_id', width: 80 },
  { title: '科目', key: 'subject_name', width: 120 },
  { title: '章节', key: 'chapter_name', width: 150, ellipsis: { tooltip: true } },
  { title: '题型', key: 'type_name', width: 100 },
  { title: '难度', key: 'difficulty_name', width: 80 },
  {
    title: '题目内容',
    key: 'question_content',
    ellipsis: { tooltip: true },
    render(row) {
      return h('div', {
        style: { cursor: 'pointer' },
        onClick: () => openDetail(row)
      }, row.question_content?.substring(0, 80))
    }
  },
  {
    title: '操作',
    key: 'actions',
    width: 200,
    render(row) {
      return h('div', { style: { display: 'flex', gap: '4px' } }, [
        h(NButton, { size: 'small', onClick: () => openEdit(row) }, { default: () => '修改通过' }),
        h(NButton, { size: 'small', type: 'error', onClick: () => remove(row) }, { default: () => '删除' })
      ])
    }
  }
]

function handlePageChange(page) {
  pending.page = page
  loadPending()
}

function handlePageSizeChange(pageSize) {
  pending.page_size = pageSize
  pending.page = 1
  loadPending()
}
</script>

<template>
  <div class="page">
    <n-card>
      <template #header>
        <div class="header">
          <span>待校验题目</span>
          <div style="display: flex; gap: 8px">
            <n-button type="success" @click="approveAll">
              <template #icon><n-icon><CheckmarkOutline /></n-icon></template>
              一键全部通过
            </n-button>
            <n-button @click="loadPending">
              <template #icon><n-icon><RefreshOutline /></n-icon></template>
              刷新
            </n-button>
          </div>
        </div>
      </template>
      <div class="filter-section">
        <div class="filter-section-header filter-section-toggle" @click="filterCollapsed = !filterCollapsed">
          <n-icon size="16" color="#64748b"><FunnelOutline /></n-icon>
          <span>条件筛选</span>
          <n-icon size="16" style="margin-left: 4px;transition:transform 0.2s;" :style="{transform: filterCollapsed ? 'rotate(-90deg)' : 'rotate(0deg)'}"><ExpandOutline /></n-icon>
        </div>
        <template v-if="!filterCollapsed">
          <!-- 筛选区域：标签式布局 -->
          <div class="filter-row">
            <div class="filter-label">科目</div>
            <div class="filter-content filter-tags">
              <n-tag
                v-for="s in subjects"
                :key="s.subject_id"
                :bordered="false"
                :class="['filter-tag', pending.subject_id === s.subject_id ? 'tag-selected' : '']"
                @click="() => { pending.subject_id = pending.subject_id === s.subject_id ? null : s.subject_id; loadPending() }"
              >
                {{ s.subject_name }}
              </n-tag>
            </div>
          </div>
        </template>
      </div>

      <n-data-table
        :columns="tableColumns"
        :data="pending.items"
        :loading="loading"
        :max-height="500"
      />

      <div class="pager">
        <n-pagination
          v-model:page="pending.page"
          v-model:page-size="pending.page_size"
          :item-count="pending.total"
          :page-sizes="[10, 20, 50, 100]"
          show-size-picker
          @update:page="handlePageChange"
          @update:page-size="handlePageSizeChange"
        />
      </div>
    </n-card>

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

    <n-modal v-model:show="editDialog.visible" preset="card" title="修改并通过" style="width: 760px">
      <n-form label-placement="left" label-width="90px">
        <n-form-item label="教材章节">
          <div style="display: flex; gap: 8px; width: 100%">
            <n-select
              v-model:value="editDialog.form.textbook_id"
              :options="textbookOptions"
              placeholder="选择教材"
              style="flex: 1"
              @update:value="() => { editDialog.form.chapter_id = null; loadChapters(editDialog.form.textbook_id) }"
            />
            <n-cascader
              v-model:value="editDialog.form.chapter_id"
              :options="chapterCascaderOptions"
              check-strategy="child"
              placeholder="选择章节"
              style="flex: 1"
            />
          </div>
        </n-form-item>
        <n-form-item label="题型">
          <n-select v-model:value="editDialog.form.type_id" :options="typeOptions" placeholder="请选择题型" />
        </n-form-item>
        <n-form-item label="题干">
          <n-input v-model:value="editDialog.form.question_content" type="textarea" :rows="5" />
        </n-form-item>
        <n-form-item label="答案">
          <n-input v-model:value="editDialog.form.question_answer" type="textarea" :rows="2" />
        </n-form-item>
        <n-form-item label="解析">
          <n-input v-model:value="editDialog.form.question_analysis" type="textarea" :rows="3" />
        </n-form-item>
        <n-form-item label="分值">
          <n-input-number v-model:value="editDialog.form.question_score" :min="0" :step="0.5" style="width: 100%" />
        </n-form-item>
      </n-form>
      <template #footer>
        <div style="display: flex; justify-content: flex-end; gap: 8px;">
          <n-button @click="editDialog.visible = false">
            <template #icon><n-icon><CloseOutline /></n-icon></template>
            取消
          </n-button>
          <n-button type="primary" @click="updateAndApprove">
            <template #icon><n-icon><CheckmarkOutline /></n-icon></template>
            保存并通过
          </n-button>
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

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

/* 筛选区域样式 */
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
  font-size: 14px;
  font-weight: 600;
  color: var(--n-text-color-2);
  line-height: 28px;
  display: flex;
  align-items: center;
  cursor: pointer;
}

.filter-section-toggle {
  cursor: pointer;
  user-select: none;
  display: flex;
  align-items: center;
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

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
</style>