<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Plus, Refresh, Delete, Check } from '@element-plus/icons-vue'
import { http } from '../api/http'

const loading = ref(false)
const error = ref('')
const saved = ref(null)

const subjects = ref([])
const textbooks = ref([])
const chapterTree = ref([])
const types = ref([])
const difficulties = ref([])

const filters = reactive({
  q: '',
  subject_id: null,
  textbook_id: null,
  author: '',
  publisher: '',
  chapter_ids: [],
  type_ids: [],
  difficulty_ids: [],
  review_status: 1,
  page: 1,
  page_size: 20,
})

const available = reactive({
  items: [],
  total: 0,
})

const availableSelection = ref([])

const paper = reactive({
  paper_name: '未命名试卷',
  exam_duration: 120,
  is_closed_book: false,
  paper_desc: '',
  creator: 'creator',
})

const picked = ref([])
const dragIndex = ref(-1)

const authorOptions = computed(() => {
  const set = new Set()
  for (const t of textbooks.value) {
    if (t.author) set.add(t.author)
  }
  return Array.from(set)
})

const publisherOptions = computed(() => {
  const set = new Set()
  for (const t of textbooks.value) {
    if (t.publisher) set.add(t.publisher)
  }
  return Array.from(set)
})

const pickedTotalScore = computed(() => {
  return picked.value.reduce((sum, it) => sum + Number(it.question_score || 0), 0)
})

function typeName(type_id) {
  const t = types.value.find((x) => x.type_id === type_id)
  return t ? t.type_name : String(type_id ?? '')
}

function difficultyName(difficulty_id) {
  const d = difficulties.value.find((x) => x.difficulty_id === difficulty_id)
  return d ? d.difficulty_name : String(difficulty_id ?? '')
}

async function loadDicts() {
  const [s, t, d] = await Promise.all([
    http.get('/dicts/subjects'),
    http.get('/dicts/question-types'),
    http.get('/dicts/difficulties'),
  ])
  subjects.value = s.data.items || []
  types.value = t.data.items || []
  difficulties.value = d.data.items || []
}

async function loadTextbooks() {
  const resp = await http.get('/textbooks', {
    params: filters.subject_id ? { subject_id: filters.subject_id } : {},
  })
  textbooks.value = resp.data.items || []
}

async function loadChapters() {
  if (!filters.textbook_id) {
    chapterTree.value = []
    return
  }
  const resp = await http.get(`/textbooks/${filters.textbook_id}/chapters`)
  chapterTree.value = resp.data.tree || []
}

async function search() {
  loading.value = true
  error.value = ''
  try {
    const params = {
      page: filters.page,
      page_size: filters.page_size,
      q: filters.q || undefined,
      subject_id: filters.subject_id || undefined,
      textbook_id: filters.textbook_id || undefined,
      author: filters.author || undefined,
      publisher: filters.publisher || undefined,
      chapter_id: filters.chapter_ids.length > 0 ? filters.chapter_ids.join(',') : undefined,
      type_id: filters.type_ids.length > 0 ? filters.type_ids.join(',') : undefined,
      difficulty_id: filters.difficulty_ids.length > 0 ? filters.difficulty_ids.join(',') : undefined,
      review_status: filters.review_status,
    }
    const resp = await http.get('/questions', { params })
    available.items = resp.data.items || []
    available.total = resp.data.total || 0
  } catch (e) {
    error.value = e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function onAvailableSelectionChange(rows) {
  availableSelection.value = rows || []
}

function renumber() {
  picked.value.forEach((it, idx) => {
    it.question_sort = idx + 1
  })
}

function addSelected() {
  const existing = new Set(picked.value.map((x) => x.question_id))
  const toAdd = (availableSelection.value || []).filter((x) => !existing.has(x.question_id))
  if (toAdd.length === 0) {
    ElMessage.warning('没有可加入的题目')
    return
  }
  for (const q of toAdd) {
    picked.value.push({
      question_id: q.question_id,
      question_sort: picked.value.length + 1,
      question_score: q.question_score ?? 0,
      question_content: q.question_content,
      type_id: q.type_id,
      difficulty_id: q.difficulty_id,
      chapter_id: q.chapter_id,
    })
  }
  renumber()
}

function removePicked(index) {
  picked.value.splice(index, 1)
  renumber()
}

function clearPicked() {
  picked.value = []
}

function onDragStart(index) {
  dragIndex.value = index
}

function onDrop(index) {
  const from = dragIndex.value
  if (from < 0 || from === index) return
  const arr = picked.value.slice()
  const [moved] = arr.splice(from, 1)
  arr.splice(index, 0, moved)
  picked.value = arr
  dragIndex.value = -1
  renumber()
}

function validatePicked() {
  if (!filters.subject_id) {
    ElMessage.error('请先选择科目')
    return false
  }
  if (picked.value.length === 0) {
    ElMessage.error('请先选择题目加入试卷')
    return false
  }
  const sorts = picked.value.map((x) => Number(x.question_sort))
  if (sorts.some((x) => !Number.isInteger(x) || x < 1)) {
    ElMessage.error('题号必须是 >= 1 的整数')
    return false
  }
  const set = new Set(sorts)
  if (set.size !== sorts.length) {
    ElMessage.error('题号存在重复，请调整后再保存')
    return false
  }
  return true
}

async function savePaper() {
  if (!validatePicked()) return
  loading.value = true
  error.value = ''
  saved.value = null
  try {
    const items = picked.value.map((x) => ({
      question_id: x.question_id,
      question_sort: x.question_sort,
      question_score: x.question_score,
    }))
    const resp = await http.post('/papers/manual', {
      paper_name: paper.paper_name,
      paper_desc: paper.paper_desc,
      subject_id: filters.subject_id,
      exam_duration: paper.exam_duration,
      is_closed_book: paper.is_closed_book,
      creator: paper.creator,
      items,
    })
    saved.value = resp.data
    ElMessage.success(`已保存试卷 paper_id=${resp.data.paper_id}`)
  } catch (e) {
    error.value = e?.message || '保存失败'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadDicts()
})
</script>

<template>
  <div class="page">
    <el-alert v-if="error" :title="error" type="error" show-icon />

    <el-row :gutter="12">
      <el-col :span="15">
        <el-card>
          <template #header>
            <div class="header">
              <div>题目筛选</div>
              <div class="actions">
                <el-button :loading="loading" @click="search" :icon="Search">查询</el-button>
                <el-button type="primary" :loading="loading" @click="addSelected" :icon="Plus">加入试卷</el-button>
              </div>
            </div>
          </template>

          <div class="filters">
            <el-input v-model="filters.q" placeholder="关键词（题干/解析）" style="width: 220px" clearable @keyup.enter="search" :prefix-icon="Search" />

            <el-select
              v-model="filters.subject_id"
              clearable
              placeholder="科目"
              style="width: 160px"
              @change="
                async () => {
                  filters.textbook_id = null
                  filters.chapter_ids = []
                  await loadTextbooks()
                  await loadChapters()
                }
              "
            >
              <el-option v-for="s in subjects" :key="s.subject_id" :label="s.subject_name" :value="s.subject_id" />
            </el-select>

            <el-select
              v-model="filters.textbook_id"
              clearable
              placeholder="教材"
              style="width: 240px"
              @change="
                async () => {
                  filters.chapter_ids = []
                  await loadChapters()
                }
              "
            >
              <el-option v-for="t in textbooks" :key="t.textbook_id" :label="t.textbook_name" :value="t.textbook_id" />
            </el-select>

            <el-select v-model="filters.author" clearable placeholder="作者" style="width: 160px" @change="search">
              <el-option v-for="a in authorOptions" :key="a" :label="a" :value="a" />
            </el-select>

            <el-select v-model="filters.publisher" clearable placeholder="出版社" style="width: 180px" @change="search">
              <el-option v-for="p in publisherOptions" :key="p" :label="p" :value="p" />
            </el-select>

            <el-tree-select
              v-model="filters.chapter_ids"
              :data="chapterTree"
              :props="{ label: 'chapter_name', children: 'children', value: 'chapter_id' }"
              node-key="chapter_id"
              clearable
              multiple
              show-checkbox
              check-strictly
              collapse-tags
              collapse-tags-tooltip
              placeholder="章节"
              style="width: 240px"
              @change="search"
            />

            <el-select v-model="filters.type_ids" clearable multiple collapse-tags collapse-tags-tooltip placeholder="题型" style="width: 200px" @change="search">
              <el-option v-for="t in types" :key="t.type_id" :label="t.type_name" :value="t.type_id" />
            </el-select>

            <el-select
              v-model="filters.difficulty_ids"
              clearable
              multiple
              collapse-tags
              collapse-tags-tooltip
              placeholder="难度"
              style="width: 200px"
              @change="search"
            >
              <el-option v-for="d in difficulties" :key="d.difficulty_id" :label="d.difficulty_name" :value="d.difficulty_id" />
            </el-select>
          </div>

          <el-table :data="available.items" height="560" @selection-change="onAvailableSelectionChange">
            <el-table-column type="selection" width="48" />
            <el-table-column prop="question_id" label="ID" width="90" />
            <el-table-column prop="chapter_id" label="章节ID" width="90" />
            <el-table-column label="题型" width="110">
              <template #default="{ row }">
                {{ typeName(row.type_id) }}
              </template>
            </el-table-column>
            <el-table-column label="难度" width="110">
              <template #default="{ row }">
                {{ difficultyName(row.difficulty_id) }}
              </template>
            </el-table-column>
            <el-table-column prop="question_score" label="分值" width="80" />
            <el-table-column label="题干" min-width="360">
              <template #default="{ row }">
                <div class="content">{{ row.question_content }}</div>
              </template>
            </el-table-column>
          </el-table>

          <div class="pager">
            <el-pagination
              v-model:current-page="filters.page"
              v-model:page-size="filters.page_size"
              :total="available.total"
              :page-sizes="[10, 20, 50, 100]"
              layout="total, sizes, prev, pager, next"
              @size-change="
                () => {
                  filters.page = 1
                  search()
                }
              "
              @current-change="search"
            />
          </div>
        </el-card>
      </el-col>

      <el-col :span="9">
        <el-card>
          <template #header>
            <div class="header">
              <div>已选题目（{{ picked.length }}）</div>
              <div class="actions">
                <el-button @click="renumber" :icon="Refresh">重新编号</el-button>
                <el-button type="danger" @click="clearPicked" :icon="Delete">清空</el-button>
                <el-button type="primary" :loading="loading" @click="savePaper" :icon="Check">保存试卷</el-button>
              </div>
            </div>
          </template>

          <el-form label-width="80px" class="paper-form">
            <el-form-item label="试卷名">
              <el-input v-model="paper.paper_name" />
            </el-form-item>
            <el-form-item label="时长">
              <el-input-number v-model="paper.exam_duration" :min="1" :max="600" style="width: 100%" />
            </el-form-item>
            <el-form-item label="闭卷">
              <el-switch v-model="paper.is_closed_book" />
            </el-form-item>
            <el-form-item label="说明">
              <el-input v-model="paper.paper_desc" type="textarea" :rows="2" />
            </el-form-item>
          </el-form>

          <div class="total">总分：{{ pickedTotalScore }}</div>
          <div v-if="saved" class="hint">已保存：paper_id={{ saved.paper_id }}，共{{ saved.question_count }}题，总分{{ saved.total_score }}</div>

          <div class="picked-list">
            <div v-if="picked.length === 0" class="empty">从左侧筛选后勾选题目加入</div>

            <div
              v-for="(it, index) in picked"
              :key="it.question_id"
              class="picked-row"
              draggable="true"
              @dragstart="onDragStart(index)"
              @dragover.prevent
              @drop="onDrop(index)"
            >
              <div class="drag">≡</div>
              <div class="sort">
                <el-input-number v-model="it.question_sort" :min="1" :max="9999" size="small" />
              </div>
              <div class="meta">
                <div class="meta-top">
                  <span class="qid">#{{ it.question_id }}</span>
                  <span class="tag">{{ typeName(it.type_id) }}</span>
                  <span class="tag">{{ difficultyName(it.difficulty_id) }}</span>
                </div>
                <div class="meta-content">{{ it.question_content }}</div>
              </div>
              <div class="score">
                <el-input-number v-model="it.question_score" :min="0" :step="0.5" size="small" />
              </div>
              <div class="remove">
                <el-button link type="danger" @click="removePicked(index)" :icon="Delete">移除</el-button>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
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
  gap: 10px;
}

.actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.paper-form {
  margin-bottom: 10px;
}

.total {
  margin-bottom: 8px;
  font-weight: 600;
}

.hint {
  margin-bottom: 10px;
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

.picked-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 560px;
  overflow-y: auto;
  border-top: 1px solid var(--el-border-color);
  padding-top: 10px;
}

.empty {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.picked-row {
  display: grid;
  grid-template-columns: 16px 92px 1fr 110px 48px;
  align-items: start;
  gap: 8px;
  padding: 10px;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  background-color: var(--el-bg-color);
}

.drag {
  user-select: none;
  cursor: grab;
  color: var(--el-text-color-secondary);
  line-height: 28px;
}

.sort {
  padding-top: 2px;
}

.meta-top {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 6px;
  flex-wrap: wrap;
}

.qid {
  font-weight: 600;
}

.tag {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.meta-content {
  white-space: pre-wrap;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  color: var(--el-text-color-regular);
  font-size: 13px;
}

.score {
  padding-top: 2px;
}

.remove {
  padding-top: 2px;
  display: flex;
  justify-content: flex-end;
}
</style>
