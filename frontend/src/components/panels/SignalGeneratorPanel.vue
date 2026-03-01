<!--
  SignalGeneratorPanel – dedicated panel for FY6800 signal generator.

  Layout:
    Top: Channel tabs (CH1 / CH2 / Counter)
    Body: Channel-specific controls
      CH1/CH2: Waveform selector, Frequency/Amplitude/Offset/Duty/Phase inputs, Output toggle
      Counter: Gate Time selector + measurement display
-->
<template>
  <v-card color="surface" rounded="lg" class="pa-3">

    <!-- Channel tabs -->
    <v-tabs v-model="activeTab" density="compact" color="primary" class="mb-3">
      <v-tab value="CH1">
        <v-icon start>mdi-numeric-1-circle</v-icon>CH1
      </v-tab>
      <v-tab value="CH2">
        <v-icon start>mdi-numeric-2-circle</v-icon>CH2
      </v-tab>
      <v-tab value="COUNTER">
        <v-icon start>mdi-counter</v-icon>Counter
      </v-tab>
      <v-tab value="ARB">
        <v-icon start>mdi-function-variant</v-icon>ARB
      </v-tab>
    </v-tabs>

    <!-- CH1 / CH2 controls -->
    <div v-if="activeTab === 'CH1' || activeTab === 'CH2'">
      <v-row no-gutters class="ga-3">

        <!-- Waveform selector -->
        <v-col cols="12" sm="6" md="4">
          <div class="text-caption text-medium-emphasis mb-1">Waveform</div>
          <v-select
            v-model="chForm.waveform"
            :items="waveformOptions"
            density="compact"
            hide-details
            :disabled="!instrStore.connected"
            @update:model-value="applyWaveform"
          />
        </v-col>

        <!-- Output toggle -->
        <v-col cols="12" sm="6" md="2" class="d-flex align-center">
          <v-btn
            :color="chForm.output ? 'success' : 'error'"
            :variant="chForm.output ? 'flat' : 'tonal'"
            :prepend-icon="chForm.output ? 'mdi-power' : 'mdi-power-off'"
            :disabled="!instrStore.connected"
            size="large"
            block
            @click="toggleOutput"
          >{{ chForm.output ? 'ON' : 'OFF' }}</v-btn>
        </v-col>
      </v-row>

      <!-- Numeric parameters -->
      <v-row no-gutters class="ga-3 mt-2">
        <v-col cols="12" sm="6" md="4">
          <div class="d-flex ga-1 align-center">
            <v-text-field
              v-model="freqDisplay"
              label="Frequency"
              type="number"
              step="any"
              density="compact"
              hide-details
              :disabled="!instrStore.connected"
              style="flex:1"
              @keydown.enter="applyFrequency"
              @blur="applyFrequency"
            >
              <template #append-inner>
                <v-btn
                  icon="mdi-check"
                  size="x-small"
                  variant="text"
                  :disabled="!instrStore.connected"
                  @click="applyFrequency"
                />
              </template>
            </v-text-field>
            <v-select
              v-model="freqUnit"
              :items="freqUnitOptions"
              density="compact"
              hide-details
              style="width:100px; flex:none"
              @update:model-value="onFreqUnitChange"
            />
          </div>
        </v-col>

        <v-col cols="12" sm="6" md="4">
          <v-text-field
            v-model.number="chForm.amplitude"
            label="Amplitude (Vpp)"
            type="number"
            step="0.1"
            density="compact"
            hide-details
            :disabled="!instrStore.connected"
            @keydown.enter="applyAmplitude"
            @blur="applyAmplitude"
          >
            <template #append-inner>
              <v-btn
                icon="mdi-check"
                size="x-small"
                variant="text"
                :disabled="!instrStore.connected"
                @click="applyAmplitude"
              />
            </template>
          </v-text-field>
        </v-col>

        <v-col cols="12" sm="6" md="4">
          <v-text-field
            v-model.number="chForm.duty"
            label="Duty (%)"
            type="number"
            step="0.1"
            density="compact"
            hide-details
            :disabled="!instrStore.connected"
            @keydown.enter="applyDuty"
            @blur="applyDuty"
          >
            <template #append-inner>
              <v-btn
                icon="mdi-check"
                size="x-small"
                variant="text"
                :disabled="!instrStore.connected"
                @click="applyDuty"
              />
            </template>
          </v-text-field>
        </v-col>

        <v-col cols="12" sm="6" md="4">
          <v-text-field
            v-model.number="chForm.phase"
            label="Phase (deg)"
            type="number"
            step="1"
            density="compact"
            hide-details
            :disabled="!instrStore.connected"
            @keydown.enter="applyPhase"
            @blur="applyPhase"
          >
            <template #append-inner>
              <v-btn
                icon="mdi-check"
                size="x-small"
                variant="text"
                :disabled="!instrStore.connected"
                @click="applyPhase"
              />
            </template>
          </v-text-field>
        </v-col>

        <v-col cols="12" sm="6" md="4">
          <v-text-field
            v-model.number="chForm.offset"
            label="Offset (V)"
            type="number"
            step="0.1"
            density="compact"
            hide-details
            :disabled="!instrStore.connected"
            @keydown.enter="applyOffset"
            @blur="applyOffset"
          >
            <template #append-inner>
              <v-btn
                icon="mdi-check"
                size="x-small"
                variant="text"
                :disabled="!instrStore.connected"
                @click="applyOffset"
              />
            </template>
          </v-text-field>
        </v-col>
      </v-row>
    </div>

    <!-- Counter controls -->
    <div v-else-if="activeTab === 'COUNTER'">
      <v-row no-gutters class="ga-3 align-center">
        <v-col cols="auto">
          <div class="text-caption text-medium-emphasis mb-1">Gate Time</div>
          <v-btn-toggle
            v-model="gateTime"
            density="compact"
            divided
            mandatory
            color="primary"
            @update:model-value="applyGateTime"
          >
            <v-btn value="1s" size="small" :disabled="!instrStore.connected">1s</v-btn>
            <v-btn value="10s" size="small" :disabled="!instrStore.connected">10s</v-btn>
            <v-btn value="100s" size="small" :disabled="!instrStore.connected">100s</v-btn>
          </v-btn-toggle>
        </v-col>

        <v-col cols="auto">
          <div class="text-caption text-medium-emphasis mb-1">Coupling</div>
          <v-btn-toggle
            v-model="coupling"
            density="compact"
            divided
            mandatory
            color="primary"
            @update:model-value="applyCoupling"
          >
            <v-btn value="AC" size="small" :disabled="!instrStore.connected">AC (Front)</v-btn>
            <v-btn value="DC" size="small" :disabled="!instrStore.connected">DC (Rear)</v-btn>
          </v-btn-toggle>
        </v-col>

        <v-col cols="auto" class="d-flex align-end">
          <v-btn
            variant="tonal"
            color="warning"
            size="small"
            prepend-icon="mdi-refresh"
            :disabled="!instrStore.connected"
            @click="counterReset"
          >RESET</v-btn>
        </v-col>
      </v-row>

      <!-- Counter readings from extra data -->
      <v-row v-if="counterExtra" no-gutters class="mt-3">
        <v-col cols="12">
          <v-table density="compact" class="counter-readings">
            <tbody>
              <tr>
                <td class="text-medium-emphasis" style="width:120px">Period</td>
                <td class="text-body-1 font-weight-medium">{{ formatTime(counterExtra.period_ns) }}</td>
              </tr>
              <tr>
                <td class="text-medium-emphasis">+Width</td>
                <td class="text-body-1 font-weight-medium">{{ formatTime(counterExtra.pos_width_ns) }}</td>
              </tr>
              <tr>
                <td class="text-medium-emphasis">-Width</td>
                <td class="text-body-1 font-weight-medium">{{ formatTime(counterExtra.neg_width_ns) }}</td>
              </tr>
              <tr>
                <td class="text-medium-emphasis">Duty</td>
                <td class="text-body-1 font-weight-medium">{{ counterExtra.duty_pct != null ? counterExtra.duty_pct.toFixed(1) + ' %' : '---' }}</td>
              </tr>
            </tbody>
          </v-table>
        </v-col>
      </v-row>
    </div>

    <!-- ARB (Arbitrary Waveform) controls -->
    <div v-else-if="activeTab === 'ARB'">

      <!-- Formula input -->
      <v-text-field
        v-model="arbFormula"
        label="Formula  f(x),  x = 0..1"
        placeholder="sin(2 * pi * x)"
        density="compact"
        hide-details
        class="mb-2"
        @update:model-value="evalFormula"
      />

      <!-- Help + Preset chips -->
      <div class="d-flex flex-wrap ga-1 mb-3 align-center">
        <v-btn
          icon="mdi-help-circle-outline"
          size="x-small"
          variant="text"
          @click="arbHelpOpen = true"
        />
        <v-chip
          v-for="p in arbPresets"
          :key="p.label"
          size="small"
          variant="tonal"
          @click="arbFormula = p.formula; evalFormula()"
        >{{ p.label }}</v-chip>
      </div>

      <!-- Help dialog -->
      <v-dialog v-model="arbHelpOpen" max-width="520">
        <v-card>
          <v-card-title>ARB — Arbitrary Waveform</v-card-title>
          <v-card-text class="text-body-2">
            <p class="mb-2">
              数式から任意波形を生成し、FY6800 の DDS メモリ (Arb 1-64) にアップロードします。
            </p>
            <p class="mb-2">
              <strong>数式:</strong> 変数 <code>x</code> は 0 から 1（1周期）を 8192 等分した値です。
              評価結果は自動的に 14-bit (0-16383) に正規化されます。
              使用可能な関数: sin, cos, tan, abs, sqrt, pow, exp, log, floor, ceil, min, max。
              定数: pi, e。
            </p>
            <p class="mb-2">
              <strong>ループ境界:</strong> DDS は 8192 ポイントを1周期として繰り返し出力します。
              <code>sin(2*pi*x)</code> のように x=0 と x=1 が同じ値になる数式なら、
              ループ境界で波形が滑らかに繋がります。
            </p>
            <p class="mb-2">
              <strong>Arb スロット:</strong> CH1/CH2 共通のメモリです。スロット N にアップロードした波形は
              どちらのチャンネルからも「Arb N」として選択できます。
              現在そのスロットを使用中のチャンネルがある場合、アップロードはブロックされます。
            </p>
            <p>
              <strong>出力:</strong> アップロード後、CH1/CH2 タブで波形を「Arb N」に設定し、
              周波数・振幅等を指定して出力します。「Apply to」でチャンネルを選んでおくと、
              アップロード成功後に自動で波形が切り替わります。
            </p>
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn variant="text" @click="arbHelpOpen = false">Close</v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>

      <!-- Formula error -->
      <v-alert
        v-if="arbError"
        type="warning"
        density="compact"
        class="mb-2"
      >{{ arbError }}</v-alert>

      <!-- Preview chart -->
      <div style="position:relative; height:200px" class="mb-3">
        <canvas ref="arbCanvasRef" />
      </div>

      <!-- Upload controls -->
      <v-row no-gutters class="ga-3 align-center">
        <v-col cols="auto">
          <v-select
            v-model.number="arbSlot"
            :items="arbSlotOptions"
            label="Arb Slot"
            density="compact"
            hide-details
            style="width:120px"
          />
        </v-col>
        <v-col cols="auto">
          <v-select
            v-model="arbChannel"
            :items="['---', 'CH1', 'CH2']"
            label="Apply to"
            density="compact"
            hide-details
            style="width:120px"
          />
        </v-col>
        <v-col cols="auto">
          <v-btn
            color="primary"
            variant="flat"
            prepend-icon="mdi-upload"
            :disabled="!instrStore.connected || arbSamples.length !== 8192 || arbUploading"
            :loading="arbUploading"
            @click="uploadArb"
          >Upload</v-btn>
        </v-col>
        <v-col cols="auto">
          <v-chip
            v-if="arbResult"
            :color="arbResult.ok ? 'success' : 'error'"
            size="small"
            closable
            @click:close="arbResult = null"
          >{{ arbResult.ok ? 'OK' : arbResult.error }}</v-chip>
        </v-col>
      </v-row>
    </div>

    <!-- Error display -->
    <v-alert
      v-if="cmdError"
      type="error"
      density="compact"
      closable
      class="mt-3"
      @click:close="cmdError = ''"
    >{{ cmdError }}</v-alert>

  </v-card>
</template>

<script setup>
import { ref, reactive, computed, watch, nextTick, onUnmounted } from 'vue'
import {
  Chart, LineController, LineElement, PointElement,
  LinearScale, CategoryScale, Tooltip, Filler
} from 'chart.js'
import { useInstrumentStore }  from '../../stores/instrument'
import { useMeasurementStore } from '../../stores/measurement'

Chart.register(
  LineController, LineElement, PointElement,
  LinearScale, CategoryScale, Tooltip, Filler
)

const instrStore = useInstrumentStore()
const measStore  = useMeasurementStore()

const activeTab = ref('CH1')
const cmdError  = ref('')

// Waveform options: dynamically updated from backend per channel
// (Adjustable Pulse is CH1-only; backend provides the correct list)
const defaultWaveforms = [
  'Sin', 'Square', 'CMOS', 'Adjustable Pulse', 'DC',
  'Triangle', 'Ramp', 'Negative Ramp',
  'Stairstep Triangle', 'Stairstep', 'Negative Stairstep',
  'Exponential', 'Negative Exponential', 'Falling Exponential', 'Neg Falling Exponential',
  'Logarithm', 'Negative Logarithm', 'Falling Logarithm', 'Neg Falling Logarithm',
  'Full Wave', 'Negative Full Wave', 'Half Wave', 'Negative Half Wave',
  'Lorentz Pulse', 'Multitone', 'Random', 'ECG', 'Trapezoidal Pulse',
  'Sinc Pulse', 'Impulse', 'Gauss White Noise',
  'AM', 'FM', 'Chirp',
  ...Array.from({length: 64}, (_, i) => `Arb ${i + 1}`),
]
const waveformOptions = ref(defaultWaveforms)

// Per-channel form state
const chForm = reactive({
  waveform:  'Sin',
  frequency: 1000.0,
  amplitude: 1.0,
  offset:    0.0,
  duty:      50.0,
  phase:     0.0,
  output:    false,
})

const gateTime = ref('1s')
const coupling = ref('AC')

// Frequency with unit (CH1/CH2)
const freqUnit    = ref('Hz')
const freqDisplay = ref('1000')
const freqUnitOptions = [
  { title: 'uHz',  value: 'uHz'  },
  { title: 'mHz',  value: 'mHz'  },
  { title: 'Hz',   value: 'Hz'   },
  { title: 'kHz',  value: 'kHz'  },
  { title: 'MHz',  value: 'MHz'  },
]
const freqUnitMul = { uHz: 1e-6, mHz: 1e-3, Hz: 1, kHz: 1e3, MHz: 1e6 }

function hzToDisplay(hz) {
  // Convert Hz to current display unit
  return hz / freqUnitMul[freqUnit.value]
}
function displayToHz() {
  return parseFloat(freqDisplay.value) * freqUnitMul[freqUnit.value]
}
function syncFreqDisplay() {
  freqDisplay.value = String(hzToDisplay(chForm.frequency))
}
function onFreqUnitChange() {
  // Re-display current Hz value in the new unit
  syncFreqDisplay()
}

// Counter extra readings from streaming measurement
const counterExtra = computed(() => {
  const latest = measStore.latest
  if (!latest || latest.function !== 'COUNTER' || !latest.extra) return null
  return latest.extra
})

// Format nanoseconds to human-readable time with auto-scaling
function formatTime(ns) {
  if (ns == null || ns === 0) return '---'
  if (ns < 1000) return ns.toFixed(1) + ' ns'
  if (ns < 1_000_000) return (ns / 1000).toFixed(3) + ' \u00B5s'
  if (ns < 1_000_000_000) return (ns / 1_000_000).toFixed(3) + ' ms'
  return (ns / 1_000_000_000).toFixed(6) + ' s'
}

// Track last-applied values to avoid redundant sends
const lastApplied = reactive({
  frequency: null,
  amplitude: null,
  offset: null,
  duty: null,
  phase: null,
})

// When switching tabs, switch function and sync form from device
watch(activeTab, async (tab) => {
  if (tab === 'ARB') {
    // ARB is not a device function; just build the preview chart
    await nextTick()
    evalFormula()
    return
  }
  try {
    await sendCmd({ function: tab })
    // Fetch channel state from backend
    const res = await fetch(`/api/channel_state/${tab}`)
    if (res.ok) {
      const state = await res.json()
      if (tab === 'COUNTER') {
        gateTime.value = state.gate_time ?? '1s'
        coupling.value = state.coupling ?? 'AC'
      } else {
        chForm.waveform  = state.waveform  ?? 'Sin'
        chForm.frequency = state.frequency ?? 1000.0
        chForm.amplitude = state.amplitude ?? 1.0
        chForm.offset    = state.offset    ?? 0.0
        chForm.duty      = state.duty      ?? 50.0
        chForm.phase     = state.phase     ?? 0.0
        chForm.output    = state.output    ?? false
        // Update per-channel waveform options (e.g. CH2 lacks Adjustable Pulse)
        if (state.waveform_options) {
          waveformOptions.value = state.waveform_options
        }
        // Reset last-applied tracking
        lastApplied.frequency = chForm.frequency
        lastApplied.amplitude = chForm.amplitude
        lastApplied.offset    = chForm.offset
        lastApplied.duty      = chForm.duty
        lastApplied.phase     = chForm.phase
        syncFreqDisplay()
      }
    }
  } catch (e) {
    cmdError.value = e.message
  }
})

// On initial connect, sync form
watch(() => instrStore.connected, async (connected) => {
  if (connected && instrStore.capability?.instrument_type === 'siggen') {
    try {
      const res = await fetch(`/api/channel_state/${activeTab.value}`)
      if (res.ok) {
        const state = await res.json()
        if (activeTab.value !== 'COUNTER') {
          chForm.waveform  = state.waveform  ?? 'Sin'
          chForm.frequency = state.frequency ?? 1000.0
          chForm.amplitude = state.amplitude ?? 1.0
          chForm.offset    = state.offset    ?? 0.0
          chForm.duty      = state.duty      ?? 50.0
          chForm.phase     = state.phase     ?? 0.0
          chForm.output    = state.output    ?? false
          if (state.waveform_options) {
            waveformOptions.value = state.waveform_options
          }
          lastApplied.frequency = chForm.frequency
          lastApplied.amplitude = chForm.amplitude
          lastApplied.offset    = chForm.offset
          lastApplied.duty      = chForm.duty
          lastApplied.phase     = chForm.phase
          syncFreqDisplay()
        }
      }
    } catch { /* ignore */ }
  }
})

async function sendCmd(settings) {
  cmdError.value = ''
  try {
    await instrStore.sendCommand(settings)
  } catch (e) {
    cmdError.value = e.message
    throw e
  }
}

async function applyWaveform()  { await sendCmd({ waveform: chForm.waveform }) }
async function applyFrequency() {
  const hz = displayToHz()
  if (hz === lastApplied.frequency) return
  chForm.frequency = hz
  lastApplied.frequency = hz
  await sendCmd({ frequency: hz })
}
async function applyAmplitude() {
  if (chForm.amplitude === lastApplied.amplitude) return
  lastApplied.amplitude = chForm.amplitude
  await sendCmd({ amplitude: chForm.amplitude })
}
async function applyOffset() {
  if (chForm.offset === lastApplied.offset) return
  lastApplied.offset = chForm.offset
  await sendCmd({ offset: chForm.offset })
}
async function applyDuty() {
  if (chForm.duty === lastApplied.duty) return
  lastApplied.duty = chForm.duty
  await sendCmd({ duty: chForm.duty })
}
async function applyPhase() {
  if (chForm.phase === lastApplied.phase) return
  lastApplied.phase = chForm.phase
  await sendCmd({ phase: chForm.phase })
}
async function applyGateTime() { await sendCmd({ gate_time: gateTime.value }) }
async function applyCoupling() { await sendCmd({ coupling: coupling.value }) }
async function counterReset() { await sendCmd({ counter_reset: true }) }

async function toggleOutput() {
  chForm.output = !chForm.output
  await sendCmd({ output: chForm.output })
}

// ---------------------------------------------------------------------------
// ARB tab
// ---------------------------------------------------------------------------

const arbCanvasRef = ref(null)
const arbFormula   = ref('sin(2 * pi * x)')
const arbError     = ref('')
const arbSamples   = ref([])   // 8192 int values 0..16383
const arbSlot      = ref(1)
const arbChannel   = ref('---')
const arbUploading = ref(false)
const arbResult    = ref(null)
const arbHelpOpen  = ref(false)
let arbChart       = null

const arbSlotOptions = Array.from({length: 64}, (_, i) => ({
  title: `Arb ${i + 1}`, value: i + 1
}))

const arbPresets = [
  { label: 'Sine',           formula: 'sin(2 * pi * x)' },
  { label: 'Sawtooth',       formula: 'x' },
  { label: 'Triangle',       formula: '1 - abs(2 * x - 1)' },
  { label: 'Gaussian',       formula: 'exp(-pow((x - 0.5) * 6, 2))' },
  { label: 'Sinc',           formula: 'x === 0.5 ? 1 : sin(pi * (x - 0.5) * 10) / (pi * (x - 0.5) * 10)' },
  { label: 'Staircase',      formula: 'floor(x * 8) / 7' },
  { label: 'Rectified',      formula: 'abs(sin(2 * pi * x))' },
  { label: 'Clipped Sin',    formula: 'min(max(sin(2 * pi * x), -0.5), 0.5)' },
]

function evalFormula() {
  arbError.value = ''
  arbResult.value = null
  const N = 8192
  try {
    const { sin, cos, tan, abs, sqrt, pow, exp, log, floor, ceil, min, max, PI, E } = Math
    const pi = PI, e = E
    // Build evaluator function
    const fn = new Function(
      'x', 'sin', 'cos', 'tan', 'abs', 'sqrt', 'pow', 'exp', 'log',
      'floor', 'ceil', 'min', 'max', 'pi', 'e',
      `return (${arbFormula.value})`
    )

    const raw = []
    for (let i = 0; i < N; i++) {
      const x = i / N
      const v = fn(x, sin, cos, tan, abs, sqrt, pow, exp, log, floor, ceil, min, max, pi, e)
      if (typeof v !== 'number' || !isFinite(v)) {
        throw new Error(`Non-finite value at x=${x.toFixed(4)}: ${v}`)
      }
      raw.push(v)
    }

    // Normalize to 0..16383
    let vmin = raw[0], vmax = raw[0]
    for (const v of raw) {
      if (v < vmin) vmin = v
      if (v > vmax) vmax = v
    }
    const range = vmax - vmin
    if (range === 0) {
      // Constant value → midpoint
      arbSamples.value = Array(N).fill(8192)
    } else {
      arbSamples.value = raw.map(v => Math.round(((v - vmin) / range) * 16383))
    }
    updateArbChart()
  } catch (e) {
    arbError.value = e.message
    arbSamples.value = []
  }
}

function buildArbChart() {
  if (arbChart) arbChart.destroy()
  const canvas = arbCanvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')

  // Downsample for display: every 8th point → 1024 points
  const display = []
  const labels  = []
  const samples = arbSamples.value
  for (let i = 0; i < samples.length; i += 8) {
    display.push(samples[i])
    labels.push('')
  }

  arbChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        data:            display,
        borderColor:     '#00ff88',
        backgroundColor: 'rgba(0,255,136,0.08)',
        borderWidth:     1.5,
        pointRadius:     0,
        tension:         0,
        fill:            true,
      }],
    },
    options: {
      animation:   false,
      responsive:  true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      scales: {
        x: {
          display: false,
        },
        y: {
          min: 0, max: 16383,
          ticks: { color: '#8b949e', font: { size: 10 } },
          grid:  { color: 'rgba(255,255,255,0.08)' },
        },
      },
    },
  })
}

function updateArbChart() {
  if (!arbChart) {
    buildArbChart()
    return
  }
  const display = []
  const labels  = []
  const samples = arbSamples.value
  for (let i = 0; i < samples.length; i += 8) {
    display.push(samples[i])
    labels.push('')
  }
  arbChart.data.labels           = labels
  arbChart.data.datasets[0].data = display
  arbChart.update('none')
}

async function uploadArb() {
  arbUploading.value = true
  arbResult.value    = null
  try {
    const res = await fetch('/api/upload_waveform', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slot: arbSlot.value, samples: arbSamples.value }),
    })
    const data = await res.json()
    arbResult.value = data

    // After successful upload, optionally select the waveform on a channel
    if (data.ok && arbChannel.value !== '---') {
      await sendCmd({
        function: arbChannel.value,
        waveform: `Arb ${arbSlot.value}`,
      })
    }
  } catch (e) {
    arbResult.value = { ok: false, error: e.message }
  } finally {
    arbUploading.value = false
  }
}

onUnmounted(() => { if (arbChart) arbChart.destroy() })
</script>
