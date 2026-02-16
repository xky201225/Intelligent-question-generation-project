<script setup>
import { computed, onMounted, reactive, ref, watch, nextTick } from 'vue'
import { useMessage, useDialog, NButton } from 'naive-ui'
import { AddOutline, RefreshOutline, CreateOutline, TrashOutline, CheckmarkOutline, EyeOutline, DownloadOutline, SparklesOutline, FunnelOutline, ExpandOutline } from '@vicons/ionicons5'
import { http } from '../api/http'
import StylePreview from '../components/StylePreview.vue'
import { marked } from 'marked'
import { asBlob } from 'html-docx-js-typescript'
import { saveAs } from 'file-saver'
import { getToken } from '../auth'

const message = useMessage()
const dialog = useDialog()
const loading = ref(false)
const error = ref('')

const activeTab = ref('styles')
const types = ref([])
const styles = ref([])

const styleDialog = reactive({
  visible: false,
  mode: 'create',
  form: { style_id: null, type_id: null, style_name: '', style_config: '{}', is_default: 0 },
})

const papers = ref([])
const subjects = ref([])
const textbooks = ref([])
const filters = reactive({ subject_id: null, textbook_id: null })

const selectedPaperId = ref(null)
const sheets = ref([])
const selectedSheetId = ref(null)
const sheetItems = ref([])

const allStyleOptions = computed(() => styles.value.map(s => ({ label: `[${s.type_id}] ${s.style_name}`, value: s.style_id })))
const previewConfig = ref({})

watch(() => styleDialog.form.style_config, (val) => {
  try {
    const parsed = JSON.parse(val || '{}')
    if (parsed.style_config) {
      const inner = typeof parsed.style_config === 'string' ? JSON.parse(parsed.style_config) : parsed.style_config
      previewConfig.value = inner || {}
    } else {
      previewConfig.value = parsed
    }
  } catch {
    previewConfig.value = {}
  }
})

// AI Sheet Dialog
const aiSheetDialog = reactive({ visible: false, loading: false, content: '', htmlContent: '' })

async function openAiGenerateSheet() {
  if (!selectedPaperId.value) return
  aiSheetDialog.content = ''
  aiSheetDialog.htmlContent = ''
  aiSheetDialog.loading = true
  aiSheetDialog.visible = true
  
  const token = getToken()
  try {
    const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api'}/ai/generate-answer-sheet-preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ paper_id: selectedPaperId.value })
    })
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n\n')
      buffer = lines.pop()
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.substring(6))
            if (data.type === 'start' || data.type === 'delta') {
              aiSheetDialog.loading = false
              if (data.content) aiSheetDialog.content += data.content
              aiSheetDialog.htmlContent = marked.parse(aiSheetDialog.content)
            } else if (data.type === 'done') {
              aiSheetDialog.content = data.markdown
              aiSheetDialog.htmlContent = marked.parse(data.markdown)
            } else if (data.type === 'error') {
              message.error(data.message || '生成出错')
            }
          } catch {}
        }
      }
    }
  } catch (e) {
    message.error('生成失败')
  } finally {
    aiSheetDialog.loading = false
  }
}

async function downloadAiWord() {
  if (!aiSheetDialog.htmlContent) return
  try {
    const html = `<!DOCTYPE html><html><head><meta charset="UTF-8"><style>body{font-family:"SimSun",serif;}</style></head><body>${aiSheetDialog.htmlContent}</body></html>`
    const blob = await asBlob(html, { orientation: 'landscape' })
    saveAs(blob, 'AI答题卡.docx')
  } catch {
    message.error('下载失败')
  }
}

async function loadTypes() {
  const resp = await http.get('/dicts/question-types')
  types.value = resp.data.items || []
}

async function loadStyles() {
  const resp = await http.get('/answer-styles')
  styles.value = resp.data.items || []
}

function openCreateStyle() {
  styleDialog.mode = 'create'
  styleDialog.form = { style_id: null, type_id: null, style_name: '', style_config: '{}', is_default: 0 }
  styleDialog.visible = true
}

function openEditStyle(row) {
  styleDialog.mode = 'edit'
  styleDialog.form = { ...row }
  styleDialog.visible = true
}

async function submitStyle() {
  try {
    if (!styleDialog.form.type_id || !styleDialog.form.style_name) {
      message.error('题型与样式名称必填')
      return
    }
    let cleanConfig = styleDialog.form.style_config
    try {
      const parsed = JSON.parse(cleanConfig)
      if (parsed.style_config) {
        const inner = typeof parsed.style_config === 'string' ? JSON.parse(parsed.style_config) : parsed.style_config
        cleanConfig = JSON.stringify(inner)
      }
    } catch {}

    if (styleDialog.mode === 'create') {
      await http.post('/answer-styles', { type_id: styleDialog.form.type_id, style_name: styleDialog.form.style_name, style_config: cleanConfig, is_default: styleDialog.form.is_default })
    } else {
      await http.put(`/answer-styles/${styleDialog.form.style_id}`, { type_id: styleDialog.form.type_id, style_name: styleDialog.form.style_name, style_config: cleanConfig, is_default: styleDialog.form.is_default })
    }
    styleDialog.visible = false
    await loadStyles()
  } catch (e) {
    message.error(e?.message || '保存失败')
  }
}

async function removeStyle(row) {
  dialog.warning({
    title: '提示',
    content: `确认删除样式：${row.style_name}？`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await http.delete(`/answer-styles/${row.style_id}`)
        await loadStyles()
      } catch (e) {
        message.error(e?.message || '删除失败')
      }
    }
  })
}

async function loadSubjects() {
  const resp = await http.get('/dicts/subjects')
  subjects.value = resp.data.items || []
}

async function loadTextbooks() {
  const params = {}
  if (filters.subject_id) params.subject_id = filters.subject_id
  const resp = await http.get('/textbooks', { params })
  textbooks.value = resp.data.items || []
}

async function loadPapers() {
  const params = {}
  if (filters.subject_id) params.subject_id = filters.subject_id
  if (filters.textbook_id) params.textbook_id = filters.textbook_id
  const resp = await http.get('/papers', { params })
  papers.value = resp.data.items || []
}

async function loadSheets() {
  if (!selectedPaperId.value) { sheets.value = []; selectedSheetId.value = null; sheetItems.value = []; return }
  const resp = await http.get('/answer-sheets', { params: { paper_id: selectedPaperId.value } })
  sheets.value = resp.data.items || []
}

async function loadSheetItems() {
  if (!selectedSheetId.value) { sheetItems.value = []; return }
  const resp = await http.get(`/answer-sheets/${selectedSheetId.value}/items`)
  sheetItems.value = resp.data.items || []
}

async function buildSheetFromPaper() {
  if (!selectedPaperId.value) { message.warning('请选择试卷'); return }
  try {
    await http.post(`/answer-sheets/from-paper/${selectedPaperId.value}`, { create_user: 'creator' })
    message.success('已生成/刷新答题卡')
    await loadSheets()
  } catch (e) {
    message.error(e?.message || '生成失败')
  }
}

async function saveSheetItems() {
  if (!selectedSheetId.value) return
  try {
    await http.put(`/answer-sheets/${selectedSheetId.value}/items`, {
      items: sheetItems.value.map(it => ({ question_id: it.question_id, style_id: it.style_id, area_sort: it.area_sort, area_score: it.area_score }))
    })
    message.success('已保存')
    await loadSheetItems()
  } catch (e) {
    message.error(e?.message || '保存失败')
  }
}

onMounted(async () => {
  loading.value = true
  try {
    await loadTypes()
    await loadStyles()
    await loadSubjects()
    await loadTextbooks()
    await loadPapers()
  } catch (e) {
    error.value = e?.message || '加载失败'
  } finally {
    loading.value = false
  }
})

const subjectOptions = computed(() => subjects.value.map(s => ({ label: s.subject_name, value: s.subject_id })))
const textbookOptions = computed(() => textbooks.value.map(t => ({ label: t.textbook_name + (t.author ? '-' + t.author : ''), value: t.textbook_id })))
const paperOptions = computed(() => papers.value.map(p => ({ label: p.paper_name, value: p.paper_id })))
const typeOptions = computed(() => types.value.map(t => ({ label: t.type_name, value: t.type_id })))

const styleTableColumns = [
  { title: 'ID', key: 'style_id', width: 90 },
  { title: '题型ID', key: 'type_id', width: 100 },
  { title: '样式名称', key: 'style_name' },
  { title: '默认', key: 'is_default', width: 90 },
  {
    title: '操作', key: 'actions', width: 180,
    render(row) {
      return h('div', { style: { display: 'flex', gap: '4px' } }, [
        h(NButton, { size: 'small', onClick: () => openEditStyle(row) }, { default: () => '编辑' }),
        h(NButton, { size: 'small', type: 'error', onClick: () => removeStyle(row) }, { default: () => '删除' })
      ])
    }
  }
]

const sheetTableColumns = [
  { title: 'ID', key: 'sheet_id', width: 90 },
  { title: '名称', key: 'sheet_name' },
  { title: '试卷ID', key: 'paper_id', width: 100 }
]

const filterCollapsed = ref(true)

import { h } from 'vue'
</script>

<template>
  <div class="page">
    <n-alert v-if="error" type="error" :title="error" />

    <n-tabs v-model:value="activeTab">
      <n-tab-pane name="styles" tab="样式库">
        <div class="toolbar">
          <n-button type="primary" @click="openCreateStyle">
            <template #icon><n-icon><AddOutline /></n-icon></template>
            新增样式
          </n-button>
          <n-button @click="loadStyles">
            <template #icon><n-icon><RefreshOutline /></n-icon></template>
            刷新
          </n-button>
        </div>

        <n-data-table :columns="styleTableColumns" :data="styles" :max-height="620" />

        <n-modal v-model:show="styleDialog.visible" preset="card" :title="styleDialog.mode === 'create' ? '新增样式' : '编辑样式'" style="width: 900px">
          <div style="display: flex; gap: 20px;">
            <div style="flex: 1;">
              <n-form label-placement="left" label-width="90px">
                <n-form-item label="题型">
                  <n-select v-model:value="styleDialog.form.type_id" :options="typeOptions" placeholder="选择题型" />
                </n-form-item>
                <n-form-item label="名称">
                  <n-input v-model:value="styleDialog.form.style_name" />
                </n-form-item>
                <n-form-item label="默认">
                  <n-switch v-model:value="styleDialog.form.is_default" :checked-value="1" :unchecked-value="0" />
                </n-form-item>
                <n-form-item label="配置JSON">
                  <n-input v-model:value="styleDialog.form.style_config" type="textarea" :rows="15" />
                </n-form-item>
              </n-form>
            </div>
            <div style="width: 300px; border-left: 1px solid #eee; padding-left: 20px;">
              <div style="margin-bottom: 10px; font-weight: bold;">样式预览</div>
              <StylePreview :config="previewConfig" />
            </div>
          </div>
          <template #footer>
            <div style="display: flex; justify-content: flex-end; gap: 8px;">
              <n-button @click="styleDialog.visible = false">取消</n-button>
              <n-button type="primary" @click="submitStyle">保存</n-button>
            </div>
          </template>
        </n-modal>
      </n-tab-pane>

      <n-tab-pane name="sheets" tab="答题卡">
        <div class="grid">
          <n-card title="选择试卷与答题卡">
            <!-- 筛选区域：标签式布局 -->
            <div class="filter-section">
              <div class="filter-section-header filter-section-toggle" @click="filterCollapsed = !filterCollapsed">
                <n-icon size="16" color="#64748b"><FunnelOutline /></n-icon>
                <span>条件筛选</span>
                <n-icon size="16" style="margin-left: 4px;transition:transform 0.2s;" :style="{transform: filterCollapsed ? 'rotate(-90deg)' : 'rotate(0deg)'}"><ExpandOutline /></n-icon>
              </div>
              <template v-if="!filterCollapsed">
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

                <div class="filter-row" v-if="papers.length > 0">
                  <div class="filter-label">试卷</div>
                  <div class="filter-content filter-tags">
                    <n-tag
                      v-for="p in papers"
                      :key="p.paper_id"
                      :bordered="false"
                      :class="['filter-tag', selectedPaperId === p.paper_id ? 'tag-selected' : '']"
                      @click="async () => {
                        selectedPaperId = selectedPaperId === p.paper_id ? null : p.paper_id;
                        selectedSheetId = null;
                        await loadSheets()
                      }"
                    >
                      {{ p.paper_name }}
                    </n-tag>
                  </div>
                </div>
              </template>
            </div>

            <div class="toolbar">
              <n-button :disabled="!selectedPaperId" type="primary" @click="buildSheetFromPaper">
                <template #icon><n-icon><RefreshOutline /></n-icon></template>
                生成/刷新答题卡
              </n-button>
              <n-button :disabled="!selectedPaperId" type="warning" @click="openAiGenerateSheet">
                <template #icon><n-icon><SparklesOutline /></n-icon></template>
                AI生成答题卡
              </n-button>
            </div>

            <n-data-table
              :columns="sheetTableColumns"
              :data="sheets"
              :max-height="400"
              :row-props="row => ({ style: 'cursor: pointer', onClick: async () => { selectedSheetId = row.sheet_id; await loadSheetItems() } })"
            />
          </n-card>

          <n-card>
            <template #header>
              <div class="header">
                <div>题目-样式绑定</div>
                <div style="display: flex; gap: 8px;">
                  <n-button type="primary" :disabled="!selectedSheetId" @click="saveSheetItems">
                    <template #icon><n-icon><CheckmarkOutline /></n-icon></template>
                    保存
                  </n-button>
                </div>
              </div>
            </template>

            <div v-if="!selectedSheetId" class="placeholder">选择左侧答题卡查看绑定关系</div>
            <n-data-table v-else :data="sheetItems" :max-height="500" :columns="[
              { title: '排序', key: 'area_sort', width: 100, render: row => h('n-input-number', { value: row.area_sort, min: 1, size: 'small', onUpdateValue: v => row.area_sort = v }, null) },
              { title: '题目ID', key: 'question_id', width: 100 },
              { title: '分值', key: 'area_score', width: 120, render: row => h('n-input-number', { value: row.area_score, min: 0, step: 0.5, size: 'small', onUpdateValue: v => row.area_score = v }, null) },
              { title: '样式', key: 'style_id', render: row => h('n-select', { value: row.style_id, options: allStyleOptions.value, clearable: true, size: 'small', onUpdateValue: v => row.style_id = v }, null) }
            ]" />
          </n-card>
        </div>
      </n-tab-pane>
    </n-tabs>

    <n-modal v-model:show="aiSheetDialog.visible" preset="card" title="AI 智能生成答题卡" style="width: 800px">
      <n-spin :show="aiSheetDialog.loading">
        <div v-if="aiSheetDialog.htmlContent" class="ai-preview" v-html="aiSheetDialog.htmlContent"></div>
        <div v-else-if="!aiSheetDialog.loading" style="text-align: center; padding: 100px 0;">AI正在思考排版...</div>
      </n-spin>
      <template #footer>
        <div style="display: flex; justify-content: flex-end; gap: 8px;">
          <n-button @click="aiSheetDialog.visible = false">关闭</n-button>
          <n-button type="primary" :disabled="!aiSheetDialog.htmlContent" @click="downloadAiWord">
            <template #icon><n-icon><DownloadOutline /></n-icon></template>
            下载 Word
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

.toolbar {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
}

.grid {
  display: grid;
  grid-template-columns: 1fr 1.4fr;
  gap: 16px;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.placeholder {
  color: var(--n-text-color-3);
  font-size: 13px;
}

.ai-preview {
  padding: 20px;
  border: 1px solid var(--n-border-color);
  border-radius: 12px;
  min-height: 300px;
}

/* 标签式筛选区域样式 */
.filter-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  background: var(--n-color-embedded);
  border-radius: 12px;
  margin-bottom: 12px;
}

.filter-section-header {
  cursor: pointer;
  user-select: none;
  display: flex;
  align-items: center;
}

.filter-section-header:hover {
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
  width: 50px;
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

