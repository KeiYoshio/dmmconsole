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

      <!-- VISA string (USB) – combobox with device discovery -->
      <v-col v-else-if="form.interface === 'usb'" cols="12" sm="4">
        <v-combobox
          :model-value="form.visa_string"
          @update:model-value="v => form.visa_string = typeof v === 'object' && v ? (v.visa_string ?? '') : (v ?? '')"
          :items="usbDevices"
          item-title="visa_string"
          item-value="visa_string"
          label="VISA Resource"
          density="compact"
          hide-details
          :loading="loadingUsb"
          :disabled="instrStore.connected"
          placeholder="USB0::0x0957::..."
          no-filter
          :no-data-text="loadingUsb ? 'Scanning…' : 'No USB devices found'"
          @focus="fetchUsbDevices"
        >
          <template #item="{ item, props }">
            <v-list-item v-bind="props">
              <template #title>
                <span class="text-body-2 font-weight-medium">
                  {{ [item.raw.manufacturer, item.raw.product].filter(Boolean).join(' ') || item.raw.visa_string }}
                </span>
              </template>
              <template #subtitle>
                <span
                  v-if="item.raw.manufacturer || item.raw.product"
                  style="font-family: monospace; font-size: 0.75rem"
                >{{ item.raw.visa_string }}</span>
              </template>
            </v-list-item>
          </template>
        </v-combobox>
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
import { ref, reactive } from 'vue'
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

const usbDevices = ref([])
const loadingUsb = ref(false)

async function fetchUsbDevices() {
  if (loadingUsb.value) return
  loadingUsb.value = true
  try {
    const res  = await fetch('/api/terminal/usb_resources')
    const data = await res.json()
    usbDevices.value = data.devices ?? []
  } catch {
    usbDevices.value = []
  } finally {
    loadingUsb.value = false
  }
}

async function doConnect() {
  await instrStore.connect({ ...form })
}

async function doDisconnect() {
  measStore.stop()
  measStore.closeWS()
  await instrStore.disconnect()
}
</script>
