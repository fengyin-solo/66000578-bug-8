<template>
  <div ref="el" class="hist-chart"></div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps<{
  counts: number[]
  edges?: number[]
}>()

const el = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null

function render() {
  if (!chart) return
  const counts = props.counts ?? []
  const edges = props.edges ?? []
  const labels = edges.length === counts.length + 1
    ? edges.slice(0, -1).map((e, i) => `${e}~${edges[i + 1]}`)
    : counts.map((_, i) => `bin${i + 1}`)

  chart.setOption({
    grid: { left: 28, right: 6, top: 6, bottom: 18 },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (items: any) => {
        const it = items[0]
        return `范围: ${labels[it.dataIndex]}<br/>体素数: <b>${it.value}</b>`
      }
    },
    xAxis: {
      type: 'category',
      data: labels,
      axisLabel: { color: '#8b949e', fontSize: 8, interval: 1, rotate: 25 },
      axisLine: { lineStyle: { color: '#30363d' } }
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: { color: '#8b949e', fontSize: 8 },
      splitLine: { lineStyle: { color: '#21262d' } }
    },
    series: [{
      type: 'bar',
      data: counts,
      barCategoryGap: '15%',
      itemStyle: { color: '#58a6ff', borderRadius: [1, 1, 0, 0] }
    }]
  }, true)
}

onMounted(() => {
  if (el.value) {
    chart = echarts.init(el.value)
    render()
    window.addEventListener('resize', resize)
  }
})

function resize() { chart?.resize() }

watch(() => [props.counts, props.edges], render, { deep: true })

onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.hist-chart { width: 100%; height: 90px; margin-top: 4px; background: #0d1117; border-radius: 3px; }
</style>
