<script setup>
import { computed, ref, onMounted, onUnmounted, nextTick, watch } from 'vue'

const props = defineProps({
  config: {
    type: Object,
    default: () => ({})
  }
})

const widgetType = computed(() => props.config.widget)

// 复选框折叠展开逻辑
const bubbleContainerRef = ref(null)
const bubbleWrapperRef = ref(null)
const isExpanded = ref(false)
const needsExpand = ref(false)
const visibleCount = ref(0)

const allOptions = computed(() => props.config.options || ['A', 'B', 'C', 'D'])

function calculateVisibleOptions() {
  if (!bubbleContainerRef.value) return

  const container = bubbleContainerRef.value
  const wrapperHeight = bubbleWrapperRef.value?.clientHeight
  const containerWidth = container.offsetWidth - 64 // 预留展开按钮的宽度
  const containerHeight = wrapperHeight || container.offsetHeight || 60

  // 估算每个选项的宽度（根据形状和内容）
  const isBracket = props.config.bubble_shape === 'bracket'
  const spacing = props.config.spacing || 10
  const optionWidth = (isBracket ? 50 : 30) + spacing // 选项宽度 + 间距
  const optionHeight = 24 + spacing // 选项高度 + 间距

  const isVertical = props.config.layout === 'vertical'

  if (isVertical) {
    // 垂直布局：计算能显示多少行
    const maxRows = Math.floor(containerHeight / optionHeight)
    visibleCount.value = Math.max(1, maxRows)
  } else {
    // 水平布局：按可用高度允许多行展示
    const maxPerRow = Math.floor(containerWidth / optionWidth)
    const maxRows = Math.floor(containerHeight / optionHeight)
    visibleCount.value = Math.max(1, maxPerRow) * Math.max(1, maxRows)
  }

  needsExpand.value = allOptions.value.length > visibleCount.value
}

function toggleExpand() {
  isExpanded.value = !isExpanded.value
}

// 监听 config 变化重新计算
watch(() => props.config, () => {
  nextTick(() => {
    calculateVisibleOptions()
  })
}, { deep: true })

onMounted(() => {
  nextTick(() => {
    calculateVisibleOptions()
  })
  window.addEventListener('resize', calculateVisibleOptions)
})

onUnmounted(() => {
  window.removeEventListener('resize', calculateVisibleOptions)
})

// 样式计算
const containerStyle = computed(() => {
  return {
    padding: '10px',
    border: '1px solid var(--sp-border)',
    borderRadius: '4px',
    background: 'var(--sp-bg)',
    minHeight: '60px',
    color: 'var(--sp-text)'
  }
})

const bubbleGroupStyle = computed(() => {
  return {
    display: 'flex',
    flexDirection: props.config.layout === 'vertical' ? 'column' : 'row',
    gap: (props.config.spacing || 10) + 'px',
    flexWrap: 'wrap'
  }
})

const bubbleStyle = computed(() => {
  const isBracket = props.config.bubble_shape === 'bracket'
  return {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: isBracket ? 'auto' : '30px',
    height: '24px',
    border: isBracket ? 'none' : '1px solid var(--sp-text)',
    borderRadius: props.config.bubble_shape === 'circle' ? '50%' : (isBracket ? '0' : '2px'),
    fontSize: '14px',
    fontWeight: 'bold',
    cursor: 'pointer',
    padding: isBracket ? '0 4px' : '0',
    color: 'var(--sp-text)',
    background: 'var(--sp-card-bg)'
  }
})

const inputLineStyle = computed(() => {
  return {
    borderBottom: props.config.line_style === 'underline' ? '1px solid var(--sp-text)' : 'none',
    border: props.config.line_style === 'box' ? '1px solid var(--sp-text)' : undefined,
    height: (props.config.line_height || 30) + 'px',
    width: '100%',
    marginBottom: '8px'
  }
})

const textAreaStyle = computed(() => {
  return {
    width: '100%',
    minHeight: (props.config.rows || 3) * 24 + 'px',
    border: props.config.border ? '1px solid var(--sp-text)' : '1px dashed var(--sp-border)',
    padding: '8px',
    position: 'relative'
  }
})

const gridAreaStyle = computed(() => {
  const isLine = props.config.style === 'line' // 新增样式判断
  const cols = props.config.cols || 20
  const color = props.config.grid_color || '#cc0000'
  
  if (isLine) {
    return {
      width: '100%',
      border: `1px solid ${color}`,
      padding: '0'
    }
  }

  return {
    display: 'grid',
    gridTemplateColumns: `repeat(${cols}, 1fr)`,
    gap: '1px',
    border: `1px solid ${color}`,
    background: color,
    width: '100%'
  }
})

const lineRowStyle = computed(() => {
  const color = props.config.grid_color || '#cc0000'
  const height = props.config.line_height || 30
  return {
    borderBottom: `1px solid ${color}`,
    height: `${height}px`,
    width: '100%'
  }
})

const gridCellStyle = computed(() => {
  return {
    aspectRatio: '1',
    background: '#fff',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center'
  }
})
</script>

<template>
  <div class="style-preview" :style="containerStyle">
    <!-- 1. 填涂卡 (bubble_group) -->
    <div v-if="widgetType === 'bubble_group'" class="bubble-wrapper" ref="bubbleWrapperRef">
      <div ref="bubbleContainerRef" :style="bubbleGroupStyle" class="bubble-container">
        <div v-for="opt in allOptions.slice(0, needsExpand ? visibleCount : allOptions.length)" :key="opt" :style="bubbleStyle">
          <span v-if="props.config.bubble_shape === 'bracket'">[ {{ opt }} ]</span>
          <span v-else>{{ opt }}</span>
        </div>
        <div v-if="needsExpand" class="expand-btn" @click.stop="toggleExpand">
          <span class="expand-icon">{{ isExpanded ? '▲' : '▼' }}</span>
          <span class="expand-text">+{{ allOptions.length - visibleCount }}</span>
        </div>
      </div>

      <!-- 展开后的列表弹出层 -->
      <div v-if="isExpanded && needsExpand" class="expanded-list-overlay" @click.stop>
        <div class="expanded-list-header">
          <span>全部选项 ({{ allOptions.length }})</span>
          <span class="collapse-btn" @click="toggleExpand">收起 ▲</span>
        </div>
        <div class="expanded-list-content">
          <div v-for="opt in allOptions" :key="opt" :style="bubbleStyle" class="expanded-option">
            <span v-if="props.config.bubble_shape === 'bracket'">[ {{ opt }} ]</span>
            <span v-else>{{ opt }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 2. 填空线 (input_line) -->
    <div v-else-if="widgetType === 'input_line'">
      <div v-for="i in (props.config.lines || 1)" :key="i" :style="inputLineStyle"></div>
    </div>

    <!-- 3. 文本区域 (text_area) -->
    <div v-else-if="widgetType === 'text_area'" :style="textAreaStyle">
      <span v-if="props.config.label" style="position: absolute; top: 5px; left: 5px; font-weight: bold;">
        {{ props.config.label }}
      </span>
      <div v-if="props.config.show_grid" style="width: 100%; height: 100%; background-image: linear-gradient(#eee 1px, transparent 0); background-size: 100% 24px;"></div>
    </div>

    <!-- 4. 作文格纸 (grid_area) -->
    <div v-else-if="widgetType === 'grid_area'">
      <div v-if="props.config.style === 'line'" :style="gridAreaStyle">
         <div v-for="i in (props.config.rows || 15)" :key="i" :style="lineRowStyle"></div>
      </div>
      <div v-else :style="gridAreaStyle">
        <div v-for="i in Math.min(100, props.config.total_count || 100)" :key="i" :style="gridCellStyle"></div>
      </div>
      <div v-if="props.config.show_word_count" style="text-align: right; font-size: 12px; color: #666; margin-top: 4px;">
        {{ props.config.total_count }}字
      </div>
    </div>

    <!-- 默认提示 -->
    <div v-else style="color: #999; text-align: center; line-height: 60px;">
      暂不支持预览或配置无效
    </div>
  </div>
</template>

<style scoped>
.style-preview {
  --sp-bg: var(--el-bg-color, #fff);
  --sp-bg-soft: var(--el-fill-color-lighter, #f7f7f7);
  --sp-border: var(--el-border-color, #ddd);
  --sp-border-light: var(--el-border-color-lighter, #eee);
  --sp-text: var(--el-text-color-primary, #333);
  --sp-text-secondary: var(--el-text-color-secondary, #666);
  --sp-accent: var(--el-color-primary, #409eff);
  --sp-card-bg: var(--el-fill-color-blank, #fff);
  --sp-card-bg-hover: var(--el-fill-color-light, #e0e0e0);
}

.bubble-wrapper {
  position: relative;
  width: 100%;
}

.bubble-container {
  width: 100%;
}

.expand-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 4px 10px;
  background: var(--sp-bg-soft);
  border: 1px solid var(--sp-border);
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  color: var(--sp-text-secondary);
  transition: all 0.2s ease;
  user-select: none;
  height: 28px;
  min-width: 64px;
  line-height: 1;
}

.expand-btn:hover {
  background: var(--sp-card-bg-hover);
  border-color: var(--sp-text-secondary);
}

.expand-icon {
  font-size: 12px;
}

.expand-text {
  font-weight: 600;
}

.expanded-list-overlay {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  margin-top: 8px;
  background: var(--sp-bg);
  border: 1px solid var(--sp-border);
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 100;
  max-height: min(240px, 50vh);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  color: var(--sp-text);
}

.expanded-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: var(--sp-bg-soft);
  border-bottom: 1px solid var(--sp-border-light);
  font-size: 12px;
  color: var(--sp-text-secondary);
}

.collapse-btn {
  cursor: pointer;
  color: var(--sp-accent);
  font-size: 12px;
  user-select: none;
  padding: 2px 6px;
  border-radius: 4px;
}

.collapse-btn:hover {
  text-decoration: underline;
}

.expanded-list-content {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px;
  overflow-y: auto;
  max-height: 190px;
}

.expanded-option {
  flex-shrink: 0;
}
</style>
