import { BrowserRouter } from 'react-router-dom'
import { AppRoutes } from './router'
import { loadActor } from './lib/actor'

export default function App() {
  const actor = loadActor()
  return (
    <BrowserRouter>
      <AppRoutes actor={actor} />
    </BrowserRouter>
  )
}
