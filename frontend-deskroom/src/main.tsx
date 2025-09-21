import React from 'react'
import './index.css'
import { createRoot } from 'react-dom/client'
import NotaOfficeSituation from './NotaOfficeSituation'

const el = document.getElementById('nota-office-app')
if (el) {
  const root = createRoot(el)
  root.render(
    <NotaOfficeSituation />
  )
}
