import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const WS_URL = `ws://${location.host}/ws/stream`
const MAX_POINTS = 500

export const useMeasurementStore = defineStore('measurement', () => {
  const latest      = ref(null)   // last MeasurementResult
  const buffer      = ref([])     // rolling window for chart
  const streaming   = ref(false)
  const intervalMs  = ref(300)
  const wsError     = ref('')
  let _ws           = null

  const chartLabels  = computed(() => buffer.value.map(d => {
    const dt = new Date(d.timestamp * 1000)
    return dt.toLocaleTimeString('en', { hour12: false, fractionalSecondDigits: 1 })
  }))
  const chartValues  = computed(() => buffer.value.map(d => d.value))
  const chartUnit    = computed(() => latest.value?.unit ?? '')

  // ------------------------------------------------------------------
  // WebSocket management
  // ------------------------------------------------------------------

  function _openWS() {
    if (_ws) _ws.close()
    _ws = new WebSocket(WS_URL)

    _ws.onmessage = (ev) => {
      const data = JSON.parse(ev.data)
      if (data.status === 'started') { streaming.value = true;  return }
      if (data.status === 'stopped') { streaming.value = false; return }
      if (data.error)                { wsError.value = data.error; return }

      latest.value = data
      buffer.value.push(data)
      if (buffer.value.length > MAX_POINTS) buffer.value.shift()
    }

    _ws.onerror = () => { wsError.value = 'WebSocket error' }
    _ws.onclose = () => { streaming.value = false }
  }

  function ensureWS() {
    if (!_ws || _ws.readyState > WebSocket.OPEN) _openWS()
  }

  function start(ms) {
    intervalMs.value = ms ?? intervalMs.value
    wsError.value    = ''
    ensureWS()
    const send = () => {
      if (_ws.readyState === WebSocket.OPEN) {
        _ws.send(JSON.stringify({ action: 'start', interval_ms: intervalMs.value }))
      } else {
        setTimeout(send, 100)
      }
    }
    send()
  }

  function stop() {
    if (_ws && _ws.readyState === WebSocket.OPEN) {
      _ws.send(JSON.stringify({ action: 'stop' }))
    }
  }

  function changeInterval(ms) {
    intervalMs.value = ms
    if (_ws && _ws.readyState === WebSocket.OPEN) {
      _ws.send(JSON.stringify({ action: 'config', interval_ms: ms }))
    }
  }

  function clearBuffer() {
    buffer.value = []
    latest.value = null
  }

  function closeWS() {
    stop()
    if (_ws) { _ws.close(); _ws = null }
    streaming.value = false
  }

  return {
    latest, buffer, streaming, intervalMs, wsError,
    chartLabels, chartValues, chartUnit,
    start, stop, changeInterval, clearBuffer, closeWS,
  }
})
