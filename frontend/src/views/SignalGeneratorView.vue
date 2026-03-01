<template>
  <v-app>
    <!-- Top toolbar -->
    <v-app-bar color="surface" elevation="2" density="compact">
      <template #prepend>
        <v-btn icon="mdi-home" @click="router.push('/')" />
      </template>
      <v-app-bar-title>
        <span class="text-medium-emphasis">Instrument Console</span>
        <span class="text-medium-emphasis"> › </span>
        <v-icon icon="mdi-waveform" color="primary" class="me-1" />
        <span class="text-primary font-weight-bold">Signal Generator</span>
      </v-app-bar-title>
      <template #append>
        <span class="text-caption text-disabled me-3">v{{ version }}</span>
        <v-chip
          :color="instrStore.connected ? 'secondary' : 'default'"
          size="small"
          :prepend-icon="instrStore.connected ? 'mdi-check-circle' : 'mdi-circle-outline'"
          class="me-2"
        >{{ instrStore.connected ? 'Connected' : 'Disconnected' }}</v-chip>
      </template>
    </v-app-bar>

    <v-main>
      <v-container fluid class="pa-3">

        <!-- Connection bar -->
        <ConnectionBar class="mb-3" />

        <!-- Main layout -->
        <v-row no-gutters class="ga-3">

          <!-- Signal Generator control panel -->
          <v-col v-if="instrStore.connected" cols="12">
            <SignalGeneratorPanel />
          </v-col>

          <!-- Measurement display + waveform (for counter mode) -->
          <v-col cols="12">
            <MeasurementDisplay class="mb-3" />
            <Waveform />
          </v-col>

        </v-row>

        <!-- Not connected placeholder -->
        <v-row v-if="!instrStore.connected" justify="center" class="mt-8">
          <v-col cols="auto" class="text-center">
            <v-icon size="80" color="surface-2">mdi-waveform</v-icon>
            <div class="text-h6 text-medium-emphasis mt-2">Select an instrument and connect</div>
          </v-col>
        </v-row>

      </v-container>
    </v-main>
  </v-app>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useInstrumentStore } from '../stores/instrument'

import ConnectionBar         from '../components/ConnectionBar.vue'
import MeasurementDisplay    from '../components/MeasurementDisplay.vue'
import Waveform              from '../components/Waveform.vue'
import SignalGeneratorPanel  from '../components/panels/SignalGeneratorPanel.vue'

const router     = useRouter()
const instrStore = useInstrumentStore()
const version    = ref('')

onMounted(async () => {
  instrStore.fetchModels()
  const res = await fetch('/api/version')
  const data = await res.json()
  version.value = data.version ?? ''
})
</script>
