import { render, screen } from '@testing-library/react'
import Badge from '../components/ui/Badge'

describe('Badge', () => {
  it('renders without crashing', () => {
    render(<Badge variant="running" />)
    expect(screen.getByText('Running')).toBeInTheDocument()
  })

  it('renders with a custom label', () => {
    render(<Badge variant="significant" label="Winner" />)
    expect(screen.getByText('Winner')).toBeInTheDocument()
  })

  it('renders fallback draft variant for unknown variant', () => {
    render(<Badge variant="unknown-variant" />)
    expect(screen.getByText('Draft')).toBeInTheDocument()
  })
})
