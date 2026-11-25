import type { ReactNode } from 'react';
import { useEffect } from 'react';

const APP = 'Глава → курс';

interface PageHeaderProps { title: ReactNode; docTitle: string; subtitle?: ReactNode; actions?: ReactNode; above?: ReactNode }

export function PageHeader({ title, docTitle, subtitle, actions, above }: PageHeaderProps) {
  useEffect(() => {
    document.title = `${docTitle} · ${APP}`;
  }, [docTitle]);
  return (
    <header className="page-head">
      <div className="page-head-text">
        {above && <div className="page-above">{above}</div>}
        <h1>{title}</h1>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
}
