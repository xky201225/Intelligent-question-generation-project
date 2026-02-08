<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Edit, Delete, Check, View, Download } from '@element-plus/icons-vue'
import { http } from '../api/http'
import StylePreview from '../components/StylePreview.vue'

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

async function loadPapers() {
  const resp = await http.get('/papers')
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
  paperSize: 'A3'
})

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
      style_name: style ? style.style_name : '未绑定样式'
    }
  })
  previewDialog.items = items
  previewDialog.visible = true
}

async function downloadSheet(type) {
  if (!selectedSheetId.value) return
  try {
    ElMessage.info('正在生成文件，请稍候...')
    const resp = await http.post(`/answer-sheets/${selectedSheetId.value}/export/${type}`, {
      paper_size: previewDialog.paperSize
    })
    const { filename, download_name } = resp.data
    
    // Use blob download to handle authentication (token)
    // The download endpoint is: /answer-sheets/download/<sheet_id>/<filename>
    const downloadResp = await http.get(`/answer-sheets/download/${selectedSheetId.value}/${filename}`, {
        responseType: 'blob'
    })
    
    // Determine mime type based on file extension
    const mimeType = type === 'pdf' ? 'application/pdf' : 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    
    const blob = new Blob([downloadResp.data], { type: mimeType })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = download_name || filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    
    ElMessage.success('下载成功')
  } catch (e) {
    console.error(e)
    const msg = e.response?.data?.error?.message || e.message || '下载失败'
    ElMessage.error(msg)
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
              <div style="margin-bottom: 10px; font-weight: bold; color: #666;">样式预览</div>
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
            <div class="toolbar">
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

          <el-card class="card" header="题目-样式绑定">
            <template #header>
              <div class="header">
                <div>题目-样式绑定</div>
                <div style="display: flex; gap: 8px;">
                  <el-button type="primary" :disabled="!selectedSheetId" @click="saveSheetItems" :icon="Check">保存</el-button>
                  <el-button type="success" :disabled="!selectedSheetId" @click="openSheetPreview" :icon="View">预览</el-button>
                </div>
              </div>
            </template>

            <div v-if="!selectedSheetId" class="placeholder">选择左侧答题卡查看绑定关系</div>
            <el-table v-else :data="sheetItems" height="620">
              <el-table-column prop="area_sort" label="排序" width="100">
                <template #default="{ row }">
                  <el-input-number v-model="row.area_sort" :min="1" style="width: 100%" />
                </template>
              </el-table-column>
              <el-table-column prop="question_id" label="题目ID" width="120" />
              <el-table-column prop="area_score" label="分值" width="120">
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

        <el-dialog v-model="previewDialog.visible" title="答题卡预览" width="1200px" top="5vh">
          <div class="sheet-preview-container">
            <div class="sheet-paper" :style="previewDialog.paperSize === 'A3' ? 'max-width: 1100px;' : 'max-width: 794px;'">
              <div class="sheet-header">
                <h3>{{ sheets.find(s => s.sheet_id === selectedSheetId)?.sheet_name }}</h3>
                <div class="student-info">
                  <span>姓名：______________</span>
                  <span>班级：______________</span>
                  <span>考号：______________</span>
                  <span>座位：______________</span>
                </div>
                <div class="header-divider"></div>
              </div>
              
              <div class="sheet-body">
                <div v-for="item in previewDialog.items" :key="item.question_id" class="sheet-item">
                  <div class="item-label">
                    <strong>{{ item.area_sort }}.</strong>
                    <span v-if="item.area_score" style="font-size: 12px; color: #666; margin-left: 4px;">({{ item.area_score }}分)</span>
                  </div>
                  <div class="item-content">
                    <StylePreview :config="item.style_config" />
                  </div>
                </div>
              </div>
            </div>
          </div>
          <template #footer>
            <div style="float: left;">
                <el-radio-group v-model="previewDialog.paperSize">
                    <el-radio-button label="A4">A4 (分页)</el-radio-button>
                    <el-radio-button label="A3">A3 (双栏)</el-radio-button>
                </el-radio-group>
            </div>
            <el-button @click="previewDialog.visible = false">关闭</el-button>
            <el-button type="primary" @click="downloadSheet('word')" :icon="Download">下载 Word</el-button>
            <el-button type="danger" @click="downloadSheet('pdf')" :icon="Download">下载 PDF</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>
    </el-tabs>
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
}

.sheet-preview-container {
  background: #eee;
  padding: 20px;
  max-height: 80vh;
  overflow-y: auto;
  display: flex;
  justify-content: center;
}

.sheet-paper {
  background: #fff;
  width: 100%;
  max-width: 1100px; /* A3 landscape ratio approximation */
  min-height: 600px;
  padding: 30px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.sheet-header {
  text-align: center;
  margin-bottom: 20px;
}

.header-divider {
  border-bottom: 2px solid #333;
  margin: 15px 0;
}

.student-info {
  display: flex;
  justify-content: center;
  gap: 40px;
  margin-top: 15px;
  font-size: 14px;
}

.sheet-body {
  column-count: 3;
  column-gap: 30px;
  column-rule: 1px solid #ccc;
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
}
</style>

