import React from 'react';

const PageLoader: React.FC = () => {
  return (
    <div className="flex flex-col items-center justify-center min-h-64 p-8">
      <div className="flex items-center justify-center space-x-2">
        <div className="w-4 h-4 rounded-full bg-primary animate-pulse"></div>
        <div className="w-4 h-4 rounded-full bg-primary animate-pulse" style={{ animationDelay: '0.2s' }}></div>
        <div className="w-4 h-4 rounded-full bg-primary animate-pulse" style={{ animationDelay: '0.4s' }}></div>
      </div>
      <p className="mt-4 text-readout">Loading page...</p>
    </div>
  );
};

export default PageLoader;