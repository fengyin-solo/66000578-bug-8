<template>
  <div ref="chartEl" class="hist-chart"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([BarChart, GridComponent, TooltipComponent, CanvasRenderer])

const props = defineProps<{
  counts: number[]
  edges: number[]
}>()

const chartEl = ref<HTMLDivElement>()
let chart: echarts.ECharts | null = null

function render() {
  if (!chart || !props.counts.length) return
  const edges = props.edges
  const bins = props.counts.map((c, i) => {
    const lo = edges[i], hi = edges[i + 1]
    return {
      value: c,
      // 单桶（所有体素取值相同）时桶标签只显示一个值
      label: lo === hi ? `${lo}` : `${lo} ~ ${hi}`,
      lo, hi,
    }
  })
  chart.setOption({
    animation: false,
    grid: { left: 28, right: 6, top: 6, bottom: 18 },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any) => {
        const b = bins[params[0].dataIndex]
        return `HU ${b.label}<br/>体素数: <b>${b.value}</b>`
      },
    },
    xAxis: {
      type: 'category',
      data: bins.map(b => b.label),
      axisLabel: {
        color: '#8b949e',
        fontSize: 8,
        interval: bins.length > 5 ? bins.length - 2 : 0,
        formatter: (v: string) => v.split(' ~ ')[0],
      },
      axisLine: { lineStyle: { color: '#30363d' } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: { color: '#8b949e', fontSize: 8 },
      splitLine: { lineStyle: { color: '#21262d' } },
    },
    series: [{
      type: 'bar',
      data: bins.map(b => b.value),
      itemStyle: { color: '#58a6ff', borderRadius: [1, 1, 0, 0] },
      barCategoryGap: '15%',
    }],
  }, true)
}

function onResize() { chart?.resize() }

onMounted(() => {
  chart = echarts.init(chartEl.value!, undefined, { renderer: 'canvas' })
  render()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
  chart = null
})

watch(() => [props.counts, props.edges], render, { deep: true })
</script>

<style scoped>
.hist-chart { width: 100%; height: 84px; margin-top: 4px; background:#0d1117; border-radius:3px }
</style>
