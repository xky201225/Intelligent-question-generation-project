<script setup>
import { computed, ref } from 'vue'
import { asBlob } from 'html-docx-js-typescript'
import { saveAs } from 'file-saver'
import { ElMessage } from 'element-plus'
import { Download, Printer, Document } from '@element-plus/icons-vue'
import { http } from '../api/http'

const props = defineProps({
  visible: Boolean,
  paper: Object,
  questions: Array,
})

const showAnswers = ref(false)
const paperSize = ref('A4') // A4 | A3
const pages = ref([])
const isCalculating = ref(false)
const measureRef = ref(null)

const emit = defineEmits(['update:visible'])

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
})

// MM to PX conversion (approximate for screen, but we rely on offsetHeight)
const MM_TO_PX = 3.78

function getPageDimensions() {
  if (paperSize.value === 'A3') {
    // A3 Landscape: Height 297mm, Padding 15mm
    // Content Height = 297 - 30 = 267mm
    return {
      totalHeight: 267 * MM_TO_PX, // ~1009px
      colCount: 2
    }
  } else {
    // A4 Portrait: Height 297mm, Padding 25.4mm
    // Content Height = 297 - 50.8 = 246.2mm
    return {
      totalHeight: 246.2 * MM_TO_PX, // ~930px
      colCount: 1
    }
  }
}

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
  
  // 1. Determine Layout Constants (in Pixels)
  // We use a temporary ruler to get accurate mm->px conversion for current screen
  container.style.cssText = 'position:absolute; visibility:hidden; height:297mm; width:210mm; padding:0; border:none; margin:0;'
  const height297mm = container.offsetHeight
  
  // A4 Constants
  // Padding 25.4mm (1 inch)
  container.style.height = '25.4mm'
  const paddingA4 = container.offsetHeight
  const contentHeightA4 = height297mm - (paddingA4 * 2)
  const contentWidthA4 = container.offsetWidth - (paddingA4 * 2) // Approx, strictly we need width check
  
  // A3 Constants
  // Padding 15mm
  container.style.height = '15mm'
  const paddingA3 = container.offsetHeight
  const contentHeightA3 = height297mm - (paddingA3 * 2) // A3 landscape height is 297mm
  // Width: A3 is 420mm wide.
  container.style.width = '420mm'
  const width420mm = container.offsetWidth
  const fullContentWidthA3 = width420mm - (paddingA3 * 2)
  // Columns: Gap 30px
  const gap30px = 30 // CSS px
  const colWidthA3 = (fullContentWidthA3 - gap30px) / 2
  
  // Clear container styles for measurement
  container.style.cssText = 'position:absolute; visibility:hidden; top:-9999px; left:-9999px;'
  container.className = 'paper-content' // Keep base class for font styles
  
  // CRITICAL FIX: The class .paper-content has fixed height: 297mm in CSS.
  // We MUST override this to 'auto' to measure the natural height of content.
  // Also reset columns to avoid multi-column rendering during measurement.
  // CRITICAL FIX 2: We must also reset PADDING. 
  // The .paper-content class has padding (25.4mm or 15mm).
  // When we set width = colWidth, if padding is present, the inner content width becomes (colWidth - padding*2).
  // This causes text to wrap excessively, making elements much taller than they really are in the column.
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
  
  // 2. Measure Header
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
  // Header width depends on mode
  if (paperSize.value === 'A3') {
      container.style.width = fullContentWidthA3 + 'px'
  } else {
      container.style.width = contentWidthA4 + 'px'
  }
  const headerHeight = container.offsetHeight
  
  // 3. Measure All Questions
  const questions = props.questions || []
  const questionHeights = []
  
  // Set container to Column Width for measuring questions
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
      // We take the first child's height + margin
      // Or just container height since it only has one child
      // Note: .q-item has margin-bottom 15px in CSS.
      // container.offsetHeight includes content + padding + border. 
      // It does NOT include margin of the child if overflow is hidden/auto, but here it's visible.
      // Safer to get computed style of the child.
      const child = container.firstElementChild
      const style = window.getComputedStyle(child)
      const mt = parseFloat(style.marginTop) || 0
      const mb = parseFloat(style.marginBottom) || 0
      questionHeights.push(child.offsetHeight + mt + mb)
  }
  
  // 4. Simulate Pagination (Column Filling)
  const isA3Mode = paperSize.value === 'A3'
  const maxColHeight = isA3Mode ? contentHeightA3 : contentHeightA4
  const maxColsPerPage = isA3Mode ? 2 : 1
  
  // Safety buffer (e.g. 5px) to avoid rounding issues causing overflow
  const SAFETY = 5
  
  let currentPages = []
  let currentPageQuestions = []
  let colsUsedOnPage = 0 // 0-indexed (0 = 1st col)
  let currentColHeight = 0
  
  // Initialize Page 1
  // Page 1 has header
  // Header "consumes" vertical space from ALL columns on the first page?
  // In `column-span: all`, the element sits at the top, and columns start below it.
  // So the effective height of columns on Page 1 is `maxColHeight - headerHeight`.
  
  let availableHeightOnPage = maxColHeight - headerHeight - SAFETY
  // If header is huge, it might take whole page, but let's assume it fits.
  if (availableHeightOnPage < 0) availableHeightOnPage = 0 
  
  for (let i = 0; i < questions.length; i++) {
      const q = questions[i]
      const h = questionHeights[i]
      
      // Check if fits in current column
      if (currentColHeight + h <= availableHeightOnPage) {
          // Fits
          currentPageQuestions.push(q)
          currentColHeight += h
      } else {
          // Does not fit in current column.
          // Move to next column?
          colsUsedOnPage++
          
          if (colsUsedOnPage < maxColsPerPage) {
              // We have another column on this page
              // Reset column height
              currentColHeight = 0
              // Now add question to this new column
              // Does it fit in a fresh column?
              if (h <= availableHeightOnPage) {
                   currentPageQuestions.push(q)
                   currentColHeight += h
              } else {
                  // Question is taller than the entire column space available!
                  // Edge case. We must put it here anyway or it will never fit anywhere.
                  // Or if it's Page 1 and space is small due to header, maybe move to Page 2?
                  if (availableHeightOnPage < maxColHeight && h <= maxColHeight - SAFETY) {
                       // It would fit on a full page (Page 2).
                       // So skip the rest of Page 1 columns and go to Page 2.
                       // Force new page
                       currentPages.push({ questions: currentPageQuestions, hasHeader: currentPages.length === 0 })
                       currentPageQuestions = [q]
                       colsUsedOnPage = 0
                       currentColHeight = h
                       availableHeightOnPage = maxColHeight - SAFETY // Page 2 full height
                  } else {
                       // It's just huge. Put it here.
                       currentPageQuestions.push(q)
                       currentColHeight += h
                  }
              }
          } else {
              // No more columns on this page.
              // Push Page
              currentPages.push({ questions: currentPageQuestions, hasHeader: currentPages.length === 0 })
              
              // Start New Page
              currentPageQuestions = [q]
              colsUsedOnPage = 0
              currentColHeight = h
              availableHeightOnPage = maxColHeight - SAFETY // New page has full height
          }
      }
  }
  
  // Push final page
  if (currentPageQuestions.length > 0) {
      currentPages.push({ questions: currentPageQuestions, hasHeader: currentPages.length === 0 })
  }
  
  pages.value = currentPages
  isCalculating.value = false
}

import { watch, nextTick, onMounted } from 'vue'

watch([() => props.visible, () => props.questions, paperSize, showAnswers], () => {
    if (props.visible) {
        calculateLayout()
    }
}, { immediate: true })

// ... existing code ...

async function doExportWord() {
  try {
    // Use backend generation for better layout support (A3 columns)
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
    
    ElMessage.success('导出成功')
  } catch (e) {
    console.error(e)
    ElMessage.error('导出失败: ' + (e?.message || '未知错误'))
  }
}

function doExportPdf() {
  const el = document.getElementById('print-area')
  const content = el ? el.innerHTML : ''

  const printWindow = window.open('', '_blank')
  if (!printWindow) {
    ElMessage.error('浏览器拦截了打印窗口，请允许弹窗后重试')
    return
  }

  const safeTitle = String(props.paper?.paper_name || 'paper')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  const isA3 = paperSize.value === 'A3'
  // Define styles for the print window
  const pageStyle = isA3 
    ? '@page { size: A3 landscape; margin: 0; }' // Margins handled by padding in div
    : '@page { size: A4; margin: 0; }'

  const html = `<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>${safeTitle}</title>
    <style>
      ${pageStyle}
      html, body { margin: 0; padding: 0; }
      body { font-family: 'Microsoft YaHei', sans-serif; color: #333; }
      img { max-width: 100%; }
      table { width: 100%; border-collapse: collapse; }
      
      .paper-content {
        background: white;
        width: 210mm;
        height: 297mm; /* Force height for each page */
        padding: 25.4mm;
        box-sizing: border-box;
        overflow: hidden;
        page-break-after: always; /* Legacy */
        break-after: page;
        position: relative;
      }
      
      .paper-content.is-a3 {
        width: 420mm;
        height: 297mm;
        padding: 15mm;
        column-count: 2;
        column-gap: 30px;
        column-rule: 1px solid #ccc;
      }
      
      /* Header spans all columns in A3 */
      .paper-content.is-a3 h1,
      .paper-content.is-a3 .paper-meta {
        column-span: all;
        text-align: center;
      }
      
      .q-item { break-inside: avoid; page-break-inside: avoid; margin-bottom: 15px; }
      
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
  // Replace patterns like " A. ", " B. " with a newline before them to ensure they start on a new line
  // Use a regex that looks for whitespace followed by A-F dot
  return content.replace(/(\s|&nbsp;)([A-F]\.)/g, '<br><br>$2')
}
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    fullscreen
    destroy-on-close
    class="preview-dialog"
    :show-close="false"
  >
    <template #header>
       <div class="preview-header">
           <div class="header-left">
               <el-icon class="icon"><Document /></el-icon>
               <span class="title">导出预览</span>
           </div>
           <div class="header-right">
               <el-radio-group v-model="paperSize" style="margin-right: 20px">
                 <el-radio-button label="A4">A4 (分页)</el-radio-button>
                 <el-radio-button label="A3">A3 (分栏)</el-radio-button>
               </el-radio-group>
               <el-switch
                 v-model="showAnswers"
                 active-text="显示答案/解析"
                 inactive-text="隐藏答案/解析"
                 style="margin-right: 20px"
               />
               <el-button @click="doExportWord" :icon="Download">导出 Word</el-button>
               <el-button @click="doExportPdf" :icon="Printer">导出 PDF (打印)</el-button>
               <el-button @click="dialogVisible = false" type="primary">关闭</el-button>
           </div>
       </div>
    </template>

    <div class="preview-wrapper">
      <!-- Hidden Measurement Container -->
      <div ref="measureRef" class="measure-box paper-content" :class="{ 'is-a3': paperSize === 'A3' }"></div>

      <!-- Real Pages -->
      <div id="print-area">
        <div 
          v-for="(page, index) in pages" 
          :key="index"
          class="paper-content page-sheet"
          :class="{ 'is-a3': paperSize === 'A3' }"
          contenteditable="true"
        >
            <!-- Header (Only on first page) -->
            <template v-if="page.hasHeader">
                <h1 style="text-align: center; margin-bottom: 20px;">{{ paper?.paper_name }}</h1>
                <p v-if="paper?.paper_desc" class="paper-meta" style="margin-bottom: 20px; text-indent: 2em;">{{ paper.paper_desc }}</p>
                <p v-if="paper" class="paper-meta" style="margin-bottom: 20px; text-align: center;">
                    时长：{{ paper.exam_duration }}分钟 &nbsp;&nbsp; 
                    {{ paper.is_closed_book ? '闭卷' : '开卷' }} &nbsp;&nbsp;
                    总分：{{ paper.total_score }}
                </p>
            </template>

            <!-- Questions -->
            <div v-for="(q, index) in page.questions" :key="q.question_id" class="q-item">
              <p class="q-title">
                <strong>{{ q.question_sort }}. </strong>
                <span v-if="q.question_score">（{{ q.question_score }}分）</span>
                <span v-html="formatQuestionContent(q.question_content)"></span>
              </p>
              <div v-if="showAnswers" class="q-answer-section">
                <p v-if="q.question_answer"><strong>答案：</strong>{{ q.question_answer }}</p>
                <p v-if="q.question_analysis"><strong>解析：</strong>{{ q.question_analysis }}</p>
              </div>
            </div>
        </div>
      </div>
    </div>

    <template #footer>
        <!-- Footer removed as buttons moved to header -->
    </template>
  </el-dialog>
</template>

<style scoped>
.preview-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-right: 20px;
}

.header-left {
    display: flex;
    align-items: center;
    gap: 10px;
}

.header-left .icon {
    font-size: 20px;
    color: var(--el-color-primary);
}

.header-left .title {
    font-size: 18px;
    font-weight: 600;
    color: var(--el-text-color-primary);
}

.header-left .subtitle {
    font-size: 13px;
    color: var(--el-text-color-secondary);
}

.preview-wrapper {
    background-color: #525659; /* Darker background for better contrast like PDF viewers */
    padding: 40px 0;
    display: flex;
    justify-content: center;
    min-height: 100%;
    overflow-y: auto;
}

.paper-content {
    background: white;
    width: 210mm; /* A4 width */
    height: 297mm; /* Changed from min-height to fixed height for pagination */
    padding: 25.4mm; /* Standard 1 inch margins */
    box-shadow: 0 0 10px rgba(0,0,0,0.3);
    outline: none;
    font-family: 'Microsoft YaHei', sans-serif;
    color: #333;
    box-sizing: border-box;
    overflow: hidden; /* Hide overflow */
    position: relative;
}

.paper-content.is-a3 {
    width: 420mm; /* A3 width */
    height: 297mm; /* A3 height (landscape) */
    padding: 15mm;
    column-count: 2;
    column-gap: 30px;
    column-rule: 1px solid #ccc;
    column-fill: auto; /* Prevent balancing columns, fill first then second */
}

.measure-box {
    visibility: hidden;
    position: absolute;
    top: -9999px;
    left: -9999px;
    z-index: -1;
    overflow: visible;
}

.page-sheet {
    margin-bottom: 20px;
}

/* Ensure title spans across columns in A3 preview mode */
.paper-content.is-a3 h1,
.paper-content.is-a3 .paper-meta {
    column-span: all;
    text-align: center;
}

.q-item {
    margin-bottom: 15px;
    break-inside: avoid; /* Prevent splitting inside a question */
}

.q-answer-section {
    margin-top: 8px;
    padding: 10px;
    background-color: #f8f9fa;
    border-radius: 4px;
    font-size: 14px;
    color: #666;
    line-height: 1.6;
}

@media print {
    :global(html), :global(body) {
        height: auto !important;
        overflow: visible !important;
        background: white !important;
    }
    :global(.el-overlay), :global(.el-overlay-dialog), :global(.el-dialog) {
        background: transparent !important;
    }
    .preview-wrapper {
        padding: 0;
        background: white;
        overflow: visible !important;
    }
    .paper-content {
        box-shadow: none;
        width: 210mm;
        min-height: auto;
        margin: 0;
    }
    .el-dialog__header, .el-dialog__footer {
        display: none !important;
    }
}
</style>
