import React from 'react'
import './index.css'
import { createRoot } from 'react-dom/client'
import NotaOfficeMap from './NotaOfficeSituation'

const el = document.getElementById('deskroom-app')
if (el) {
  const root = createRoot(el)
  root.render(
    <NotaOfficeMap
      colorScheme="red-blue"
      fetchStatus={() => fetch('/api/deskroom/status').then(r=>r.json())}
      fetchReservations={(id) => fetch(`/api/deskroom/${id}/reservations`).then(r=>r.json())}
    />
  )
}
