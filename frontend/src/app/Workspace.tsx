import { createContext, useContext, type ReactNode } from 'react';
import type { Dataset, Summary } from '../types/api';
export interface WorkspaceValue {
  dataset: Dataset;
  summary: Summary;
  readOnly: boolean;
  refresh: () => void;
}
const Context = createContext<WorkspaceValue | null>(null);
export function WorkspaceProvider({
  value,
  children,
}: {
  value: WorkspaceValue;
  children: ReactNode;
}) {
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function useWorkspace() {
  const context = useContext(Context);
  if (!context) throw new Error('Workspace missing');
  return context;
}
