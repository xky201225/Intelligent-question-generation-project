<script setup>
import { onMounted, ref } from 'vue'
import { Refresh, User, Document, Files, Reading } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { http } from '../api/http'

const loading = ref(false)
const error = ref('')

const subjects = ref([])
const questionTypes = ref([])
const difficulties = ref([])

// 检测深色模式
const isDarkMode = ref(window.matchMedia('(prefers-color-scheme: dark)').matches)

const stats = ref({
  users: 0,
  subjects: 0,
  textbooks: 0,
  questions: 0,
  papers: 0,
  pending_questions: 0,
  pending_papers: 0
})

const trendChartRef = ref(null)
const pieChartRef = ref(null)

let trendChart = null
let pieChart = null

async function loadDashboard() {
  try {
    // 1. Load Stats
    const statsResp = await http.get('/dashboard/stats')
    stats.value = statsResp.data || {}

    // 2. Load Trend
    const trendResp = await http.get('/dashboard/trend')
    renderTrendChart(trendResp.data)

    // 3. Load Distribution
    const distResp = await http.get('/dashboard/distribution')
    renderPieChart(distResp.data.items)
  } catch (e) {
    console.error('Dashboard load failed', e)
  }
}

function renderTrendChart(data) {
  if (!trendChartRef.value) return
  if (trendChart) trendChart.dispose()
  
  trendChart = echarts.init(trendChartRef.value, isDarkMode.value ? 'dark' : null)
  const textColor = isDarkMode.value ? 'rgba(255,255,255,0.87)' : '#303133'
  const option = {
    backgroundColor: 'transparent',
    title: { text: '近30天系统活跃趋势', left: 'left', textStyle: { fontSize: 16, color: textColor } },
    tooltip: { trigger: 'axis' },
    legend: { data: ['题目新增', '试卷生成'], bottom: 0, textStyle: { color: textColor } },
    grid: { left: '3%', right: '4%', bottom: '10%', containLabel: true },
    xAxis: { type: 'category', boundaryGap: false, data: data.dates, axisLabel: { color: textColor }, axisLine: { lineStyle: { color: isDarkMode.value ? '#4c4d4f' : '#ccc' } } },
    yAxis: { type: 'value', axisLabel: { color: textColor }, axisLine: { lineStyle: { color: isDarkMode.value ? '#4c4d4f' : '#ccc' } }, splitLine: { lineStyle: { color: isDarkMode.value ? '#333' : '#eee' } } },
    series: [
      {
        name: '题目新增',
        type: 'line',
        data: data.questions,
        smooth: true,
        itemStyle: { color: '#409EFF' },
        areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: 'rgba(64,158,255,0.3)' }, { offset: 1, color: 'rgba(64,158,255,0)' }]) }
      },
      {
        name: '试卷生成',
        type: 'line',
        data: data.papers,
        smooth: true,
        itemStyle: { color: '#67C23A' },
        areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: 'rgba(103,194,58,0.3)' }, { offset: 1, color: 'rgba(103,194,58,0)' }]) }
      }
    ]
  }
  trendChart.setOption(option)
}

function renderPieChart(items) {
  if (!pieChartRef.value) return
  if (pieChart) pieChart.dispose()
  
  pieChart = echarts.init(pieChartRef.value, isDarkMode.value ? 'dark' : null)
  const textColor = isDarkMode.value ? 'rgba(255,255,255,0.87)' : '#303133'
  const option = {
    backgroundColor: 'transparent',
    title: { text: '题库科目分布', left: 'left', textStyle: { fontSize: 16, color: textColor } },
    tooltip: { trigger: 'item' },
    legend: { orient: 'vertical', left: 'right', top: 'center', textStyle: { color: textColor } },
    series: [
      {
        name: '科目',
        type: 'pie',
        radius: ['40%', '65%'],
        center: ['35%', '50%'],
        avoidLabelOverlap: false,
        itemStyle: { borderRadius: 10, borderColor: isDarkMode.value ? '#141414' : '#fff', borderWidth: 2 },
        label: { show: false, position: 'center' },
        emphasis: { label: { show: true, fontSize: 20, fontWeight: 'bold' } },
        labelLine: { show: false },
        data: items
      }
    ]
  }
  pieChart.setOption(option)
}

async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    await loadDashboard()
    
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

onMounted(() => {
    loadAll()
    window.addEventListener('resize', () => {
        trendChart?.resize()
        pieChart?.resize()
    })

    // 监听系统深色模式变化
    const darkModeMediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    darkModeMediaQuery.addEventListener('change', (e) => {
        isDarkMode.value = e.matches
        loadDashboard() // 重新加载图表以应用新主题
    })
})
</script>

<template>
  <div class="page">
    <div class="header">
      <div class="title">基础信息仪表盘</div>
      <el-button :loading="loading" @click="loadAll" :icon="Refresh">刷新</el-button>
    </div>

    <el-alert v-if="error" :title="error" type="error" show-icon />

    <!-- 顶部统计卡片 -->
    <div class="stats-grid">
        <div class="stat-card blue">
            <div class="stat-icon"><el-icon><User /></el-icon></div>
            <div class="stat-content">
                <div class="stat-label">总用户数</div>
                <div class="stat-value">{{ stats.users }}</div>
            </div>
        </div>
        <div class="stat-card green">
            <div class="stat-icon"><el-icon><Document /></el-icon></div>
            <div class="stat-content">
                <div class="stat-label">题库总量</div>
                <div class="stat-value">{{ stats.questions }} <span class="sub-text">({{ stats.pending_questions }} 待审)</span></div>
            </div>
        </div>
        <div class="stat-card orange">
            <div class="stat-icon"><el-icon><Files /></el-icon></div>
            <div class="stat-content">
                <div class="stat-label">试卷总数</div>
                <div class="stat-value">{{ stats.papers }} <span class="sub-text">({{ stats.pending_papers }} 待审)</span></div>
            </div>
        </div>
        <div class="stat-card purple">
            <div class="stat-icon"><el-icon><Reading /></el-icon></div>
            <div class="stat-content">
                <div class="stat-label">教材数量</div>
                <div class="stat-value">{{ stats.textbooks }}</div>
            </div>
        </div>
    </div>

    <!-- 图表区域 -->
    <div class="charts-row">
        <el-card class="chart-card" shadow="never">
            <div ref="trendChartRef" style="width: 100%; height: 350px;"></div>
        </el-card>
        <el-card class="chart-card" shadow="never">
            <div ref="pieChartRef" style="width: 100%; height: 350px;"></div>
        </el-card>
    </div>

    <!-- 基础字典表格 -->
    <el-card class="card" header="科目列表">
      <el-table :data="subjects" :loading="loading" height="260" stripe>
        <el-table-column prop="subject_id" label="ID" width="80" />
        <el-table-column prop="subject_name" label="名称" width="150" />
        <el-table-column prop="subject_code" label="编码" width="100" />
        <el-table-column prop="target_grade" label="年级" width="120" />
        <el-table-column prop="teach_type" label="类型" />
      </el-table>
    </el-card>

    <div class="grid">
      <el-card class="card" header="题型定义">
        <el-table :data="questionTypes" :loading="loading" height="260" stripe>
          <el-table-column prop="type_id" label="ID" width="80" />
          <el-table-column prop="type_name" label="名称" />
          <el-table-column prop="type_code" label="编码" />
        </el-table>
      </el-card>

      <el-card class="card" header="难度分级">
        <el-table :data="difficulties" :loading="loading" height="260" stripe>
          <el-table-column prop="difficulty_id" label="ID" width="80" />
          <el-table-column prop="difficulty_name" label="名称" />
          <el-table-column prop="difficulty_level" label="等级" />
        </el-table>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.title {
  font-size: 20px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

/* Stats Cards */
.stats-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 20px;
}

.stat-card {
    background: var(--el-bg-color);
    border-radius: 8px;
    padding: 20px;
    display: flex;
    align-items: center;
    gap: 15px;
    box-shadow: 0 2px 12px 0 rgba(0,0,0,0.05);
    transition: transform 0.2s;
    border: 1px solid var(--el-border-color-lighter);
}

.stat-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 16px 0 rgba(0,0,0,0.1);
}

.stat-icon {
    width: 48px;
    height: 48px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
    color: #fff;
}

.blue .stat-icon { background: linear-gradient(135deg, #409EFF, #79bbff); }
.green .stat-icon { background: linear-gradient(135deg, #67C23A, #95d475); }
.orange .stat-icon { background: linear-gradient(135deg, #E6A23C, #f3d19e); }
.purple .stat-icon { background: linear-gradient(135deg, #909399, #c8c9cc); } /* Placeholder color for textbooks */

.stat-content {
    flex: 1;
}

.stat-label {
    font-size: 14px;
    color: var(--el-text-color-secondary);
    margin-bottom: 4px;
}

.stat-value {
    font-size: 24px;
    font-weight: bold;
    color: var(--el-text-color-primary);
}

.sub-text {
    font-size: 12px;
    color: var(--el-text-color-secondary);
    font-weight: normal;
}

/* Charts */
.charts-row {
    display: grid;
    grid-template-columns: 2fr 1fr;
    gap: 20px;
}

.chart-card {
    border-radius: 8px;
}

.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.card {
  width: 100%;
}
</style>

