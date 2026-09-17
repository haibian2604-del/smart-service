import type { Actor } from '../types'

export type { Actor }

export const DEMO_ACTORS: Actor[] = [
  { id: 1, role: 'user', name: '演示用户', merchantId: null },
  { id: 2, role: 'merchant', name: '青柠数码', merchantId: 1 },
  { id: 3, role: 'merchant', name: '山野户外', merchantId: 2 },
]

const KEY = 'smart-service.actor'

export function loadActor(): Actor | null {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return null
    const a = JSON.parse(raw) as Actor
    return DEMO_ACTORS.some(d => d.id === a.id && d.role === a.role) ? a : null
  } catch {
    return null
  }
}

export function saveActor(a: Actor) {
  localStorage.setItem(KEY, JSON.stringify(a))
}

export function clearActor() {
  localStorage.removeItem(KEY)
}
