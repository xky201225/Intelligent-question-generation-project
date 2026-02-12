<script setup>
import { computed } from 'vue'

const props = defineProps({
  config: {
    type: Object,
    default: () => ({})
  }
})

const widgetType = computed(() => props.config.widget)

// 样式计算
const containerStyle = computed(() => {
  return {
    padding: '10px',
    border: '1px solid #ddd',
    borderRadius: '4px',
    background: '#fff',
    minHeight: '60px'
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
    border: isBracket ? 'none' : '1px solid #333',
    borderRadius: props.config.bubble_shape === 'circle' ? '50%' : (isBracket ? '0' : '2px'),
    fontSize: '14px',
    fontWeight: 'bold',
    cursor: 'pointer',
    padding: isBracket ? '0 4px' : '0'
  }
})

const inputLineStyle = computed(() => {
  return {
    borderBottom: props.config.line_style === 'underline' ? '1px solid #333' : 'none',
    border: props.config.line_style === 'box' ? '1px solid #333' : undefined,
    height: (props.config.line_height || 30) + 'px',
    width: '100%',
    marginBottom: '8px'
  }
})

const textAreaStyle = computed(() => {
  return {
    width: '100%',
    minHeight: (props.config.rows || 3) * 24 + 'px',
    border: props.config.border ? '1px solid #333' : '1px dashed #999',
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
    <div v-if="widgetType === 'bubble_group'" :style="bubbleGroupStyle">
      <div v-for="opt in (props.config.options || ['A','B','C','D'])" :key="opt" :style="bubbleStyle">
        <span v-if="props.config.bubble_shape === 'bracket'">[ {{ opt }} ]</span>
        <span v-else>{{ opt }}</span>
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
