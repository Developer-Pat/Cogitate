import React from 'react';

interface PageContainerProps {
  children: React.ReactNode;
  className?: string;
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl' | '2xl' | '3xl' | '4xl' | '5xl' | '6xl' | '7xl' | 'full';
}

export const PageContainer: React.FC<PageContainerProps> = ({
  children,
  className = '',
  maxWidth = '7xl'
}) => {
  const maxWidthClass = maxWidth === 'full' ? '' : `max-w-${maxWidth} mx-auto`;
  
  return (
    <div className={`p-6 ${maxWidthClass} ${className}`}>
      {children}
    </div>
  );
};

export default PageContainer;