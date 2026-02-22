<template>
  <v-card
    color="dmm-display"
    class="dmm-display d-flex flex-column align-center justify-center pa-4"
    elevation="8"
    rounded="lg"
    style="min-height: 160px"
  >
    <!-- Value -->
    <div class="dmm-value text-center" :class="valueColor">
      {{ displayValue }}
    </div>

    <!-- Unit + function badges -->
    <div class="d-flex ga-2 mt-2">
      <v-chip size="small" color="primary"  label>{{ measStore.latest?.function ?? instrStore.currentFunction }}</v-chip>
      <v-chip size="small" color="secondary" label>{{ measStore.latest?.range ?? instrStore.currentRange }}</v-chip>
      <v-chip v-if="measStore.streaming" size="small" color="warning" label>
        <v-icon start size="x-small">mdi-circle</v-icon>LIVE
      </v-chip>
    </div>

    <!-- Error overlay -->
    <v-chip v-if="measStore.wsError" color="error" class="mt-2" size="small" prepend-icon="mdi-alert">
      {{ measStore.wsError }}
    </v-chip>
  </v-card>
</template>

<script setup>
import { computed } from 'vue'
import { useInstrumentStore }  from '../stores/instrument'
import { useMeasurementStore } from '../stores/measurement'

const instrStore = useInstrumentStore()
const measStore  = useMeasurementStore()

const displayValue = computed(() => {
  if (!instrStore.connected) return '----'
  return measStore.latest?.value_str ?? '----'
})

const valueColor = computed(() => {
  if (measStore.wsError) return 'text-error'
  if (!measStore.latest) return 'text-disabled'
  return 'text-dmm-value'
})
</script>

<style scoped>
.dmm-display {
  font-family: 'Courier New', 'Roboto Mono', monospace;
  background: rgb(var(--v-theme-dmm-display)) !important;
  border: 1px solid rgba(var(--v-theme-primary), 0.3);
}
.dmm-value {
  font-size: clamp(2rem, 5vw, 3.5rem);
  font-weight: 700;
  letter-spacing: 0.05em;
  white-space: nowrap;
}
</style>
