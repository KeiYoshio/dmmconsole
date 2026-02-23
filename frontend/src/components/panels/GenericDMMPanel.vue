<!--
  GenericDMMPanel – dynamically built from the instrument's capability descriptor.

  Layout:
    Left  : Function buttons (from capability.functions)
    Center: Range buttons    (from capability.ranges[currentFunction])
    Right : Settings         (from capability.settings)
-->
<template>
  <v-card color="surface" rounded="lg" class="pa-3">
    <v-row no-gutters class="ga-2">

      <!-- ── Function buttons ── -->
      <v-col cols="auto">
        <div class="text-caption text-medium-emphasis mb-1">Function</div>
        <div class="d-flex flex-wrap ga-1" style="max-width:200px">
          <v-btn
            v-for="fn in cap.functions"
            :key="fn.id"
            size="small"
            :color="instrStore.currentFunction === fn.id ? 'primary' : undefined"
            :variant="instrStore.currentFunction === fn.id ? 'flat' : 'tonal'"
            :prepend-icon="fn.icon"
            :disabled="!instrStore.connected"
            @click="setFunction(fn.id)"
          >{{ fn.label }}</v-btn>
        </div>
      </v-col>

      <v-divider vertical class="mx-1" />

      <!-- ── Range buttons ── -->
      <v-col cols="auto">
        <div class="text-caption text-medium-emphasis mb-1">Range</div>
        <div
          v-if="currentRanges.length"
          class="d-flex flex-wrap ga-1"
          style="max-width:200px"
        >
          <v-btn
            v-for="r in currentRanges"
            :key="r"
            size="small"
            :color="instrStore.currentRange === r ? 'secondary' : undefined"
            :variant="instrStore.currentRange === r ? 'flat' : 'tonal'"
            :disabled="!instrStore.connected"
            @click="setRange(r)"
          >{{ r }}</v-btn>
        </div>
        <div v-else class="text-caption text-disabled">N/A</div>
      </v-col>

      <v-divider vertical class="mx-1" />

      <!-- ── Settings ── -->
      <v-col cols="auto">
        <div class="text-caption text-medium-emphasis mb-1">Settings</div>
        <div
          v-for="s in applicableSettings"
          :key="s.id"
          class="mb-2"
          style="min-width:130px"
        >
          <div class="text-caption text-disabled">{{ s.label }}</div>

          <!-- select type -->
          <v-btn-toggle
            v-if="s.type === 'select'"
            v-model="settingValues[s.id]"
            density="compact"
            divided
            mandatory
            color="primary"
            @update:model-value="val => setSetting(s.id, val)"
          >
            <v-btn
              v-for="opt in s.options"
              :key="opt"
              :value="opt"
              size="x-small"
              :disabled="!instrStore.connected"
            >{{ opt }}</v-btn>
          </v-btn-toggle>
        </div>
      </v-col>

      <v-divider vertical class="mx-1" />

      <!-- ── Utility buttons ── -->
      <!-- ── Command error ── -->
      <v-col v-if="cmdError" cols="12">
        <v-alert type="error" density="compact" closable @click:close="cmdError=''">
          {{ cmdError }}
        </v-alert>
      </v-col>

      <v-col cols="auto" class="d-flex flex-column ga-1">
        <div class="text-caption text-medium-emphasis mb-1">Utility</div>
        <v-btn
          size="small"
          prepend-icon="mdi-restart"
          :disabled="!instrStore.connected"
          @click="instrStore.resetInstrument()"
        >Reset</v-btn>
        <v-btn
          size="small"
          prepend-icon="mdi-magnify"
          :disabled="!instrStore.connected"
          @click="measureOnce"
        >Measure</v-btn>
      </v-col>

    </v-row>
  </v-card>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useInstrumentStore }  from '../../stores/instrument'
import { useMeasurementStore } from '../../stores/measurement'

const instrStore = useInstrumentStore()
const measStore  = useMeasurementStore()

const cap = computed(() => instrStore.capability ?? { functions: [], ranges: {}, settings: [] })

const currentRanges = computed(() =>
  cap.value.ranges?.[instrStore.currentFunction] ?? []
)

const applicableSettings = computed(() =>
  (cap.value.settings ?? []).filter(s =>
    !s.applicable_to || s.applicable_to.includes(instrStore.currentFunction)
  )
)

// Local setting values initialised from capability defaults
const settingValues = reactive({})
watch(() => cap.value, (c) => {
  ;(c.settings ?? []).forEach(s => { settingValues[s.id] = s.default })
}, { immediate: true })

// Error display
const cmdError = ref('')

async function sendCmd(settings) {
  cmdError.value = ''
  await instrStore.sendCommand(settings)
}

// ------------------------------------------------------------------ actions

async function setFunction(fnId) {
  try {
    await sendCmd({ function: fnId })
    const firstRange = currentRanges.value[0]
    if (firstRange) await sendCmd({ range: firstRange })
  } catch (e) {
    cmdError.value = e.message
    console.error(e)
  }
}

async function setRange(r) {
  try { await sendCmd({ range: r }) }
  catch (e) { cmdError.value = e.message; console.error(e) }
}

async function setSetting(id, value) {
  try { await sendCmd({ [id]: value }) }
  catch (e) { cmdError.value = e.message; console.error(e) }
}

async function measureOnce() {
  try {
    const res  = await fetch('/api/measure', { method: 'POST' })
    const data = await res.json()
    measStore.latest = data
  } catch (e) { console.error(e) }
}
</script>
