import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
// Fonts and KaTeX's stylesheet are self-hosted npm packages, never CDN links:
// the privacy policy states this app loads no third-party scripts and lists every
// processor it shares data with, and a font CDN would quietly add one.
import '@fontsource-variable/jetbrains-mono'
import '@fontsource-variable/jetbrains-mono/wght-italic.css'
import '@fontsource-variable/ibm-plex-sans'
import 'katex/dist/katex.min.css'
import './styles/index.css'
import App from './App'
import { AuthProvider } from './auth'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
