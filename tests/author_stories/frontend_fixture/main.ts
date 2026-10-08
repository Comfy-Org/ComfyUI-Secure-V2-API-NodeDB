import { createPinia, setActivePinia } from 'pinia'
setActivePinia(createPinia())
await import('./story')
