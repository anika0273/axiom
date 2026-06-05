import { render, screen } from '@testing-library/react'
import Button from '../components/ui/Button'

describe('Button', () => {
  it('renders without crashing', () => {
    render(<Button>Click me</Button>)
    expect(screen.getByRole('button', { name: /click me/i })).toBeInTheDocument()
  })

  it('renders in loading state', () => {
    render(<Button loading>Saving</Button>)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('renders disabled when disabled prop is set', () => {
    render(<Button disabled>Submit</Button>)
    expect(screen.getByRole('button')).toBeDisabled()
  })
})
