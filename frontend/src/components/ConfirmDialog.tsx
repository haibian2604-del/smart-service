import { useEffect } from 'react'

/** 应用内确认弹窗：替代 window.confirm。 */
export function ConfirmDialog({ open, title = '确认操作', message, confirmText = '删除',
                                onConfirm, onCancel }: {
  open: boolean
  title?: string
  message: string
  confirmText?: string
  onConfirm: () => void
  onCancel: () => void
}) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onCancel() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onCancel])

  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" role="dialog" aria-modal="true" aria-label={title}
         onClick={onCancel}>
      <div className="mx-4 w-full max-w-sm rounded-2xl bg-white p-5 shadow-xl" onClick={e => e.stopPropagation()}>
        <h2 className="text-base font-medium text-slate-900">{title}</h2>
        <p className="mt-2 text-sm text-slate-600">{message}</p>
        <div className="mt-5 flex justify-end gap-2">
          <button onClick={onCancel}
                  className="rounded-xl px-4 py-2 text-sm text-slate-600 hover:bg-slate-100">取消</button>
          <button onClick={onConfirm} autoFocus
                  className="rounded-xl bg-red-500 px-4 py-2 text-sm font-medium text-white hover:bg-red-600">
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  )
}
