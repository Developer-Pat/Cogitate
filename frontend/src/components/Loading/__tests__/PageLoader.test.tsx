import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import PageLoader from '../PageLoader';

describe('PageLoader', () => {
  it('should render loading animation and text', () => {
    render(<PageLoader />);
    
    // Should render loading dots
    const dots = screen.getAllByRole('generic').filter(el => 
      el.className.includes('animate-pulse') && el.className.includes('bg-primary')
    );
    expect(dots).toHaveLength(3);
    
    // Should render loading text
    expect(screen.getByText('Loading page...')).toBeInTheDocument();
  });

  it('should have proper styling classes', () => {
    const { container } = render(<PageLoader />);
    
    const wrapper = container.firstChild;
    expect(wrapper).toHaveClass('flex', 'flex-col', 'items-center', 'justify-center', 'min-h-64', 'p-8');
    
    const dotsContainer = screen.getByText('Loading page...').previousSibling;
    expect(dotsContainer).toHaveClass('flex', 'items-center', 'justify-center', 'space-x-2');
  });
});