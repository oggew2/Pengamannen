// Haptic feedback utility for mobile
export const haptic = {
  light: () => navigator.vibrate?.(10),
  medium: () => navigator.vibrate?.(20),
  success: () => navigator.vibrate?.([10, 50, 10]),
  error: () => navigator.vibrate?.([50, 30, 50]),
};

// Undo action manager
type UndoCallback = () => void;

interface UndoState {
  callback: UndoCallback;
  timeout: ReturnType<typeof setTimeout>;
}

const undoStates = new Map<string, UndoState>();

export function registerUndo(id: string, callback: UndoCallback, duration = 5000): void {
  // Clear existing undo for this id
  cancelUndo(id);
  
  const timeout = setTimeout(() => {
    undoStates.delete(id);
  }, duration);
  
  undoStates.set(id, { callback, timeout });
}

export function executeUndo(id: string): boolean {
  const state = undoStates.get(id);
  if (state) {
    clearTimeout(state.timeout);
    state.callback();
    undoStates.delete(id);
    haptic.success();
    return true;
  }
  return false;
}

export function cancelUndo(id: string): void {
  const state = undoStates.get(id);
  if (state) {
    clearTimeout(state.timeout);
    undoStates.delete(id);
  }
}
