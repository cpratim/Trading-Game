import { io } from 'socket.io-client'

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || null

let traderId = localStorage.getItem('trader_id')
if (!traderId) {
  traderId = crypto.randomUUID()
  localStorage.setItem('trader_id', traderId)
}

export const socket = io(BACKEND_URL ?? undefined, {
  autoConnect: true,
  query: { trader_id: traderId },
  extraHeaders: { 'ngrok-skip-browser-warning': '1' },
})
