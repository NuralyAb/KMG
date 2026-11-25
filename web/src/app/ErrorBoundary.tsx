import { Component, type ReactNode } from 'react';
import { ErrorState } from '@/ui/states';

interface Props { children: ReactNode }
interface State { error: Error | null }

/** Ошибка одного экрана не роняет рамку. Классовый компонент: в React 18 другого способа нет. */
export class ErrorBoundary extends Component<Props, State> {
  override state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  override render(): ReactNode {
    if (this.state.error) return <ErrorState error={this.state.error} onRetry={() => this.setState({ error: null })} />;
    return this.props.children;
  }
}
