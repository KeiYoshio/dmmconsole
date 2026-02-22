import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useInstrumentStore = defineStore('instrument', () => {
  // All available models fetched from backend
  const models      = ref([])
  const connected   = ref(false)
  const connecting  = ref(false)
  const modelId     = ref(null)
  const capability  = ref(null)
  const idn         = ref('')
  const error       = ref('')

  // Current instrument settings
  const currentFunction = ref('DCV')
  const currentRange    = ref('AUTO')
  const currentNplc     = ref(10)

  const currentModel = computed(() =>
    models.value.find(m => m.id === modelId.value) ?? null
  )

  // ------------------------------------------------------------------
  // Actions
  // ------------------------------------------------------------------

  async function fetchModels() {
    const res = await fetch('/api/instruments')
    models.value = await res.json()
  }

  async function connect(config) {
    connecting.value = true
    error.value      = ''
    try {
      const res  = await fetch('/api/connect', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(config),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail ?? 'Connection failed')

      modelId.value    = config.model_id
      capability.value = models.value.find(m => m.id === config.model_id)?.capability ?? null
      idn.value        = data.idn ?? ''
      connected.value  = true

      // Reset settings to defaults from capability
      const firstFunc = capability.value?.functions?.[0]
      if (firstFunc) currentFunction.value = firstFunc.id
      currentRange.value = 'AUTO'
      currentNplc.value  = capability.value?.settings?.find(s => s.id === 'nplc')?.default ?? 10
    } catch (e) {
      error.value = e.message
    } finally {
      connecting.value = false
    }
  }

  async function disconnect() {
    await fetch('/api/disconnect', { method: 'POST' })
    connected.value  = false
    modelId.value    = null
    capability.value = null
    idn.value        = ''
  }

  async function sendCommand(settings) {
    const res = await fetch('/api/command', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(settings),
    })
    if (!res.ok) {
      const data = await res.json()
      throw new Error(data.detail ?? 'Command failed')
    }
    // Update local state
    if (settings.function !== undefined) currentFunction.value = settings.function
    if (settings.range    !== undefined) currentRange.value    = settings.range
    if (settings.nplc     !== undefined) currentNplc.value     = settings.nplc
  }

  async function resetInstrument() {
    await fetch('/api/reset', { method: 'POST' })
  }

  return {
    models, connected, connecting, modelId, capability, idn, error,
    currentFunction, currentRange, currentNplc, currentModel,
    fetchModels, connect, disconnect, sendCommand, resetInstrument,
  }
})
