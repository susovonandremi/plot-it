import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { Toaster } from 'sonner'
import { ClerkProvider } from '@clerk/clerk-react'
import App from './App.jsx'
import './styles/index.css'

const PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY

if (!PUBLISHABLE_KEY) {
  throw new Error("Missing Publishable Key")
}

ReactDOM.createRoot(document.getElementById('root')).render(
     <React.StrictMode>
          <ClerkProvider publishableKey={PUBLISHABLE_KEY}>
               <BrowserRouter>
                    <App />
                    <Toaster richColors position="top-right" />
               </BrowserRouter>
          </ClerkProvider>
     </React.StrictMode>,
)
