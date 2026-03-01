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
          <v-text-field
            v-model.number="chForm.frequency"
            label="Frequency (Hz)"
            type="number"
            density="compact"
            hide-details
            :disabled="!instrStore.connected"
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
      <v-row no-gutters class="ga-3">
        <v-col cols="12" sm="4">
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
import { ref, reactive, watch } from 'vue'
import { useInstrumentStore }  from '../../stores/instrument'
import { useMeasurementStore } from '../../stores/measurement'

const instrStore = useInstrumentStore()
const measStore  = useMeasurementStore()

const activeTab = ref('CH1')
const cmdError  = ref('')

const waveformOptions = [
  'Sine', 'Square', 'Rectangle', 'Trapezoid', 'CMOS', 'Adj Pulse',
  'DC', 'Triangle', 'Ramp', 'Staircase+', 'Staircase-',
  'Half Wave', 'Full Wave', 'Pos Stair', 'Neg Stair',
  'Noise', 'Exp Rise', 'Exp Decay', 'Multi Tone', 'Sinc', 'Lorenz',
  'Impulse', 'PRBS', 'AM', 'FM', 'Chirp', 'ECG',
  'Gauss', 'LFPulse', 'RSPulse', 'CPulse', 'PWM', 'NPulse', 'Trapezia',
]

// Per-channel form state
const chForm = reactive({
  waveform:  'Sine',
  frequency: 1000.0,
  amplitude: 1.0,
  offset:    0.0,
  duty:      50.0,
  phase:     0.0,
  output:    false,
})

const gateTime = ref('1s')

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
  try {
    await sendCmd({ function: tab })
    // Fetch channel state from backend
    const res = await fetch(`/api/channel_state/${tab}`)
    if (res.ok) {
      const state = await res.json()
      if (tab === 'COUNTER') {
        gateTime.value = state.gate_time ?? '1s'
      } else {
        chForm.waveform  = state.waveform  ?? 'Sine'
        chForm.frequency = state.frequency ?? 1000.0
        chForm.amplitude = state.amplitude ?? 1.0
        chForm.offset    = state.offset    ?? 0.0
        chForm.duty      = state.duty      ?? 50.0
        chForm.phase     = state.phase     ?? 0.0
        chForm.output    = state.output    ?? false
        // Reset last-applied tracking
        lastApplied.frequency = chForm.frequency
        lastApplied.amplitude = chForm.amplitude
        lastApplied.offset    = chForm.offset
        lastApplied.duty      = chForm.duty
        lastApplied.phase     = chForm.phase
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
          chForm.waveform  = state.waveform  ?? 'Sine'
          chForm.frequency = state.frequency ?? 1000.0
          chForm.amplitude = state.amplitude ?? 1.0
          chForm.offset    = state.offset    ?? 0.0
          chForm.duty      = state.duty      ?? 50.0
          chForm.phase     = state.phase     ?? 0.0
          chForm.output    = state.output    ?? false
          lastApplied.frequency = chForm.frequency
          lastApplied.amplitude = chForm.amplitude
          lastApplied.offset    = chForm.offset
          lastApplied.duty      = chForm.duty
          lastApplied.phase     = chForm.phase
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
  if (chForm.frequency === lastApplied.frequency) return
  lastApplied.frequency = chForm.frequency
  await sendCmd({ frequency: chForm.frequency })
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

async function toggleOutput() {
  chForm.output = !chForm.output
  await sendCmd({ output: chForm.output })
}
</script>
