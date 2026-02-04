<script setup>
import { onMounted, ref } from 'vue'
import { http } from '../api/http'

const loading = ref(false)
const error = ref('')

const subjects = ref([])
const questionTypes = ref([])
const difficulties = ref([])

async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    const [s, t, d] = await Promise.all([
      http.get('/dicts/subjects'),
      http.get('/dicts/question-types'),
      http.get('/dicts/difficulties'),
    ])
    subjects.value = s.data.items || []
    questionTypes.value = t.data.items || []
    difficulties.value = d.data.items || []
  } catch (e) {
    error.value = e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(loadAll)
</script>

<template>
  <div class="page">
    <div class="header">
      <div class="title">基础字典</div>
      <el-button :loading="loading" @click="loadAll">刷新</el-button>
    </div>

    <el-alert v-if="error" :title="error" type="error" show-icon />

    <el-card class="card" header="科目 subject_dict">
      <el-table :data="subjects" :loading="loading" height="260">
        <el-table-column prop="subject_id" label="ID" width="90" />
        <el-table-column prop="subject_name" label="名称" />
        <el-table-column prop="subject_code" label="编码" width="140" />
        <el-table-column prop="target_grade" label="年级" width="120" />
        <el-table-column prop="teach_type" label="类型" width="140" />
      </el-table>
    </el-card>

    <div class="grid">
      <el-card class="card" header="题型 question_type_dict">
        <el-table :data="questionTypes" :loading="loading" height="260">
          <el-table-column prop="type_id" label="ID" width="90" />
          <el-table-column prop="type_name" label="名称" />
          <el-table-column prop="type_code" label="编码" width="140" />
        </el-table>
      </el-card>

      <el-card class="card" header="难度 question_difficulty_dict">
        <el-table :data="difficulties" :loading="loading" height="260">
          <el-table-column prop="difficulty_id" label="ID" width="90" />
          <el-table-column prop="difficulty_name" label="名称" />
          <el-table-column prop="difficulty_level" label="等级" width="120" />
        </el-table>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.title {
  font-size: 18px;
  font-weight: 600;
}

.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.card {
  width: 100%;
}
</style>

