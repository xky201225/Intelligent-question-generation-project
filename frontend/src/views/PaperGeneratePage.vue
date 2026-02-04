<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { http } from '../api/http'

const loading = ref(false)
const error = ref('')
const result = ref(null)
const saved = ref(null)

const strategyText = ref(
  JSON.stringify(
    {
      paper_name: '示例试卷',
      subject_id: 1,
      shuffle: true,
      sections: [
        { name: '选择题', type_id: 1, difficulty_id: 1, chapter_ids: [], count: 5, score_each: 2 },
        { name: '填空题', type_id: 2, difficulty_id: 2, chapter_ids: [], count: 5, score_each: 2 },
      ],
    },
    null,
    2,
  ),
)

const parsedStrategy = computed(() => {
  try {
    return JSON.parse(strategyText.value)
  } catch {
    return null
  }
})

async function preview() {
  if (!parsedStrategy.value) {
    ElMessage.error('策略 JSON 解析失败')
    return
  }
  loading.value = true
  error.value = ''
  saved.value = null
  try {
    const resp = await http.post('/papers/generate', { strategy: parsedStrategy.value })
    result.value = resp.data
  } catch (e) {
    error.value = e?.message || '生成失败'
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!parsedStrategy.value) {
    ElMessage.error('策略 JSON 解析失败')
    return
  }
  loading.value = true
  error.value = ''
  try {
    const resp = await http.post('/papers', { strategy: parsedStrategy.value, creator: 'creator' })
    saved.value = resp.data
    ElMessage.success(`已保存试卷 paper_id=${resp.data.paper_id}`)
  } catch (e) {
    error.value = e?.message || '保存失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  result.value = null
})
</script>

<template>
  <div class="page">
    <el-card>
      <template #header>
        <div class="header">
          <div>组卷策略 JSON</div>
          <div class="actions">
            <el-button :loading="loading" @click="preview">生成预览</el-button>
            <el-button type="primary" :loading="loading" @click="save">保存试卷</el-button>
          </div>
        </div>
      </template>

      <el-alert v-if="error" :title="error" type="error" show-icon />
      <el-input v-model="strategyText" type="textarea" :rows="16" placeholder="粘贴组卷策略 JSON" />
      <div v-if="!parsedStrategy" class="hint">当前 JSON 不合法，无法生成</div>
      <div v-if="saved" class="hint">已保存：paper_id={{ saved.paper_id }}，共{{ saved.question_count }}题，总分{{ saved.total_score }}</div>
    </el-card>

    <el-card v-if="result">
      <template #header>
        <div class="header">
          <div>预览结果</div>
          <div class="hint">总分：{{ result.paper.total_score }}</div>
        </div>
      </template>

      <el-table :data="result.questions" height="560">
        <el-table-column prop="question_sort" label="序号" width="90" />
        <el-table-column prop="section_name" label="部分" width="140" />
        <el-table-column prop="question_id" label="题目ID" width="110" />
        <el-table-column prop="question_score" label="分值" width="90" />
        <el-table-column prop="chapter_id" label="章节ID" width="100" />
        <el-table-column prop="type_id" label="题型ID" width="100" />
        <el-table-column prop="difficulty_id" label="难度ID" width="100" />
        <el-table-column label="题干" min-width="360">
          <template #default="{ row }">
            <div class="content">{{ row.question_content }}</div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
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
}

.hint {
  margin-top: 8px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.content {
  max-height: 80px;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  white-space: pre-wrap;
}
</style>

