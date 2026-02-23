import { createRouter, createWebHistory } from 'vue-router'
import HomeView     from '../views/HomeView.vue'
import DmmView      from '../views/DmmView.vue'
import TerminalView from '../views/TerminalView.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/',         component: HomeView     },
    { path: '/dmm',      component: DmmView      },
    { path: '/terminal', component: TerminalView },
  ],
})
