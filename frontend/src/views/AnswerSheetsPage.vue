<script setup>
import { computed, onMounted, reactive, ref, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Edit, Delete, Check, View, Download, MagicStick } from '@element-plus/icons-vue'
import { http } from '../api/http'
import StylePreview from '../components/StylePreview.vue'
import { marked } from 'marked'
import { asBlob } from 'html-docx-js-typescript'
import { saveAs } from 'file-saver'

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
const filters = reactive({
  subject_id: null,
  textbook_id: null,
})

const selectedPaperId = ref(null)
const sheets = ref([])
const selectedSheetId = ref(null)
const sheetItems = ref([])

const styleOptionsByType = computed(() => {
  const map = new Map()
  for (const s of styles.value) {
    const arr = map.get(s.type_id) || []
    arr.push(s)
    map.set(s.type_id, arr)
  }
  return map
})

const allStyleOptions = computed(() => styles.value)

import { getToken } from '../auth'

const aiSheetDialog = reactive({
  visible: false,
  loading: false,
  content: '',
  htmlContent: ''
})

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
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ paper_id: selectedPaperId.value })
    })

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n\n')
      buffer = lines.pop() // Keep the last incomplete chunk

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const jsonStr = line.substring(6)
          try {
            const data = JSON.parse(jsonStr)
            if (data.type === 'start') {
              aiSheetDialog.loading = false
            } else if (data.type === 'delta') {
              aiSheetDialog.loading = false
              aiSheetDialog.content += data.content
              aiSheetDialog.htmlContent = marked.parse(aiSheetDialog.content)
            } else if (data.type === 'done') {
              aiSheetDialog.content = data.markdown
              aiSheetDialog.htmlContent = marked.parse(data.markdown)
            } else if (data.type === 'error') {
              ElMessage.error(data.message || '生成出错')
            }
          } catch (e) {
            console.warn('Parse error', e)
          }
        }
      }
    }
  } catch (e) {
    console.error(e)
    ElMessage.error('生成失败')
  } finally {
    aiSheetDialog.loading = false
  }
}

async function downloadAiWord() {
  if (!aiSheetDialog.htmlContent) return
  try {
    const html = `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="UTF-8">
        <style>
          @page {
            size: A3 landscape;
            margin: 20mm;
            mso-page-orientation: landscape;
          }
          body { 
            font-family: "SimSun", "Songti SC", serif; 
            line-height: 1.5; 
            width: 100%;
          }
          /* Two column layout simulation for Word */
          .columns-container {
            column-count: 2;
            column-gap: 40px;
            column-rule: 1px solid #000;
            width: 100%;
          }
          /* Ensure header spans full width */
          .header-section {
            column-span: all;
            border-bottom: 2px solid #000;
            margin-bottom: 20px;
            padding-bottom: 10px;
          }
          table { border-collapse: collapse; width: 100%; margin: 10px 0; }
          td, th { border: 1px solid #000; padding: 4px; text-align: center; font-size: 10.5pt; }
          h1 { text-align: center; font-size: 22pt; margin: 10px 0; }
          h2 { font-size: 14pt; margin: 8px 0; border-left: 4px solid #000; padding-left: 8px; background: #eee; }
          h3 { font-size: 12pt; margin: 5px 0; }
          p { font-size: 10.5pt; margin: 5px 0; }
          
          /* Specific styles for AI generated elements */
          .ticket-no-table td { width: 25px; height: 18px; font-size: 9pt; }
          .option-box { display: inline-block; width: 30px; text-align: center; border: 1px solid #000; margin-right: 5px; }
          .essay-line { border-bottom: 1px solid #ccc; height: 30px; }
        </style>
      </head>
      <body>
        ${aiSheetDialog.htmlContent}
      </body>
      </html>
    `
    const blob = await asBlob(html, { orientation: 'landscape', margins: { top: 1134, bottom: 1134, left: 1134, right: 1134 } })
    saveAs(blob, 'AI答题卡.docx')
  } catch (e) {
    console.error(e)
    ElMessage.error('下载失败')
  }
}

const previewConfig = ref({})

watch(() => styleDialog.form.style_config, (val) => {
  try {
    const parsed = JSON.parse(val || '{}')
    // 智能兼容：如果用户粘贴了包含 style_config 的完整记录
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
      ElMessage.error('题型与样式名称必填')
      return
    }

    // 自动清洗：如果 style_config 是嵌套的完整记录，则提取内部真实配置
    let cleanConfig = styleDialog.form.style_config
    try {
      const parsed = JSON.parse(cleanConfig)
      if (parsed.style_config) {
        const inner = typeof parsed.style_config === 'string' ? JSON.parse(parsed.style_config) : parsed.style_config
        cleanConfig = JSON.stringify(inner)
        // 可选：如果用户未填写其他字段，也可以顺便从 parsed 中提取并提示，但这里只做静默清洗最安全
      }
    } catch (e) {
      // ignore parse error, let backend handle it or fail
    }

    if (styleDialog.mode === 'create') {
      await http.post('/answer-styles', {
        type_id: styleDialog.form.type_id,
        style_name: styleDialog.form.style_name,
        style_config: cleanConfig,
        is_default: styleDialog.form.is_default,
      })
    } else {
      await http.put(`/answer-styles/${styleDialog.form.style_id}`, {
        type_id: styleDialog.form.type_id,
        style_name: styleDialog.form.style_name,
        style_config: cleanConfig,
        is_default: styleDialog.form.is_default,
      })
    }
    styleDialog.visible = false
    await loadStyles()
  } catch (e) {
    ElMessage.error(e?.message || '保存失败')
  }
}

async function removeStyle(row) {
  try {
    await ElMessageBox.confirm(`确认删除样式：${row.style_name}？`, '提示', { type: 'warning' })
    await http.delete(`/answer-styles/${row.style_id}`)
    await loadStyles()
  } catch (e) {
    if (e?.message) ElMessage.error(e.message)
  }
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
  if (!selectedPaperId.value) {
    sheets.value = []
    selectedSheetId.value = null
    sheetItems.value = []
    return
  }
  const resp = await http.get('/answer-sheets', { params: { paper_id: selectedPaperId.value } })
  sheets.value = resp.data.items || []
}

async function loadSheetItems() {
  if (!selectedSheetId.value) {
    sheetItems.value = []
    return
  }
  const resp = await http.get(`/answer-sheets/${selectedSheetId.value}/items`)
  sheetItems.value = resp.data.items || []
}

const previewDialog = reactive({
  visible: false,
  items: [],
  paperSize: 'A3',
  ticketNoDigits: 8,
  headerConfig: {
    title: '',
    labels: {
      name: '姓名',
      class: '班级',
      id: '考号',
      seat: '座位'
    },
    notesTitle: '注意事项：',
    notesContent: [
      '1. 答题前请将姓名、班级、考号填写清楚。',
      '2. 客观题必须使用2B铅笔填涂；主观题必须使用黑色签字笔书写。',
      '3. 必须在各题目的答题区域内作答，超出黑色矩形边框限定区域的答案无效。'
    ]
  }
})

const previewPages = ref([])
const isCalculating = ref(false)
const measureRef = ref(null)
const measureColWidth = ref(100) // px

// Resize Logic
const resizingItem = ref(null)
const startY = ref(0)
const startHeight = ref(0)

function startResize(e, item) {
  resizingItem.value = item
  startY.value = e.clientY
  // Handle is absolute positioned at bottom, parent is .item-content
  const contentEl = e.target.parentElement
  startHeight.value = contentEl.offsetHeight
  
  document.addEventListener('mousemove', doResize)
  document.addEventListener('mouseup', stopResize)
  document.body.style.cursor = 'ns-resize'
  document.body.style.userSelect = 'none'
}

function doResize(e) {
  if (!resizingItem.value) return
  const dy = e.clientY - startY.value
  const newHeight = Math.max(30, startHeight.value + dy)
  resizingItem.value.customHeight = newHeight
}

function stopResize() {
  resizingItem.value = null
  document.removeEventListener('mousemove', doResize)
  document.removeEventListener('mouseup', stopResize)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
  calculateLayout()
}

watch([() => previewDialog.visible, () => previewDialog.paperSize, () => previewDialog.items, () => previewDialog.ticketNoDigits], () => {
  if (previewDialog.visible) {
    calculateLayout()
  }
})

async function calculateLayout() {
  if (!previewDialog.visible) return
  isCalculating.value = true
  
  await nextTick() // Wait for measureRef to be rendered/updated
  
  const container = measureRef.value
  if (!container) {
    isCalculating.value = false
    return
  }
  
  // Constants (MM to PX)
  const MM_TO_PX = 3.78
  const isA3 = previewDialog.paperSize === 'A3'
  
  // Dimensions
  // A3: 420x297mm, Padding 15mm
  // A4: 210x297mm, Padding 25.4mm
  const pageHeightMM = 297
  const paddingMM = isA3 ? 15 : 25.4
  const pageWidthMM = isA3 ? 420 : 210
  
  const pageHeight = pageHeightMM * MM_TO_PX
  const contentHeight = (pageHeightMM - paddingMM * 2) * MM_TO_PX
  const contentWidth = (pageWidthMM - paddingMM * 2) * MM_TO_PX
  
  const colGap = 30
  const colCount = isA3 ? 2 : 1
  const colWidth = isA3 ? (contentWidth - colGap) / 2 : contentWidth
  
  // Update measure box width to simulate real column width
  measureColWidth.value = colWidth
  
  await nextTick() // Wait for DOM update with new width
  
  // Measure Header
  // The header is not inside the measure-box for column calculation, 
  // but it takes up space on the first page.
  // We need to estimate its height.
  // Since we changed the header structure, let's assume a fixed height or measure it if possible.
  // But header is rendered in the real page, not measure box.
  // Let's approximate: 
  // Title + Info + Notes + Ticket Grid. 
  // Ticket Grid is ~10 rows.
  // Let's say ~250px height.
  const headerHeight = 350 // approx px
  
  // Measure Items
  const itemEls = container.querySelectorAll('.measure-item')
  const itemHeights = Array.from(itemEls).map(el => el.offsetHeight + 15) // +15 margin-bottom
  
  // Bin Packing
  const pages = []
  let currentPage = { columns: Array.from({ length: colCount }, () => []), hasHeader: true }
  let currentColIndex = 0
  let currentH = headerHeight + 20 // +margin
  
  // Helper to start new page
  const startNewPage = () => {
      pages.push(currentPage)
      currentPage = { columns: Array.from({ length: colCount }, () => []), hasHeader: false }
      currentColIndex = 0
      currentH = 0
  }
  
  for (let i = 0; i < previewDialog.items.length; i++) {
      const item = previewDialog.items[i]
      const h = itemHeights[i] || 50
      
      // Check if fits in current column
      if (currentH + h <= contentHeight) {
          currentPage.columns[currentColIndex].push(item)
          currentH += h
      } else {
          // Move to next column
          currentColIndex++
          if (currentColIndex < colCount) {
              // New column on same page
              currentH = 0
              // Check if fits in new column
              if (h <= contentHeight) {
                  currentPage.columns[currentColIndex].push(item)
                  currentH += h
              } else {
                  // Item too big for empty column? Force add or split (not handling split)
                  currentPage.columns[currentColIndex].push(item)
                  currentH += h
              }
          } else {
              // No more columns, new page
              startNewPage()
              // Try add to first col of new page
              if (h <= contentHeight) {
                  currentPage.columns[currentColIndex].push(item)
                  currentH += h
              } else {
                   currentPage.columns[currentColIndex].push(item)
                   currentH += h
              }
          }
      }
  }
  
  if (currentPage.columns.some(c => c.length > 0)) {
      pages.push(currentPage)
  }
  
  previewPages.value = pages
  isCalculating.value = false
}

async function openSheetPreview() {
  if (!selectedSheetId.value) return
  // Prepare items with full style config
  const items = sheetItems.value.map(it => {
    const style = styles.value.find(s => s.style_id === it.style_id)
    let config = {}
    if (style) {
      try {
        const parsed = JSON.parse(style.style_config || '{}')
        // 同样应用智能清洗逻辑
        if (parsed.style_config) {
          const inner = typeof parsed.style_config === 'string' ? JSON.parse(parsed.style_config) : parsed.style_config
          config = inner || {}
        } else {
          config = parsed
        }
      } catch {}
    }
    return {
      ...it,
      style_config: config,
      style_name: style ? style.style_name : '未绑定样式',
      customHeight: null // Initialize
    }
  })
  previewDialog.items = items
  // Init Header
  const sheet = sheets.value.find(s => s.sheet_id === selectedSheetId.value)
  previewDialog.headerConfig.title = sheet ? sheet.sheet_name : '答题卡'
  
  previewDialog.visible = true
}

async function downloadSheet(type) {
  if (!selectedSheetId.value) return
  try {
    ElMessage.info('正在生成文件，请稍候...')
    const resp = await http.post(`/answer-sheets/${selectedSheetId.value}/export/${type}`, {
      paper_size: previewDialog.paperSize,
      ticket_no_digits: previewDialog.ticketNoDigits
    }, {
      responseType: 'blob'
    })
    
    const mimeType = type === 'pdf' ? 'application/pdf' : 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    const blob = new Blob([resp.data], { type: mimeType })
    
    let downloadName = `答题卡.${type === 'pdf' ? 'pdf' : 'docx'}`
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
    } else {
        // Fallback: use sheet name if available
        const sheet = sheets.value.find(s => s.sheet_id === selectedSheetId.value)
        if (sheet && sheet.sheet_name) {
            downloadName = `${sheet.sheet_name}.${type === 'pdf' ? 'pdf' : 'docx'}`
        }
    }

    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = downloadName
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    
    ElMessage.success('下载成功')
  } catch (e) {
    console.error(e)
    ElMessage.error('下载失败')
  }
}

async function buildSheetFromPaper() {
  if (!selectedPaperId.value) {
    ElMessage.warning('请选择试卷')
    return
  }
  try {
    await http.post(`/answer-sheets/from-paper/${selectedPaperId.value}`, { create_user: 'creator' })
    ElMessage.success('已生成/刷新答题卡')
    await loadSheets()
  } catch (e) {
    ElMessage.error(e?.message || '生成失败')
  }
}

async function saveSheetItems() {
  if (!selectedSheetId.value) return
  try {
    await http.put(`/answer-sheets/${selectedSheetId.value}/items`, {
      items: sheetItems.value.map((it) => ({
        question_id: it.question_id,
        style_id: it.style_id,
        area_sort: it.area_sort,
        area_score: it.area_score,
      })),
    })
    ElMessage.success('已保存')
    await loadSheetItems()
  } catch (e) {
    ElMessage.error(e?.message || '保存失败')
  }
}

onMounted(async () => {
  loading.value = true
  error.value = ''
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
</script>

<template>
  <div class="page">
    <el-alert v-if="error" :title="error" type="error" show-icon />

    <el-tabs v-model="activeTab">
      <el-tab-pane name="styles" label="样式库">
        <div class="toolbar">
          <el-button type="primary" @click="openCreateStyle" :icon="Plus">新增样式</el-button>
          <el-button @click="loadStyles" :icon="Refresh">刷新</el-button>
        </div>

        <el-table :data="styles" height="620">
          <el-table-column prop="style_id" label="ID" width="90" />
          <el-table-column prop="type_id" label="题型ID" width="100" />
          <el-table-column prop="style_name" label="样式名称" min-width="260" />
          <el-table-column prop="is_default" label="默认" width="90" />
          <el-table-column fixed="right" label="操作" width="180">
            <template #default="{ row }">
              <el-button link type="primary" @click="openEditStyle(row)" :icon="Edit">编辑</el-button>
              <el-button link type="danger" @click="removeStyle(row)" :icon="Delete">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-dialog v-model="styleDialog.visible" :title="styleDialog.mode === 'create' ? '新增样式' : '编辑样式'" width="900px">
          <div style="display: flex; gap: 20px;">
            <div style="flex: 1;">
              <el-form label-width="90px">
                <el-form-item label="题型">
                  <el-select v-model="styleDialog.form.type_id" placeholder="选择题型" style="width: 100%">
                    <el-option v-for="t in types" :key="t.type_id" :label="t.type_name" :value="t.type_id" />
                  </el-select>
                </el-form-item>
                <el-form-item label="名称">
                  <el-input v-model="styleDialog.form.style_name" />
                </el-form-item>
                <el-form-item label="默认">
                  <el-switch v-model="styleDialog.form.is_default" :active-value="1" :inactive-value="0" />
                </el-form-item>
                <el-form-item label="配置JSON">
                  <el-input v-model="styleDialog.form.style_config" type="textarea" :rows="15" />
                </el-form-item>
              </el-form>
            </div>
            <div style="width: 300px; border-left: 1px solid #eee; padding-left: 20px;">
              <div style="margin-bottom: 10px; font-weight: bold; color: var(--el-text-color-secondary);">样式预览</div>
              <StylePreview :config="previewConfig" />
            </div>
          </div>
          <template #footer>
            <el-button @click="styleDialog.visible = false">取消</el-button>
            <el-button type="primary" @click="submitStyle">保存</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>

      <el-tab-pane name="sheets" label="答题卡">
        <div class="grid">
          <el-card class="card" header="选择试卷与答题卡">
            <div class="toolbar" style="flex-wrap: wrap;">
              <el-select
                v-model="filters.subject_id"
                clearable
                placeholder="科目"
                style="width: 140px"
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
                style="width: 180px"
                @change="loadPapers"
              >
                <el-option v-for="t in textbooks" :key="t.textbook_id" :label="t.textbook_name + (t.author ? ' (' + t.author + ')' : '')" :value="t.textbook_id" />
              </el-select>

              <el-select
                v-model="selectedPaperId"
                clearable
                placeholder="选择试卷"
                style="width: 100%"
                @change="
                  async () => {
                    selectedSheetId = null
                    await loadSheets()
                  }
                "
              >
                <el-option v-for="p in papers" :key="p.paper_id" :label="p.paper_name" :value="p.paper_id" />
              </el-select>
            </div>
            <div class="toolbar">
              <el-button :disabled="!selectedPaperId" type="primary" @click="buildSheetFromPaper" :icon="Refresh">生成/刷新答题卡</el-button>
              <el-button :disabled="!selectedPaperId" type="warning" @click="openAiGenerateSheet" :icon="MagicStick">AI生成答题卡</el-button>
              <el-button :disabled="!selectedPaperId" @click="loadSheets" :icon="Refresh">刷新</el-button>
            </div>

            <el-table
              :data="sheets"
              height="520"
              highlight-current-row
              @current-change="
                async (row) => {
                  selectedSheetId = row?.sheet_id || null
                  await loadSheetItems()
                }
              "
            >
              <el-table-column prop="sheet_id" label="ID" width="90" />
              <el-table-column prop="sheet_name" label="名称" min-width="220" />
              <el-table-column prop="paper_id" label="试卷ID" width="100" />
            </el-table>
          </el-card>

          <el-card class="card">
            <template #header>
              <div class="header">
                <div>题目-样式绑定</div>
                <div style="display: flex; gap: 8px; flex-shrink: 0; min-width: 150px; justify-content: flex-end;">
                  <el-button type="primary" :disabled="!selectedSheetId" @click="saveSheetItems" :icon="Check">保存</el-button>
                  <el-button type="success" :disabled="!selectedSheetId" @click="openSheetPreview" :icon="View">预览</el-button>
                </div>
              </div>
            </template>

            <div v-if="!selectedSheetId" class="placeholder">选择左侧答题卡查看绑定关系</div>
            <el-table v-else :data="sheetItems" height="620">
              <el-table-column prop="area_sort" label="排序" width="140">
                <template #default="{ row }">
                  <el-input-number v-model="row.area_sort" :min="1" style="width: 100%" />
                </template>
              </el-table-column>
              <el-table-column prop="question_id" label="题目ID" width="120" />
              <el-table-column prop="area_score" label="分值" width="150">
                <template #default="{ row }">
                  <el-input-number v-model="row.area_score" :min="0" :step="0.5" style="width: 100%" />
                </template>
              </el-table-column>
              <el-table-column prop="style_id" label="样式" min-width="260">
                <template #default="{ row }">
                  <el-select v-model="row.style_id" clearable placeholder="选择样式" style="width: 100%">
                    <el-option v-for="s in allStyleOptions" :key="s.style_id" :label="`[${s.type_id}] ${s.style_name}`" :value="s.style_id" />
                  </el-select>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </div>

        <el-dialog v-model="previewDialog.visible" title="答题卡预览" width="100%" fullscreen class="preview-dialog-no-padding">
          <div class="preview-top-bar">
            <div style="display: flex; align-items: center; gap: 20px;">
                <el-radio-group v-model="previewDialog.paperSize">
                    <el-radio-button label="A4">A4 (分页)</el-radio-button>
                    <el-radio-button label="A3">A3 (双栏)</el-radio-button>
                </el-radio-group>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 14px; color: var(--el-text-color-regular);">准考证号位数：</span>
                    <el-input-number v-model="previewDialog.ticketNoDigits" :min="4" :max="12" size="small" style="width: 100px" />
                </div>
            </div>
            <div style="display: flex; gap: 10px;">
                <el-button @click="previewDialog.visible = false">关闭</el-button>
                <el-button type="primary" @click="downloadSheet('word')" :icon="Download">下载 Word</el-button>
                <el-button type="danger" @click="downloadSheet('pdf')" :icon="Download">下载 PDF</el-button>
            </div>
          </div>
          <div class="sheet-preview-container">
            <!-- Measurement Box (Hidden) -->
            <div ref="measureRef" class="measure-box" :style="{ width: measureColWidth + 'px' }">
               <div class="measure-header">
                 <h3>{{ sheets.find(s => s.sheet_id === selectedSheetId)?.sheet_name }}</h3>
                 <div class="student-info">...</div>
               </div>
               <div v-for="item in previewDialog.items" :key="item.question_id" class="measure-item sheet-item">
                 <div class="item-label">
                   <strong>{{ item.area_sort }}.</strong>
                   <span v-if="item.area_score" style="font-size: 12px; color: #666; margin-left: 4px;">({{ item.area_score }}分)</span>
                 </div>
                 <div class="item-content">
                   <StylePreview :config="item.style_config" :style="item.customHeight ? { height: item.customHeight + 'px', minHeight: 'auto', overflow: 'hidden' } : {}" />
                 </div>
               </div>
            </div>

            <!-- Real Pages -->
            <div v-for="(page, pIndex) in previewPages" :key="pIndex" 
                 class="sheet-paper" 
                 :class="{ 'is-a3': previewDialog.paperSize === 'A3' }"
                 :style="previewDialog.paperSize === 'A3' ? 'max-width: none; width: 420mm;' : 'max-width: none; width: 210mm;'">
              
              <!-- Header on first page only -->
              <div v-if="page.hasHeader" class="sheet-header-wrapper">
                <div class="header-left">
                    <h3 class="header-title" contenteditable="true" @blur="previewDialog.headerConfig.title = $event.target.innerText">{{ previewDialog.headerConfig.title }}</h3>
                    
                    <div class="info-grid">
                        <div class="info-item">
                            <span class="info-label" contenteditable="true" @blur="previewDialog.headerConfig.labels.name = $event.target.innerText">{{ previewDialog.headerConfig.labels.name }}：</span>
                            <span class="info-line">__________________</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label" contenteditable="true" @blur="previewDialog.headerConfig.labels.class = $event.target.innerText">{{ previewDialog.headerConfig.labels.class }}：</span>
                            <span class="info-line">__________________</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label" contenteditable="true" @blur="previewDialog.headerConfig.labels.id = $event.target.innerText">{{ previewDialog.headerConfig.labels.id }}：</span>
                            <span class="info-line">__________________</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label" contenteditable="true" @blur="previewDialog.headerConfig.labels.seat = $event.target.innerText">{{ previewDialog.headerConfig.labels.seat }}：</span>
                            <span class="info-line">__________________</span>
                        </div>
                    </div>
                    
                    <div class="notes-section">
                        <div class="notes-title" contenteditable="true" @blur="previewDialog.headerConfig.notesTitle = $event.target.innerText">{{ previewDialog.headerConfig.notesTitle }}</div>
                        <div class="notes-content">
                            <p v-for="(note, idx) in previewDialog.headerConfig.notesContent" :key="idx" contenteditable="true" @blur="previewDialog.headerConfig.notesContent[idx] = $event.target.innerText">{{ note }}</p>
                        </div>
                    </div>
                </div>
                
                <div class="header-right">
                    <div class="ticket-title">准考证号填涂区</div>
                    <table class="ticket-grid">
                        <tbody>
                            <tr v-for="r in 10" :key="r">
                                <td v-for="c in previewDialog.ticketNoDigits" :key="c">[{{ r-1 }}]</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
              </div>
              <div v-if="page.hasHeader" class="header-divider"></div>
              
              <div class="sheet-body-flex">
                <div v-for="(col, cIndex) in page.columns" :key="cIndex" class="sheet-column">
                    <div v-for="item in col" :key="item.question_id" class="sheet-item">
                      <div class="item-label">
                        <strong>{{ item.area_sort }}.</strong>
                        <span v-if="item.area_score" style="font-size: 12px; color: #666; margin-left: 4px;">({{ item.area_score }}分)</span>
                      </div>
                      <div class="item-content">
                        <StylePreview :config="item.style_config" :style="item.customHeight ? { height: item.customHeight + 'px', minHeight: 'auto', overflow: 'hidden' } : {}" />
                        <div class="resize-handle" @mousedown.prevent="startResize($event, item)"></div>
                      </div>
                    </div>
                </div>
              </div>
              
              <div class="sheet-footer">
                  第 {{ pIndex + 1 }} 页 / 共 {{ previewPages.length }} 页
              </div>
            </div>
          </div>
        </el-dialog>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="aiSheetDialog.visible" title="AI 智能生成答题卡" width="800px">
      <div v-loading="aiSheetDialog.loading" style="min-height: 300px;">
        <div v-if="aiSheetDialog.htmlContent" class="ai-preview" v-html="aiSheetDialog.htmlContent"></div>
        <div v-else-if="!aiSheetDialog.loading" style="text-align: center; color: var(--el-text-color-secondary); margin-top: 100px;">
          AI正在思考排版...
        </div>
      </div>
      <template #footer>
        <el-button @click="aiSheetDialog.visible = false">关闭</el-button>
        <el-button type="primary" :disabled="!aiSheetDialog.htmlContent" @click="downloadAiWord" :icon="Download">下载 Word</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style>
.preview-dialog-no-padding .el-dialog__body {
  padding: 0 !important;
  display: flex;
  flex-direction: column;
  height: calc(100vh - 55px); /* Header height approx */
  overflow: hidden;
}
</style>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 12px;
  background-color: var(--el-bg-color);
  color: var(--el-text-color-primary);
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

.card {
  width: 100%;
}

.placeholder {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  box-sizing: border-box; /* Ensure padding doesn't affect width */
}

.preview-top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 20px;
  background-color: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color);
  position: sticky;
  top: 0;
  z-index: 100;
  color: var(--el-text-color-primary);
}

.sheet-preview-container {
  background: #525659;
  padding: 40px;
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 30px;
  height: auto; /* Let flex handle height */
}

.sheet-paper {
  background: #fff;
  color: #000;
  /* width is set by inline style */
  min-height: 297mm; /* Fixed height for page simulation */
  padding: 25.4mm;
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  position: relative;
}

.sheet-paper.is-a3 {
  min-height: 297mm;
  padding: 15mm;
}

.sheet-header-wrapper {
  display: flex;
  border: 1px solid #000;
  margin-bottom: 20px;
}

.header-left {
  flex: 1;
  padding: 15px;
  border-right: 1px solid #000;
  display: flex;
  flex-direction: column;
}

.header-right {
  width: 350px; /* Fixed width for ticket grid area */
  padding: 10px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.header-title {
  text-align: center;
  margin: 0 0 20px 0;
  font-size: 24px;
  font-family: "SimHei", serif; /* 模拟黑体 */
}

.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 15px 30px;
  margin-bottom: 20px;
  border-bottom: 1px dashed #999;
  padding-bottom: 20px;
}

.info-item {
  display: flex;
  align-items: baseline;
}

.info-label {
  font-size: 16px;
  font-family: "SimSun", serif; /* 模拟宋体 */
  font-weight: bold;
  white-space: nowrap;
}

.info-line {
  flex: 1;
  border-bottom: 1px solid #000;
  text-align: center;
  font-family: "Courier New", monospace;
  font-size: 14px;
}

.notes-section {
  font-size: 14px;
  line-height: 1.6;
}

.notes-title {
  font-weight: bold;
  margin-bottom: 5px;
  font-size: 16px;
}

.notes-content p {
  margin: 2px 0;
}

.ticket-title {
  font-weight: bold;
  font-size: 18px;
  margin-bottom: 10px;
  text-align: center;
  font-family: "SimHei", serif;
}

.ticket-grid {
  border-collapse: collapse;
  width: 100%;
}

.ticket-grid td {
  border: 1px solid #000;
  text-align: center;
  padding: 2px;
  font-size: 12px;
  font-family: "Arial", sans-serif;
  height: 20px;
  width: 25px;
}

.header-divider {
  display: none; /* Hide old divider */
}

.student-info {
  display: none; /* Hide old info */
}

.sheet-body-flex {
  flex: 1;
  display: flex;
  gap: 30px; /* Column gap */
}

.sheet-column {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0; /* Items margin handled by item itself */
}

.measure-box {
  position: absolute;
  top: -9999px;
  left: -9999px;
  visibility: hidden;
  background: white;
}

.sheet-footer {
    text-align: center;
    font-size: 12px;
    color: #333;
    margin-top: 10px;
    position: absolute;
    bottom: 10mm;
    width: calc(100% - 50mm); /* approx */
    left: 50%;
    transform: translateX(-50%);
}

.sheet-item {
  display: flex;
  gap: 10px;
  margin-bottom: 15px;
  break-inside: avoid; /* Prevent split across columns */
}

.item-label {
  width: 50px;
  text-align: right;
  padding-top: 5px;
}

.item-content {
  flex: 1;
  position: relative;
}

.resize-handle {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  height: 8px;
  cursor: ns-resize;
  background: transparent;
  transition: background 0.2s;
  z-index: 10;
}

.resize-handle:hover {
  background: rgba(0, 0, 0, 0.1);
}

[contenteditable="true"]:hover {
  outline: 1px dashed #999;
  cursor: text;
}

.ai-preview {
  padding: 20px;
  border: 1px solid var(--el-border-color);
  background: var(--el-bg-color);
  border-radius: 4px;
  color: var(--el-text-color-primary);
}
</style>

