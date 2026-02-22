<template>
  <v-card class="pa-3" color="surface">
    <v-row align="center" no-gutters class="ga-2">

      <!-- Model selector -->
      <v-col cols="12" sm="3">
        <v-select
          v-model="form.model_id"
          :items="instrStore.models"
          item-title="model"
          item-value="id"
          label="Instrument"
          density="compact"
          hide-details
          :disabled="instrStore.connected"
        />
      </v-col>

      <!-- Interface selector -->
      <v-col cols="6" sm="2">
        <v-select
          v-model="form.interface"
          :items="interfaces"
          label="Interface"
          density="compact"
          hide-details
          :disabled="instrStore.connected"
        />
      </v-col>

      <!-- GPIB address -->
      <v-col v-if="form.interface === 'gpib'" cols="6" sm="1">
        <v-text-field
          v-model.number="form.gpib_addr"
          label="Addr"
          type="number"
          min="0" max="30"
          density="compact"
          hide-details
          :disabled="instrStore.connected"
        />
      </v-col>

      <!-- IP address (LAN) -->
      <v-col v-else-if="form.interface === 'lan'" cols="6" sm="2">
        <v-text-field
          v-model="form.ip_address"
          label="IP Address"
          density="compact"
          hide-details
          :disabled="instrStore.connected"
        />
      </v-col>

      <!-- VISA string (USB) -->
      <v-col v-else-if="form.interface === 'usb'" cols="6" sm="3">
        <v-text-field
          v-model="form.visa_string"
          label="VISA Resource"
          density="compact"
          hide-details
          placeholder="USB0::0x0957::..."
          :disabled="instrStore.connected"
        />
      </v-col>

      <!-- Connect / Disconnect button -->
      <v-col cols="auto">
        <v-btn
          v-if="!instrStore.connected"
          color="secondary"
          :loading="instrStore.connecting"
          prepend-icon="mdi-lan-connect"
          @click="doConnect"
        >Connect</v-btn>
        <v-btn
          v-else
          color="error"
          prepend-icon="mdi-lan-disconnect"
          @click="doDisconnect"
        >Disconnect</v-btn>
      </v-col>

      <!-- IDN / status chip -->
      <v-col cols="12" sm>
        <v-chip
          v-if="instrStore.connected"
          color="secondary"
          size="small"
          prepend-icon="mdi-check-circle"
          class="text-truncate"
          style="max-width:100%"
        >{{ instrStore.idn || instrStore.currentModel?.model }}</v-chip>
        <v-chip
          v-if="instrStore.error"
          color="error"
          size="small"
          prepend-icon="mdi-alert-circle"
        >{{ instrStore.error }}</v-chip>
      </v-col>

    </v-row>
  </v-card>
</template>

<script setup>
import { reactive } from 'vue'
import { useInstrumentStore }  from '../stores/instrument'
import { useMeasurementStore } from '../stores/measurement'

const instrStore = useInstrumentStore()
const measStore  = useMeasurementStore()

const interfaces = [
  { title: 'GPIB (82357B)', value: 'gpib' },
  { title: 'LAN / VXI-11',  value: 'lan'  },
  { title: 'USB-TMC',        value: 'usb'  },
]

const form = reactive({
  model_id:    instrStore.models[0]?.id ?? 'hp34401a',
  interface:   'gpib',
  gpib_addr:   6,
  ip_address:  '',
  visa_string: '',
})

async function doConnect() {
  await instrStore.connect({ ...form })
}

async function doDisconnect() {
  measStore.stop()
  measStore.closeWS()
  await instrStore.disconnect()
}
</script>
