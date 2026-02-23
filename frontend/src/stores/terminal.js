import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useTerminalStore = defineStore('terminal', () => {
  const connected  = ref(false)
  const connecting = ref(false)
  const idn        = ref('')
  const error      = ref('')

  // TX: all sent commands  [{ id, ts, command }]
  // RX: query responses / errors  [{ id, ts, response, error }]
  const txHistory = ref([])
  const rxHistory = ref([])

  let _nextId = 1

  // ------------------------------------------------------------------
  // Connection
  // ------------------------------------------------------------------

  async function connect(config) {
    connecting.value = true
    error.value      = ''
    try {
      const res  = await fetch('/api/terminal/connect', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(config),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail ?? 'Connection failed')
      idn.value       = data.idn ?? ''
      connected.value = true
    } catch (e) {
      error.value = e.message
    } finally {
      connecting.value = false
    }
  }

  async function disconnect() {
    await fetch('/api/terminal/disconnect', { method: 'POST' })
    connected.value = false
    idn.value       = ''
  }

  // ------------------------------------------------------------------
  // Send command
  // ------------------------------------------------------------------

  async function send(command, lineEnding = '') {
    const id = _nextId++
    const ts = Date.now() / 1000

    txHistory.value.push({ id, ts, command, lineEnding })

    try {
      const res  = await fetch('/api/terminal/send', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ command, line_ending: lineEnding }),
      })
      const data = await res.json()

      if (!res.ok) {
        // HTTP-level error (4xx / 5xx)
        rxHistory.value.push({ id, ts: Date.now() / 1000, response: null, error: data.detail ?? 'Error' })
      } else if (!data.ok) {
        // Application-level error returned as 200
        rxHistory.value.push({ id, ts: Date.now() / 1000, response: null, error: data.error ?? 'Unknown error' })
      } else if (data.response !== null && data.response !== undefined) {
        // Successful query response
        rxHistory.value.push({ id, ts: Date.now() / 1000, response: data.response, error: null })
      }
      // Successful write (response === null): nothing in RX pane
    } catch (e) {
      rxHistory.value.push({ id, ts: Date.now() / 1000, response: null, error: e.message })
    }
  }

  // ------------------------------------------------------------------
  // Utilities
  // ------------------------------------------------------------------

  function clearHistory() {
    txHistory.value = []
    rxHistory.value = []
    _nextId = 1
  }

  return {
    connected, connecting, idn, error,
    txHistory, rxHistory,
    connect, disconnect, send, clearHistory,
  }
})
