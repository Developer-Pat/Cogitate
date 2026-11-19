import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import SkeletonLoader from '../SkeletonLoader';

describe('SkeletonLoader', () => {
  it('should render card skeleton by default', () => {
    const { container } = render(<SkeletonLoader />);
    
    // Should render card skeleton structure
    const cardElement = container.querySelector('.card.animate-pulse');
    expect(cardElement).toBeInTheDocument();
  });

  it('should render multiple skeletons when count is specified', () => {
    const { container } = render(<SkeletonLoader count={3} />);
    
    const skeletons = container.querySelectorAll('.animate-pulse');
    expect(skeletons.length).toBe(3);
  });

  it('should render table skeleton type', () => {
    const { container } = render(<SkeletonLoader type="table" />);
    
    // Should render table structure
    const tableElement = container.querySelector('table');
    expect(tableElement).toBeInTheDocument();
    
    const rows = container.querySelectorAll('tr');
    expect(rows.length).toBe(6); // header + 5 rows
  });

  it('should render stat skeleton type', () => {
    const { container } = render(<SkeletonLoader type="stat" />);
    
    // Should render stat structure
    const statElement = container.querySelector('.stat');
    expect(statElement).toBeInTheDocument();
  });

  it('should render text skeleton type', () => {
    const { container } = render(<SkeletonLoader type="text" />);
    
    // Should render text placeholder structure
    const textElements = container.querySelectorAll('.bg-base-300.rounded');
    expect(textElements.length).toBe(4); // 4 text lines
  });

  it('should apply custom className', () => {
    const { container } = render(<SkeletonLoader className="custom-class" />);
    
    const wrapper = container.firstChild;
    expect(wrapper).toHaveClass('custom-class');
  });

  it('should render different skeleton types with multiple counts', () => {
    const { container } = render(<SkeletonLoader type="card" count={2} />);
    
    const cards = container.querySelectorAll('.card');
    expect(cards).toHaveLength(2);
    
    const animatedElements = container.querySelectorAll('.animate-pulse');
    expect(animatedElements.length).toBe(2);
  });
});