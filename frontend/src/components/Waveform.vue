<template>
  <v-card color="surface-2" rounded="lg" class="pa-3">
    <div class="d-flex align-center justify-space-between mb-2">
      <span class="text-body-2 text-medium-emphasis">Waveform</span>

      <div class="d-flex ga-2 align-center">
        <!-- Interval -->
        <v-select
          v-model="localInterval"
          :items="intervalOptions"
          density="compact"
          hide-details
          style="width:110px"
          @update:model-value="onIntervalChange"
        />

        <!-- Point count -->
        <v-select
          v-model="localPoints"
          :items="pointOptions"
          density="compact"
          hide-details
          style="width:90px"
        />

        <!-- Start / Stop -->
        <v-btn
          v-if="!measStore.streaming"
          color="secondary"
          size="small"
          icon="mdi-play"
          :disabled="!instrStore.connected"
          @click="startStream"
        />
        <v-btn
          v-else
          color="warning"
          size="small"
          icon="mdi-stop"
          @click="measStore.stop()"
        />

        <!-- Clear -->
        <v-btn
          size="small"
          icon="mdi-trash-can-outline"
          @click="measStore.clearBuffer()"
        />

        <!-- CSV download -->
        <v-btn
          size="small"
          icon="mdi-download"
          :disabled="measStore.buffer.length === 0"
          @click="downloadCSV"
        />
      </div>
    </div>

    <!-- Canvas -->
    <div style="position:relative; height:220px">
      <canvas ref="canvasRef" />
    </div>
  </v-card>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, computed } from 'vue'
import {
  Chart, LineController, LineElement, PointElement,
  LinearScale, CategoryScale, TimeScale, Tooltip, Legend, Filler
} from 'chart.js'

import { useInstrumentStore }  from '../stores/instrument'
import { useMeasurementStore } from '../stores/measurement'

Chart.register(
  LineController, LineElement, PointElement,
  LinearScale, CategoryScale, Tooltip, Filler
)

const instrStore = useInstrumentStore()
const measStore  = useMeasurementStore()

const canvasRef     = ref(null)
const localInterval = ref(300)
const localPoints   = ref(200)
let chart = null

const intervalOptions = [
  { title: 'Max',    value: 0    },
  { title: '50 ms',  value: 50   },
  { title: '100 ms', value: 100  },
  { title: '200 ms', value: 200  },
  { title: '300 ms', value: 300  },
  { title: '500 ms', value: 500  },
  { title: '1 s',    value: 1000 },
  { title: '2 s',    value: 2000 },
]
const pointOptions = [
  { title: '100 pts', value: 100 },
  { title: '200 pts', value: 200 },
  { title: '500 pts', value: 500 },
]

// Slice buffer to the desired number of points
const slicedLabels = computed(() =>
  measStore.chartLabels.slice(-localPoints.value)
)
const slicedValues = computed(() =>
  measStore.chartValues.slice(-localPoints.value)
)
const slicedTimestamps = computed(() =>
  measStore.buffer.slice(-localPoints.value).map(d => d.timestamp)
)

// -----------------------------------------------------------------------

function startStream() {
  measStore.start(localInterval.value)
}

function onIntervalChange(ms) {
  if (measStore.streaming) measStore.changeInterval(ms)
}

function downloadCSV() {
  const rows = ['timestamp,value,unit,function,range']
  measStore.buffer.forEach(d => {
    rows.push(`${d.timestamp},${d.value},${d.unit},${d.function},${d.range}`)
  })
  const blob = new Blob([rows.join('\n')], { type: 'text/csv' })
  const a    = document.createElement('a')
  a.href     = URL.createObjectURL(blob)
  a.download = `dmm_${Date.now()}.csv`
  a.click()
}

// -----------------------------------------------------------------------
// Chart.js
// -----------------------------------------------------------------------

function buildChart() {
  if (chart) chart.destroy()
  const ctx = canvasRef.value.getContext('2d')

  chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels:   slicedLabels.value,
      datasets: [{
        label:           measStore.chartUnit || 'Value',
        data:            slicedValues.value,
        borderColor:     '#00ff88',
        backgroundColor: 'rgba(0,255,136,0.08)',
        borderWidth:     1.5,
        pointRadius:     0,
        tension:         0.2,
        fill:            true,
      }],
    },
    options: {
      animation:   false,
      responsive:  true,
      maintainAspectRatio: false,
      interaction: { mode: 'nearest', axis: 'x', intersect: false },
      plugins: {
        legend:  { display: false },
        tooltip: {
          callbacks: {
            title: (items) => {
              const idx = items[0]?.dataIndex ?? 0
              const ts  = slicedTimestamps.value
              if (!ts.length) return ''
              const elapsed = ts[idx] - ts[0]
              return `+${elapsed.toFixed(1)} s`
            },
            label: ctx => `${ctx.parsed.y.toExponential(4)} ${measStore.chartUnit}`
          }
        },
      },
      scales: {
        x: {
          ticks:  { color: '#8b949e', font: { size: 10 }, maxTicksLimit: 8 },
          grid:   { color: 'rgba(255,255,255,0.05)' },
        },
        y: {
          ticks:  { color: '#8b949e', font: { size: 10 } },
          grid:   { color: 'rgba(255,255,255,0.08)' },
        },
      },
    },
  })
}

function updateChart() {
  if (!chart) return
  chart.data.labels            = slicedLabels.value
  chart.data.datasets[0].data  = slicedValues.value
  chart.data.datasets[0].label = measStore.chartUnit || 'Value'
  chart.update('none')
}

// Re-draw whenever a new measurement arrives
watch(() => measStore.latest, updateChart)
// Rebuild chart when unit changes (Y-axis label)
watch(() => measStore.chartUnit, buildChart)

onMounted(buildChart)
onUnmounted(() => { if (chart) chart.destroy() })
</script>
