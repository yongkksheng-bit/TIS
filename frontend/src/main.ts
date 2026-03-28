import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import * as Sentry from '@sentry/vue'
import App from './App.vue'
import router from './router'
import './style.css'
import '@/api/mock'

// ── Sentry initialization ─────────────────────────────────────────────────
Sentry.init({
  dsn: (import.meta as any).env.VITE_SENTRY_DSN || '',
  environment: (import.meta as any).env.VITE_SENTRY_ENV || 'development',
  integrations: [
    Sentry.browserTracingIntegration(),
    Sentry.replayIntegration(),
  ],
  tracesSampleRate: 0.1,
  ignoreErrors: [
    'Request failed with status 400',
    'HTTP 400',
  ],
  beforeSend(event) {
    const level = event.level
    if (level === 'warning' || level === 'info' || level === 'debug') {
      return null
    }
    return event
  },
})

const app = createApp(App)

// Register all Element Plus icons
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(createPinia())
app.use(router)
app.use(ElementPlus)

Sentry.setTag('app_name', 'tis-frontend')
app.config.errorHandler = (err, instance, info) => {
  Sentry.captureException(err, { extra: { info } })
}

app.mount('#app')