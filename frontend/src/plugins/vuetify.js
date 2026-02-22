import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'
import { createVuetify } from 'vuetify'

// Custom theme – change these two color blocks to restyle the whole app
const dmmTheme = {
  dark: true,
  colors: {
    background:   '#0d1117',
    surface:      '#161b22',
    'surface-2':  '#21262d',
    primary:      '#58a6ff',
    secondary:    '#3fb950',
    accent:       '#f78166',
    warning:      '#d29922',
    error:        '#f85149',
    info:         '#58a6ff',
    success:      '#3fb950',
    // DMM-specific
    'dmm-display':'#0d2137',
    'dmm-value':  '#00ff88',
  },
}

export default createVuetify({
  theme: {
    defaultTheme: 'dmmTheme',
    themes: { dmmTheme },
  },
  defaults: {
    VBtn: {
      variant: 'tonal',
      rounded: 'lg',
    },
    VCard: {
      rounded: 'lg',
    },
  },
})
