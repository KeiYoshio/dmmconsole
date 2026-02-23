<template>
  <v-app>
    <v-app-bar color="surface" elevation="2" density="compact">
      <v-app-bar-title>
        <v-icon icon="mdi-instruments" color="primary" class="me-2" />
        <span class="text-primary font-weight-bold">Instrument</span>
        <span class="text-medium-emphasis"> Console</span>
      </v-app-bar-title>
      <template #append>
        <span class="text-caption text-disabled me-3">v{{ version }}</span>
      </template>
    </v-app-bar>

    <v-main>
      <v-container class="pa-6">
        <div class="text-h6 text-medium-emphasis mb-4">Instruments</div>
        <v-row>
          <!-- DMM card -->
          <v-col cols="12" sm="6" md="4" lg="3">
            <v-card
              hover
              @click="router.push('/dmm')"
            >
              <v-card-item>
                <template #prepend>
                  <v-icon icon="mdi-meter-electric" color="primary" size="32" />
                </template>
                <v-card-title>Digital Multimeter</v-card-title>
                <v-card-subtitle>DMM control &amp; measurement</v-card-subtitle>
              </v-card-item>
            </v-card>
          </v-col>

          <!-- Terminal card -->
          <v-col cols="12" sm="6" md="4" lg="3">
            <v-card hover @click="router.push('/terminal')">
              <v-card-item>
                <template #prepend>
                  <v-icon icon="mdi-console" color="primary" size="32" />
                </template>
                <v-card-title>Inst. Terminal</v-card-title>
                <v-card-subtitle>Raw command console</v-card-subtitle>
              </v-card-item>
            </v-card>
          </v-col>

          <!-- Coming soon placeholder -->
          <v-col cols="12" sm="6" md="4" lg="3">
            <v-card disabled>
              <v-card-item>
                <template #prepend>
                  <v-icon icon="mdi-help-circle-outline" size="32" />
                </template>
                <v-card-title>Coming Soon</v-card-title>
                <v-card-subtitle>More instruments</v-card-subtitle>
              </v-card-item>
            </v-card>
          </v-col>
        </v-row>
      </v-container>
    </v-main>
  </v-app>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router  = useRouter()
const version = ref('')

onMounted(async () => {
  const res = await fetch('/api/version')
  const data = await res.json()
  version.value = data.version ?? ''
})
</script>
