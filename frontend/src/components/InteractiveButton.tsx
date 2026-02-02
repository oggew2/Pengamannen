import { motion } from 'framer-motion';
import { forwardRef, ReactNode } from 'react';
import { haptic } from '../utils/interactions';

interface InteractiveButtonProps {
  children: ReactNode;
  onClick?: () => void;
  hapticFeedback?: 'light' | 'medium' | 'success' | 'error' | false;
  className?: string;
  disabled?: boolean;
  style?: React.CSSProperties;
}

export const InteractiveButton = forwardRef<HTMLButtonElement, InteractiveButtonProps>(
  ({ hapticFeedback = 'light', onClick, children, className, disabled, style }, ref) => {
    const handleClick = () => {
      if (disabled) return;
      if (hapticFeedback && haptic[hapticFeedback]) {
        haptic[hapticFeedback]();
      }
      onClick?.();
    };

    return (
      <motion.button
        ref={ref}
        whileHover={disabled ? {} : { scale: 1.02 }}
        whileTap={disabled ? {} : { scale: 0.97 }}
        onClick={handleClick}
        className={className}
        disabled={disabled}
        style={style}
      >
        {children}
      </motion.button>
    );
  }
);

InteractiveButton.displayName = 'InteractiveButton';
