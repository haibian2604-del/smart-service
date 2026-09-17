import { beforeEach, describe, expect, it } from 'vitest'
import { loadActor, saveActor, clearActor, DEMO_ACTORS } from './actor'

beforeEach(() => { localStorage.clear(); clearActor() })

describe('actor store', () => {
  it('exposes exactly two demo identities: one customer, two merchants', () => {
    expect(DEMO_ACTORS.filter(a => a.role === 'user')).toHaveLength(1)
    expect(DEMO_ACTORS.filter(a => a.role === 'merchant')).toHaveLength(2)
  })

  it('returns null when nothing stored', () => {
    expect(loadActor()).toBeNull()
  })

  it('round-trips the selected actor', () => {
    saveActor(DEMO_ACTORS[1])
    expect(loadActor()).toEqual(DEMO_ACTORS[1])
  })

  it('discards corrupted storage', () => {
    localStorage.setItem('smart-service.actor', '{not json')
    expect(loadActor()).toBeNull()
  })

  it('discards unknown actor ids', () => {
    localStorage.setItem('smart-service.actor', JSON.stringify({ id: 999, role: 'user' }))
    expect(loadActor()).toBeNull()
  })
})
