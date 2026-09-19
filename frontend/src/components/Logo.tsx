/** 品牌 logo：对话气泡 + 闪电。size 默认 28px。 */
export function Logo({ size = 28 }: { size?: number }) {
  return (
    <img src="/logo.svg" alt="智能客服" width={size} height={size} className="shrink-0" />
  )
}
