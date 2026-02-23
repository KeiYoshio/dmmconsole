<template>
  <v-app>
    <!-- App bar -->
    <v-app-bar color="surface" elevation="2" density="compact">
      <template #prepend>
        <v-btn icon="mdi-home" @click="router.push('/')" />
      </template>
      <v-app-bar-title>
        <span class="text-medium-emphasis">Instrument Console</span>
        <span class="text-medium-emphasis"> › </span>
        <v-icon icon="mdi-console" color="primary" class="me-1" />
        <span class="text-primary font-weight-bold">Terminal</span>
      </v-app-bar-title>
      <template #append>
        <v-chip
          :color="termStore.connected ? 'secondary' : 'default'"
          size="small"
          :prepend-icon="termStore.connected ? 'mdi-check-circle' : 'mdi-circle-outline'"
          class="me-2"
        >{{ termStore.connected ? 'Connected' : 'Disconnected' }}</v-chip>
      </template>
    </v-app-bar>

    <v-main>
      <div class="term-layout">

        <!-- ── Connection bar ───────────────────────────────────────── -->
        <v-card class="pa-3 flex-shrink-0">
          <v-row align="center" no-gutters class="ga-2">

            <!-- Interface -->
            <v-col cols="6" sm="2">
              <v-select
                v-model="form.interface"
                :items="interfaces"
                label="Interface"
                density="compact"
                hide-details
                :disabled="termStore.connected"
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
                :disabled="termStore.connected"
              />
            </v-col>

            <!-- IP address (LAN) -->
            <v-col v-else-if="form.interface === 'lan'" cols="6" sm="2">
              <v-text-field
                v-model="form.ip_address"
                label="IP Address"
                density="compact"
                hide-details
                :disabled="termStore.connected"
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
                :disabled="termStore.connected"
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
                        class="text-caption visa-mono"
                      >{{ item.raw.visa_string }}</span>
                    </template>
                  </v-list-item>
                </template>
              </v-combobox>
            </v-col>

            <!-- Connect / Disconnect -->
            <v-col cols="auto">
              <v-btn
                v-if="!termStore.connected"
                color="secondary"
                :loading="termStore.connecting"
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

            <!-- IDN / error chip -->
            <v-col cols="12" sm>
              <v-chip
                v-if="termStore.connected"
                color="secondary"
                size="small"
                prepend-icon="mdi-check-circle"
                class="text-truncate"
                style="max-width:100%"
              >{{ termStore.idn || 'Connected' }}</v-chip>
              <v-chip
                v-if="termStore.error"
                color="error"
                size="small"
                prepend-icon="mdi-alert-circle"
              >{{ termStore.error }}</v-chip>
            </v-col>

          </v-row>
        </v-card>

        <!-- ── TX / RX panes ──────────────────────────────────────── -->
        <div class="pane-row">

          <!-- TX -->
          <v-card class="pane-card">
            <div class="pane-header">
              <v-icon icon="mdi-arrow-up-circle" color="primary" size="16" />
              <span class="pane-title">TX – Sent Commands</span>
              <v-spacer />
              <v-btn
                icon="mdi-delete-sweep"
                size="x-small"
                variant="text"
                title="Clear history"
                @click="termStore.clearHistory()"
              />
            </div>
            <v-divider />
            <div ref="txPane" class="log-pane">
              <div
                v-for="entry in termStore.txHistory"
                :key="entry.id"
                class="log-entry"
              >
                <span class="log-id">[{{ entry.id }}]</span>
                <span class="log-ts">{{ fmtTime(entry.ts) }}</span>
                <span class="log-cmd">{{ entry.command }}</span>
                <span v-if="fmtEol(entry.lineEnding)" class="log-eol">{{ fmtEol(entry.lineEnding) }}</span>
              </div>
              <div v-if="termStore.txHistory.length === 0" class="log-empty">
                No commands sent yet.
              </div>
            </div>
          </v-card>

          <!-- RX -->
          <v-card class="pane-card">
            <div class="pane-header">
              <v-icon icon="mdi-arrow-down-circle" color="secondary" size="16" />
              <span class="pane-title">RX – Received Responses</span>
            </div>
            <v-divider />
            <div ref="rxPane" class="log-pane">
              <div
                v-for="entry in termStore.rxHistory"
                :key="entry.id"
                class="log-entry"
                :class="{ 'log-entry--error': !!entry.error }"
              >
                <span class="log-id">[{{ entry.id }}]</span>
                <span class="log-ts">{{ fmtTime(entry.ts) }}</span>
                <span v-if="entry.response !== null" class="log-response">{{ entry.response }}</span>
                <span v-else class="log-error">{{ entry.error }}</span>
              </div>
              <div v-if="termStore.rxHistory.length === 0" class="log-empty">
                No responses yet.
              </div>
            </div>
          </v-card>

        </div>

        <!-- ── Command input ──────────────────────────────────────── -->
        <v-card class="pa-3 flex-shrink-0">
          <v-row no-gutters align="center" class="ga-2">

            <!-- CR / LF toggle buttons -->
            <v-col cols="auto">
              <v-btn-toggle
                v-model="selectedEol"
                multiple
                density="compact"
                variant="outlined"
                color="primary"
                rounded="lg"
              >
                <v-btn value="cr" size="small" class="px-3">CR</v-btn>
                <v-btn value="lf" size="small" class="px-3">LF</v-btn>
              </v-btn-toggle>
            </v-col>

            <!-- Command text field -->
            <v-col>
              <v-text-field
                ref="cmdInputRef"
                v-model="cmdInput"
                label="Command String"
                density="compact"
                hide-details
                :disabled="!termStore.connected || sending"
                placeholder="e.g. *IDN?  or  :CONF:VOLT:DC"
                @keydown.enter="doSend"
              />
            </v-col>

            <!-- Send button -->
            <v-col cols="auto">
              <v-btn
                color="primary"
                :disabled="!termStore.connected || !cmdInput.trim()"
                :loading="sending"
                prepend-icon="mdi-send"
                @click="doSend"
              >Send</v-btn>
            </v-col>

          </v-row>
        </v-card>

      </div>
    </v-main>
  </v-app>
</template>

<script setup>
import { ref, reactive, computed, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useTerminalStore } from '../stores/terminal'

const router    = useRouter()
const termStore = useTerminalStore()

const interfaces = [
  { title: 'GPIB (82357B)', value: 'gpib' },
  { title: 'LAN / VXI-11',  value: 'lan'  },
  { title: 'USB-TMC',        value: 'usb'  },
]

const form = reactive({
  interface:   'gpib',
  gpib_addr:   6,
  ip_address:  '',
  visa_string: '',
})

// ── Line-ending selection (v-btn-toggle multiple) ─────────────────────────
// Default: LF only (standard for GPIB/SCPI)
const selectedEol = ref(['lf'])

const lineEnding = computed(() => {
  const cr = selectedEol.value.includes('cr') ? '\r' : ''
  const lf = selectedEol.value.includes('lf') ? '\n' : ''
  return cr + lf
})

function fmtEol(le) {
  if (!le) return ''
  if (le === '\r\n') return '[CRLF]'
  if (le === '\r')   return '[CR]'
  if (le === '\n')   return '[LF]'
  return ''
}

// ── Refs ──────────────────────────────────────────────────────────────────
const cmdInput    = ref('')
const sending     = ref(false)
const cmdInputRef = ref(null)
const txPane      = ref(null)
const rxPane      = ref(null)

// ── USB device discovery ───────────────────────────────────────────────────
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

// ── Actions ───────────────────────────────────────────────────────────────

async function doConnect() {
  await termStore.connect({ ...form })
}

async function doDisconnect() {
  await termStore.disconnect()
}

async function doSend() {
  const cmd = cmdInput.value.trim()
  if (!cmd || !termStore.connected || sending.value) return
  sending.value = true
  try {
    await termStore.send(cmd, lineEnding.value)
    cmdInput.value = ''
  } finally {
    sending.value = false
    // Restore focus to the input field for continuous entry
    await nextTick()
    cmdInputRef.value?.$el?.querySelector('input')?.focus()
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────

function fmtTime(ts) {
  return new Date(ts * 1000).toTimeString().slice(0, 8)
}

// ── Auto-scroll panes to bottom on new entries ────────────────────────────

watch(() => termStore.txHistory.length, async () => {
  await nextTick()
  if (txPane.value) txPane.value.scrollTop = txPane.value.scrollHeight
})

watch(() => termStore.rxHistory.length, async () => {
  await nextTick()
  if (rxPane.value) rxPane.value.scrollTop = rxPane.value.scrollHeight
})
</script>

<style scoped>
/* Full-height flex column layout inside v-main.
   v-app-bar with density="compact" is 48 px. */
.term-layout {
  height: calc(100vh - 48px);
  display: flex;
  flex-direction: column;
  padding: 12px;
  gap: 12px;
  box-sizing: border-box;
  overflow: hidden;
}

/* Middle row holds both panes side-by-side */
.pane-row {
  flex: 1;
  min-height: 0;
  display: flex;
  gap: 12px;
}

/* Each pane card stretches vertically */
.pane-card {
  flex: 1;
  min-width: 0;
  display: flex !important;
  flex-direction: column;
  overflow: hidden;
}

/* Pane title bar */
.pane-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  flex-shrink: 0;
}

.pane-title {
  font-size: 0.8125rem;
  font-weight: 500;
  letter-spacing: 0.01em;
}

/* Scrollable log area */
.log-pane {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 6px 12px;
  font-family: 'Courier New', Courier, monospace;
  font-size: 0.8125rem;
  line-height: 1.6;
}

/* Individual log line */
.log-entry {
  display: flex;
  gap: 8px;
  align-items: baseline;
  padding: 1px 0;
}

.log-id {
  color: rgba(var(--v-theme-on-surface), 0.38);
  min-width: 2.8rem;
  text-align: right;
  flex-shrink: 0;
}

.log-ts {
  color: rgba(var(--v-theme-on-surface), 0.38);
  flex-shrink: 0;
}

.log-cmd {
  color: rgb(var(--v-theme-primary));
  word-break: break-all;
}

.log-eol {
  color: rgba(var(--v-theme-on-surface), 0.38);
  font-size: 0.7rem;
  flex-shrink: 0;
}

.log-response {
  color: rgb(var(--v-theme-secondary));
  word-break: break-all;
}

.log-error,
.log-entry--error .log-response {
  color: rgb(var(--v-theme-error));
  word-break: break-all;
}

.log-empty {
  color: rgba(var(--v-theme-on-surface), 0.38);
  font-style: italic;
  padding: 4px 0;
}

.visa-mono {
  font-family: 'Courier New', Courier, monospace;
}
</style>
