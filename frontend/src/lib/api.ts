import type { Actor } from '../types'
import { loadActor } from './actor'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const actor: Actor | null = loadActor()
  if (!actor) throw new ApiError(401, '未选择身份，请返回首页选择')
  const headers = new Headers(init.headers)
  headers.set('X-Actor-Id', String(actor.id))
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')

  const resp = await fetch(path, { ...init, headers })
  if (!resp.ok) {
    throw new ApiError(resp.status, `${init.method ?? 'GET'} ${path} -> ${resp.status}`)
  }
  return resp.json() as Promise<T>
}
