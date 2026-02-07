<script setup>
import { computed, ref } from 'vue'
import { asBlob } from 'html-docx-js-typescript'
import { saveAs } from 'file-saver'
import { ElMessage } from 'element-plus'
import { Download, Printer, Document } from '@element-plus/icons-vue'

const props = defineProps({
  visible: Boolean,
  paper: Object,
  questions: Array,
})

const showAnswers = ref(false)
const emit = defineEmits(['update:visible'])

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
})

async function doExportWord() {
  try {
    const content = document.getElementById('paper-content').innerHTML
    
    // Wrap in a basic HTML structure for Word
    const html = `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="UTF-8">
        <style>
          body { font-family: 'Microsoft YaHei'; }
        </style>
      </head>
      <body>
        ${content}
      </body>
      </html>
    `
    
    const blob = await asBlob(html, {
      orientation: 'portrait',
      margins: { top: 720, bottom: 720, left: 720, right: 720 } // twips
    })
    
    saveAs(blob, `${props.paper.paper_name || 'paper'}.docx`)
    ElMessage.success('导出成功')
  } catch (e) {
    console.error(e)
    ElMessage.error('导出失败: ' + e.message)
  }
}

function doExportPdf() {
  const el = document.getElementById('paper-content')
  const content = el ? el.innerHTML : ''

  const printWindow = window.open('', '_blank')
  if (!printWindow) {
    ElMessage.error('浏览器拦截了打印窗口，请允许弹窗后重试')
    return
  }

  const safeTitle = String(props.paper?.paper_name || 'paper')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  const html = `<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>${safeTitle}</title>
    <style>
      @page { size: A4; margin: 25.4mm; }
      html, body { margin: 0; padding: 0; }
      body { font-family: 'Microsoft YaHei', sans-serif; color: #333; }
      img { max-width: 100%; }
      table { width: 100%; border-collapse: collapse; }
      .q-item { break-inside: avoid; page-break-inside: avoid; }
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
      <div id="paper-content" class="paper-content" contenteditable="true">
        <h1 style="text-align: center; margin-bottom: 20px;">{{ paper?.paper_name }}</h1>
        <p v-if="paper?.paper_desc" style="margin-bottom: 20px; text-indent: 2em;">{{ paper.paper_desc }}</p>
        <p v-if="paper" style="margin-bottom: 20px; text-align: center;">
            时长：{{ paper.exam_duration }}分钟 &nbsp;&nbsp; 
            {{ paper.is_closed_book ? '闭卷' : '开卷' }} &nbsp;&nbsp;
            总分：{{ paper.total_score }}
        </p>

        <div v-for="(q, index) in questions" :key="q.question_id" class="q-item">
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
    min-height: 297mm;
    padding: 25.4mm; /* Standard 1 inch margins */
    box-shadow: 0 0 10px rgba(0,0,0,0.3);
    outline: none;
    font-family: 'Microsoft YaHei', sans-serif;
    color: #333;
    box-sizing: border-box;
}

.q-item {
    margin-bottom: 15px;
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
