import { motion } from 'framer-motion';
import { ReactNode } from 'react';

// Spring easing for Revolut-style bounce
const springEase = [0.34, 1.56, 0.64, 1] as const;

// Page transition wrapper - wrap each page component
const pageVariants = {
  initial: { opacity: 0, y: 8 },
  animate: { 
    opacity: 1, 
    y: 0,
    transition: { duration: 0.3, ease: springEase }
  },
  exit: { 
    opacity: 0, 
    y: -8,
    transition: { duration: 0.2, ease: 'easeIn' as const }
  }
};

export function PageTransition({ children }: { children: ReactNode }) {
  return (
    <motion.div
      initial="initial"
      animate="animate"
      exit="exit"
      variants={pageVariants}
    >
      {children}
    </motion.div>
  );
}

// Staggered container - wrap lists of items
const staggerVariants = {
  initial: {},
  animate: {
    transition: { staggerChildren: 0.05, delayChildren: 0.1 }
  }
};

const staggerItemVariants = {
  initial: { opacity: 0, y: 12 },
  animate: { 
    opacity: 1, 
    y: 0,
    transition: { duration: 0.3, ease: springEase }
  }
};

export function StaggerContainer({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <motion.div
      initial="initial"
      animate="animate"
      variants={staggerVariants}
      className={className}
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <motion.div variants={staggerItemVariants} className={className}>
      {children}
    </motion.div>
  );
}

// Scale-in for modals and cards
const scaleVariants = {
  initial: { opacity: 0, scale: 0.95 },
  animate: { 
    opacity: 1, 
    scale: 1,
    transition: { duration: 0.25, ease: springEase }
  },
  exit: { 
    opacity: 0, 
    scale: 0.95,
    transition: { duration: 0.15 }
  }
};

export function ScaleIn({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <motion.div
      initial="initial"
      animate="animate"
      exit="exit"
      variants={scaleVariants}
      className={className}
    >
      {children}
    </motion.div>
  );
}

// Slide-in from right (for banners, notifications)
const slideVariants = {
  initial: { opacity: 0, x: 20 },
  animate: { 
    opacity: 1, 
    x: 0,
    transition: { duration: 0.35, ease: springEase }
  },
  exit: { 
    opacity: 0, 
    x: 20,
    transition: { duration: 0.2 }
  }
};

export function SlideIn({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <motion.div
      initial="initial"
      animate="animate"
      exit="exit"
      variants={slideVariants}
      className={className}
    >
      {children}
    </motion.div>
  );
}

// Hover lift effect for interactive cards
export function HoverLift({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <motion.div
      whileHover={{ y: -2, transition: { duration: 0.15 } }}
      whileTap={{ scale: 0.98 }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

// Pulse animation for loading states
export function Pulse({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <motion.div
      animate={{ opacity: [1, 0.5, 1] }}
      transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
