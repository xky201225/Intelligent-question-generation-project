<script setup>
import { computed, ref, watch, nextTick } from 'vue'
import { useMessage } from 'naive-ui'
import { DownloadOutline, PrintOutline, DocumentOutline } from '@vicons/ionicons5'
import { http } from '../api/http'

const message = useMessage()

const props = defineProps({
  visible: Boolean,
  paper: Object,
  questions: Array,
})

const showAnswers = ref(false)
const paperSize = ref('A4')
const pages = ref([])
const isCalculating = ref(false)
const measureRef = ref(null)

const emit = defineEmits(['update:visible'])

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
})

async function calculateLayout() {
  if (!props.visible) return
  isCalculating.value = true
  pages.value = []
  
  await nextTick()
  
  const container = measureRef.value
  if (!container) {
    isCalculating.value = false
    return
  }
  
  container.style.cssText = 'position:absolute; visibility:hidden; height:297mm; width:210mm; padding:0; border:none; margin:0;'
  const height297mm = container.offsetHeight
  
  container.style.height = '25.4mm'
  const paddingA4 = container.offsetHeight
  const contentHeightA4 = height297mm - (paddingA4 * 2)
  const contentWidthA4 = container.offsetWidth - (paddingA4 * 2)

  container.style.height = '15mm'
  const paddingA3 = container.offsetHeight
  const contentHeightA3 = height297mm - (paddingA3 * 2)
  container.style.width = '420mm'
  const width420mm = container.offsetWidth
  const fullContentWidthA3 = width420mm - (paddingA3 * 2)
  const gap30px = 30
  const colWidthA3 = (fullContentWidthA3 - gap30px) / 2
  
  container.style.cssText = 'position:absolute; visibility:hidden; top:-9999px; left:-9999px;'
  container.className = 'paper-content'

  const resetMeasureStyle = () => {
    container.style.height = 'auto'
    container.style.minHeight = '0'
    container.style.maxHeight = 'none'
    container.style.columnCount = 'auto'
    container.style.overflow = 'visible'
    container.style.padding = '0'
    container.style.border = 'none'
    container.style.margin = '0'
  }
  
  const getHeaderHtml = () => `
    <h1 style="text-align: center; margin-bottom: 20px;">${props.paper?.paper_name || ''}</h1>
    ${props.paper?.paper_desc ? `<p class="paper-meta" style="margin-bottom: 20px; text-indent: 2em;">${props.paper.paper_desc}</p>` : ''}
    <p class="paper-meta" style="margin-bottom: 20px; text-align: center;">
        时长：${props.paper?.exam_duration || 0}分钟 &nbsp;&nbsp; 
        ${props.paper?.is_closed_book ? '闭卷' : '开卷'} &nbsp;&nbsp;
        总分：${props.paper?.total_score || 0}
    </p>
  `
  
  resetMeasureStyle()
  container.innerHTML = getHeaderHtml()
  if (paperSize.value === 'A3') {
    container.style.width = fullContentWidthA3 + 'px'
  } else {
    container.style.width = contentWidthA4 + 'px'
  }
  const headerHeight = container.offsetHeight
  
  const questions = props.questions || []
  const questionHeights = []
  
  resetMeasureStyle()
  if (paperSize.value === 'A3') {
    container.style.width = colWidthA3 + 'px'
  } else {
    container.style.width = contentWidthA4 + 'px'
  }
  
  for (let q of questions) {
    container.innerHTML = `
      <div class="q-item" style="margin-bottom: 15px;">
        <p class="q-title">
          <strong>${q.question_sort}. </strong>
          ${q.question_score ? `<span>（${q.question_score}分）</span>` : ''}
          <span>${formatQuestionContent(q.question_content)}</span>
        </p>
        ${showAnswers.value ? `
          <div class="q-answer-section" style="margin-top: 8px; padding: 10px;">
            ${q.question_answer ? `<p><strong>答案：</strong>${q.question_answer}</p>` : ''}
            ${q.question_analysis ? `<p><strong>解析：</strong>${q.question_analysis}</p>` : ''}
          </div>
        ` : ''}
      </div>
    `
    const child = container.firstElementChild
    const style = window.getComputedStyle(child)
    const mt = parseFloat(style.marginTop) || 0
    const mb = parseFloat(style.marginBottom) || 0
    questionHeights.push(child.offsetHeight + mt + mb)
  }
  
  const isA3Mode = paperSize.value === 'A3'
  const maxColHeight = isA3Mode ? contentHeightA3 : contentHeightA4
  const maxColsPerPage = isA3Mode ? 2 : 1
  const SAFETY = 5
  
  let currentPages = []
  let currentPageQuestions = []
  let colsUsedOnPage = 0
  let currentColHeight = 0
  let availableHeightOnPage = maxColHeight - headerHeight - SAFETY
  if (availableHeightOnPage < 0) availableHeightOnPage = 0
  
  for (let i = 0; i < questions.length; i++) {
    const q = questions[i]
    const h = questionHeights[i]

    if (currentColHeight + h <= availableHeightOnPage) {
      currentPageQuestions.push(q)
      currentColHeight += h
    } else {
      colsUsedOnPage++

      if (colsUsedOnPage < maxColsPerPage) {
        currentColHeight = 0
        if (h <= availableHeightOnPage) {
          currentPageQuestions.push(q)
          currentColHeight += h
        } else {
          if (availableHeightOnPage < maxColHeight && h <= maxColHeight - SAFETY) {
            currentPages.push({ questions: currentPageQuestions, hasHeader: currentPages.length === 0 })
            currentPageQuestions = [q]
            colsUsedOnPage = 0
            currentColHeight = h
            availableHeightOnPage = maxColHeight - SAFETY
          } else {
            currentPageQuestions.push(q)
            currentColHeight += h
          }
        }
      } else {
        currentPages.push({ questions: currentPageQuestions, hasHeader: currentPages.length === 0 })
        currentPageQuestions = [q]
        colsUsedOnPage = 0
        currentColHeight = h
        availableHeightOnPage = maxColHeight - SAFETY
      }
    }
  }
  
  if (currentPageQuestions.length > 0) {
    currentPages.push({ questions: currentPageQuestions, hasHeader: currentPages.length === 0 })
  }
  
  pages.value = currentPages
  isCalculating.value = false
}

watch([() => props.visible, () => props.questions, paperSize, showAnswers], () => {
  if (props.visible) {
    calculateLayout()
  }
}, { immediate: true })

async function doExportWord() {
  try {
    const resp = await http.post(`/papers/${props.paper.paper_id}/export/word`, {
      paper_size: paperSize.value
    }, {
      responseType: 'blob'
    })
    
    const blob = new Blob([resp.data], { 
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    })
    
    let downloadName = props.paper?.paper_name ? `${props.paper.paper_name}.docx` : `paper_export.docx`
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
    }
    
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = downloadName
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    
    message.success('导出成功')
  } catch (e) {
    console.error(e)
    message.error('导出失败: ' + (e?.message || '未知错误'))
  }
}

function doExportPdf() {
  const el = document.getElementById('print-area')
  const content = el ? el.innerHTML : ''

  const printWindow = window.open('', '_blank')
  if (!printWindow) {
    message.error('浏览器拦截了打印窗口，请允许弹窗后重试')
    return
  }

  const safeTitle = String(props.paper?.paper_name || 'paper')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  const isA3 = paperSize.value === 'A3'
  const pageStyle = isA3
    ? '@page { size: A3 landscape; margin: 0; }'
    : '@page { size: A4; margin: 0; }'

  const html = `<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <title>${safeTitle}</title>
    <style>
      ${pageStyle}
      html, body { margin: 0; padding: 0; }
      body { font-family: 'Microsoft YaHei', sans-serif; color: #333; }
      img { max-width: 100%; }
      .paper-content {
        background: white;
        width: 210mm;
        height: 297mm;
        padding: 25.4mm;
        box-sizing: border-box;
        overflow: hidden;
        break-after: page;
      }
      .paper-content.is-a3 {
        width: 420mm;
        height: 297mm;
        padding: 15mm;
        column-count: 2;
        column-gap: 30px;
        column-rule: 1px solid #ccc;
      }
      .paper-content.is-a3 h1,
      .paper-content.is-a3 .paper-meta {
        column-span: all;
        text-align: center;
      }
      .q-item { break-inside: avoid; margin-bottom: 15px; }
      .q-answer-section {
        margin-top: 8px;
        padding: 10px;
        background-color: #f8f9fa;
        border-radius: 4px;
        font-size: 14px;
        color: #666;
        line-height: 1.6;
      }
    </style>
  </head>
  <body>
    ${content}
  </body>
</html>`

  printWindow.document.open()
  printWindow.document.write(html)
  printWindow.document.close()
  printWindow.focus()

  const triggerPrint = () => {
    try {
      printWindow.print()
    } finally {
      printWindow.close()
    }
  }

  if (printWindow.document.readyState === 'complete') {
    setTimeout(triggerPrint, 50)
  } else {
    printWindow.onload = () => setTimeout(triggerPrint, 50)
  }
}

function formatQuestionContent(content) {
  if (!content) return ''
  return content.replace(/(\s|&nbsp;)([A-F]\.)/g, '<br><br>$2')
}

function scrollToPage(index) {
  const el = document.getElementById('page-' + index)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}
</script>

<template>
  <n-modal
    v-model:show="dialogVisible"
    preset="card"
    style="width: 95vw; height: 95vh; max-width: 1600px;"
    :mask-closable="false"
    :segmented="{ content: true }"
    content-style="padding: 0; display: flex; flex-direction: column; overflow: hidden;"
  >
    <template #header>
      <div class="modal-header">
        <div class="header-title">
          <n-icon size="20" class="title-icon"><DocumentOutline /></n-icon>
          <span>导出预览</span>
        </div>
      </div>
    </template>

    <template #header-extra>
      <div class="header-actions">
        <n-button-group>
          <n-button :type="paperSize === 'A4' ? 'primary' : 'default'" @click="paperSize = 'A4'" size="small">
            A4 分页
          </n-button>
          <n-button :type="paperSize === 'A3' ? 'primary' : 'default'" @click="paperSize = 'A3'" size="small">
            A3 分栏
          </n-button>
        </n-button-group>

        <n-divider vertical />

        <n-checkbox v-model:checked="showAnswers" size="small">
          显示答案
        </n-checkbox>

        <n-divider vertical />

        <n-button type="primary" @click="doExportWord" size="small">
          <template #icon><n-icon><DownloadOutline /></n-icon></template>
          Word
        </n-button>
        <n-button type="info" @click="doExportPdf" size="small">
          <template #icon><n-icon><PrintOutline /></n-icon></template>
          PDF
        </n-button>
      </div>
    </template>

    <div class="preview-container">
      <!-- 左侧信息面板 -->
      <aside class="info-panel">
        <div class="paper-info">
          <h3 class="info-title">试卷信息</h3>
          <div class="info-item">
            <span class="info-label">试卷名称</span>
            <span class="info-value">{{ paper?.paper_name || '-' }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">考试时长</span>
            <span class="info-value">{{ paper?.exam_duration || 0 }} 分钟</span>
          </div>
          <div class="info-item">
            <span class="info-label">考试形式</span>
            <span class="info-value">{{ paper?.is_closed_book ? '闭卷' : '开卷' }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">总分</span>
            <span class="info-value highlight">{{ paper?.total_score || 0 }} 分</span>
          </div>
          <div class="info-item">
            <span class="info-label">题目数量</span>
            <span class="info-value">{{ questions?.length || 0 }} 题</span>
          </div>
        </div>

        <n-divider />

        <div class="page-nav">
          <h3 class="info-title">页面导航</h3>
          <div v-if="pages.length > 0" class="page-list">
            <div
              v-for="(page, index) in pages"
              :key="index"
              class="page-thumb"
              :class="{ 'has-header': page.hasHeader }"
              @click="scrollToPage(index)"
            >
              <span class="page-num">{{ index + 1 }}</span>
              <span class="page-questions">{{ page.questions.length }} 题</span>
            </div>
          </div>
          <div v-else class="page-empty">
            暂无页面
          </div>
        </div>
      </aside>

      <!-- 主预览区 -->
      <main class="preview-main">
        <div ref="measureRef" class="measure-box paper-content" :class="{ 'is-a3': paperSize === 'A3' }"></div>

        <!-- 加载状态 -->
        <div v-if="isCalculating" class="loading-state">
          <n-spin size="large" />
          <span class="loading-text">正在计算分页布局...</span>
        </div>

        <!-- 空状态 -->
        <div v-else-if="pages.length === 0" class="empty-state">
          <n-icon size="64" color="rgba(255,255,255,0.3)"><DocumentOutline /></n-icon>
          <span class="empty-text">暂无预览内容</span>
          <span class="empty-hint">请确保试卷包含题目</span>
        </div>

        <!-- 页面预览 -->
        <div v-else id="print-area" class="print-area">
          <div
            v-for="(page, index) in pages"
            :key="index"
            :id="'page-' + index"
            class="page-wrapper"
          >
            <!-- 页码标签 -->
            <div class="page-label">
              <span class="page-label-text">第 {{ index + 1 }} 页 / 共 {{ pages.length }} 页</span>
            </div>

            <div
              class="paper-content page-sheet"
              :class="{ 'is-a3': paperSize === 'A3' }"
              contenteditable="true"
            >
              <template v-if="page.hasHeader">
                <h1 class="paper-title">{{ paper?.paper_name }}</h1>
                <p v-if="paper?.paper_desc" class="paper-desc">{{ paper.paper_desc }}</p>
                <div class="paper-meta">
                  <span class="meta-item">
                    <strong>时长：</strong>{{ paper.exam_duration }}分钟
                  </span>
                  <span class="meta-divider">|</span>
                  <span class="meta-item">
                    <strong>形式：</strong>{{ paper.is_closed_book ? '闭卷' : '开卷' }}
                  </span>
                  <span class="meta-divider">|</span>
                  <span class="meta-item">
                    <strong>总分：</strong>{{ paper.total_score }}分
                  </span>
                </div>
              </template>

              <div v-for="q in page.questions" :key="q.question_id" class="q-item">
                <div class="q-header">
                  <span class="q-number">{{ q.question_sort }}</span>
                  <span v-if="q.question_score" class="q-score">{{ q.question_score }}分</span>
                </div>
                <div class="q-content" v-html="formatQuestionContent(q.question_content)"></div>
                <div v-if="showAnswers" class="q-answer-section">
                  <div v-if="q.question_answer" class="answer-row">
                    <span class="answer-label">答案</span>
                    <span class="answer-text">{{ q.question_answer }}</span>
                  </div>
                  <div v-if="q.question_analysis" class="answer-row">
                    <span class="answer-label">解析</span>
                    <span class="answer-text">{{ q.question_analysis }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  </n-modal>
</template>

<style scoped>
/* ========== 头部样式 ========== */
.modal-header {
  display: flex;
  align-items: center;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 600;
  font-size: 16px;
}

.title-icon {
  color: #2080f0;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

/* 按钮组圆角优化 */
.header-actions :deep(.n-button-group .n-button) {
  border-radius: 10px !important;
}

.header-actions :deep(.n-button-group .n-button:first-child) {
  border-radius: 10px 0 0 10px !important;
}

.header-actions :deep(.n-button-group .n-button:last-child) {
  border-radius: 0 10px 10px 0 !important;
}

.header-actions :deep(.n-button) {
  border-radius: 10px;
}

.header-actions :deep(.n-checkbox) {
  border-radius: 8px;
}

/* ========== 主容器布局 ========== */
.preview-container {
  display: flex;
  flex: 1;
  overflow: hidden;
  background: #f0f2f5;
  border-radius: 16px;
}

/* ========== 左侧信息面板 ========== */
.info-panel {
  width: 240px;
  flex-shrink: 0;
  background: #fff;
  border-right: 1px solid #e8e8e8;
  padding: 24px 20px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  border-radius: 16px 0 0 16px;
}

.info-title {
  font-size: 13px;
  font-weight: 600;
  color: #333;
  margin: 0 0 16px 0;
  padding-bottom: 10px;
  border-bottom: 2px solid #2080f0;
  display: inline-block;
  border-radius: 1px;
}

.paper-info {
  display: flex;
  flex-direction: column;
  gap: 14px;
  background: #f8fafc;
  padding: 16px;
  border-radius: 16px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-label {
  font-size: 11px;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.info-value {
  font-size: 13px;
  color: #333;
  font-weight: 500;
  word-break: break-all;
}

.info-value.highlight {
  color: #2080f0;
  font-size: 18px;
  font-weight: 600;
}

/* 页面导航 */
.page-nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  margin-top: 8px;
}

.page-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
  flex: 1;
  padding: 4px;
}

.page-thumb {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: #f8f9fa;
  border-radius: 14px;
  cursor: pointer;
  transition: all 0.25s ease;
  border: 1px solid transparent;
}

.page-thumb:hover {
  background: #e8f4ff;
  border-color: #2080f0;
  transform: translateX(4px);
  box-shadow: 0 4px 12px rgba(32, 128, 240, 0.15);
}

.page-thumb.has-header {
  border-left: 4px solid #2080f0;
  border-radius: 4px 14px 14px 4px;
}

.page-num {
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.page-num::before {
  content: '第 ';
  font-weight: 400;
  color: #666;
}

.page-num::after {
  content: ' 页';
  font-weight: 400;
  color: #666;
}

.page-questions {
  font-size: 11px;
  color: #666;
  background: #e8eef5;
  padding: 4px 10px;
  border-radius: 20px;
  font-weight: 500;
}

.page-empty {
  font-size: 13px;
  color: #999;
  text-align: center;
  padding: 24px;
  background: #f8f9fa;
  border-radius: 14px;
}

/* ========== 主预览区 ========== */
.preview-main {
  flex: 1;
  background: linear-gradient(180deg, #3a3d42 0%, #4a4e54 100%);
  padding: 36px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  border-radius: 0 16px 16px 0;
}

.measure-box {
  visibility: hidden;
  position: absolute;
  top: -9999px;
  left: -9999px;
  z-index: -1;
  overflow: visible;
}

/* 加载和空状态 */
.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20px;
  padding: 100px 0;
  color: rgba(255, 255, 255, 0.85);
  flex: 1;
}

.loading-text {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.65);
}

.empty-text {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.6);
  margin-top: 8px;
}

.empty-hint {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.4);
}

/* 打印区域 */
.print-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 40px;
  width: 100%;
}

/* 页面包装器 */
.page-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  animation: fadeInUp 0.4s ease;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.page-label {
  margin-bottom: 16px;
}

.page-label-text {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.8);
  background: rgba(0, 0, 0, 0.35);
  padding: 6px 20px;
  border-radius: 20px;
  font-weight: 500;
  backdrop-filter: blur(4px);
}

/* ========== 纸张内容样式 ========== */
.paper-content {
  background: white;
  width: 210mm;
  height: 297mm;
  padding: 25.4mm;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.3);
  outline: none;
  font-family: 'Microsoft YaHei', 'PingFang SC', 'Hiragino Sans GB', sans-serif;
  color: #333;
  box-sizing: border-box;
  overflow: hidden;
  position: relative;
  border-radius: 16px;
  transition: all 0.3s ease;
}

.paper-content:hover {
  box-shadow: 0 16px 56px rgba(0, 0, 0, 0.4);
  transform: translateY(-2px);
}

.paper-content.is-a3 {
  width: 420mm;
  height: 297mm;
  padding: 15mm;
  column-count: 2;
  column-gap: 30px;
  column-rule: 1px solid #e5e5e5;
  column-fill: auto;
}

/* 试卷头部 */
.paper-title {
  font-size: 24px;
  font-weight: 700;
  color: #1a1a1a;
  text-align: center;
  margin: 0 0 16px 0;
  letter-spacing: 2px;
}

.paper-desc {
  font-size: 14px;
  color: #555;
  text-indent: 2em;
  line-height: 1.8;
  margin: 0 0 16px 0;
  text-align: justify;
}

.paper-meta {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  color: #666;
  margin-bottom: 28px;
  padding: 12px 20px;
  background: #f8fafc;
  border-radius: 14px;
  border: 1px dashed #e0e0e0;
}

.meta-item strong {
  color: #333;
}

.meta-divider {
  color: #ddd;
}

.paper-content.is-a3 .paper-title,
.paper-content.is-a3 .paper-desc,
.paper-content.is-a3 .paper-meta {
  column-span: all;
}

/* ========== 题目样式 ========== */
.q-item {
  margin-bottom: 24px;
  break-inside: avoid;
  page-break-inside: avoid;
  padding: 16px;
  background: #fafbfc;
  border-radius: 14px;
  border: 1px solid #f0f0f0;
  transition: all 0.2s ease;
}

.q-item:hover {
  border-color: #e0e8f0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.q-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.q-number {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  height: 28px;
  background: linear-gradient(135deg, #2080f0 0%, #1a6ed8 100%);
  color: white;
  font-size: 13px;
  font-weight: 600;
  border-radius: 10px;
  padding: 0 8px;
  box-shadow: 0 2px 6px rgba(32, 128, 240, 0.3);
}

.q-score {
  font-size: 12px;
  color: #e69500;
  font-weight: 600;
  background: linear-gradient(135deg, #fff8e6 0%, #fff3d6 100%);
  padding: 4px 12px;
  border-radius: 20px;
  border: 1px solid #ffe4a0;
}

.q-content {
  font-size: 14px;
  line-height: 1.85;
  color: #333;
  text-align: justify;
  padding-left: 38px;
}

/* 答案区域 */
.q-answer-section {
  margin-top: 14px;
  margin-left: 38px;
  padding: 14px 18px;
  background: linear-gradient(135deg, #f0f7ff 0%, #e6f2ff 100%);
  border-radius: 14px;
  border-left: 4px solid #2080f0;
  box-shadow: 0 2px 8px rgba(32, 128, 240, 0.08);
}

.answer-row {
  display: flex;
  gap: 14px;
  margin-bottom: 8px;
  font-size: 13px;
  line-height: 1.7;
  align-items: flex-start;
}

.answer-row:last-child {
  margin-bottom: 0;
}

.answer-label {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 600;
  color: white;
  background: linear-gradient(135deg, #2080f0 0%, #1a6ed8 100%);
  padding: 4px 12px;
  border-radius: 10px;
  height: fit-content;
  box-shadow: 0 2px 4px rgba(32, 128, 240, 0.25);
}

.answer-text {
  color: #444;
  flex: 1;
}

/* ========== 深色模式适配 ========== */
:root[data-theme="dark"] .info-panel {
  background: #2c2c32;
  border-color: #3c3c44;
  border-radius: 16px 0 0 16px;
}

:root[data-theme="dark"] .paper-info {
  background: #363640;
}

:root[data-theme="dark"] .info-label {
  color: #888;
}

:root[data-theme="dark"] .info-value {
  color: #e0e0e0;
}

:root[data-theme="dark"] .page-thumb {
  background: #3c3c44;
}

:root[data-theme="dark"] .page-thumb:hover {
  background: #2a4060;
}

:root[data-theme="dark"] .page-num,
:root[data-theme="dark"] .info-title {
  color: #e0e0e0;
}

:root[data-theme="dark"] .preview-container {
  background: #1c1c1e;
}

:root[data-theme="dark"] .page-empty {
  background: #363640;
}
</style>
