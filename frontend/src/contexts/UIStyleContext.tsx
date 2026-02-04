import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

type UIStyle = 'classic' | 'modern';

interface UIStyleContextType {
  style: UIStyle;
  setStyle: (style: UIStyle) => void;
  isModern: boolean;
}

const UIStyleContext = createContext<UIStyleContextType | null>(null);

const STORAGE_KEY = 'borslabbet_ui_style';

export function UIStyleProvider({ children }: { children: ReactNode }) {
  const [style, setStyleState] = useState<UIStyle>(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    return (saved === 'classic' || saved === 'modern') ? saved : 'modern';
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, style);
    // Apply class to root for CSS targeting
    document.documentElement.setAttribute('data-ui-style', style);
  }, [style]);

  const setStyle = (newStyle: UIStyle) => setStyleState(newStyle);

  return (
    <UIStyleContext.Provider value={{ style, setStyle, isModern: style === 'modern' }}>
      {children}
    </UIStyleContext.Provider>
  );
}

export function useUIStyle() {
  const context = useContext(UIStyleContext);
  if (!context) {
    return { style: 'modern' as UIStyle, setStyle: () => {}, isModern: true };
  }
  return context;
}
