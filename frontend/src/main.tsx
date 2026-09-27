import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import './food-motion.css'
import '@fontsource-variable/inter'
import '@fontsource-variable/inter-tight'
import './cooking-voice.css'
import './ui-polish.css'
import './brand.css'
import './refresh.css'
import { installBananaCursor } from './bananaCursor'

installBananaCursor()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
