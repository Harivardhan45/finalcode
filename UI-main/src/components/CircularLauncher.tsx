import React, { useState, useRef, useEffect } from 'react';

interface CircularLauncherProps {
  onClick: () => void;
}

const CircularLauncher: React.FC<CircularLauncherProps> = ({ onClick }) => {
  // Initialize position at top right
  const [position, setPosition] = useState({ x: window.innerWidth - 100, y: 20 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragged, setDragged] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const buttonRef = useRef<HTMLButtonElement>(null);

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    setDragged(false);
    setDragStart({
      x: e.clientX - position.x,
      y: e.clientY - position.y
    });
  };

  const handleMouseMove = (e: MouseEvent) => {
    if (isDragging) {
      setDragged(true);
      const newX = e.clientX - dragStart.x;
      const newY = e.clientY - dragStart.y;
      
      // Keep button within viewport bounds
      const maxX = window.innerWidth - 80;
      const maxY = window.innerHeight - 80;
      
      setPosition({
        x: Math.max(0, Math.min(newX, maxX)),
        y: Math.max(0, Math.min(newY, maxY))
      });
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleClick = (e: React.MouseEvent) => {
    if (!isDragging && !dragged) {
      onClick();
    }
  };

  useEffect(() => {
    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      
      return () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [isDragging, dragStart]);

  // Update position on window resize to keep it in bounds
  useEffect(() => {
    const handleResize = () => {
      const maxX = window.innerWidth - 80;
      const maxY = window.innerHeight - 80;
      
      setPosition(prev => ({
        x: Math.min(prev.x, maxX),
        y: Math.min(prev.y, maxY)
      }));
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return (
    <button
      ref={buttonRef}
      onMouseDown={handleMouseDown}
      onClick={handleClick}
      className="fixed w-20 h-20 bg-confluence-blue text-white rounded-full cursor-move z-50 flex items-center justify-center font-bold text-sm border-2 border-white/30 transition-all duration-300"
      style={{
        left: `${position.x}px`,
        top: `${position.y}px`,
        background: '#2684ff', // solid confluence blue
      }}
    >
      <span className="text-white font-extrabold tracking-tight">C.AIA</span>
    </button>
  );
};

export default CircularLauncher; 