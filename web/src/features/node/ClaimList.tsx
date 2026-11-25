import { IconAlertTriangle } from '@tabler/icons-react';
import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { CLAIM_KIND, SOURCE_KIND, label } from '@/lib/labels';
import { Chip } from '@/ui/bits';
import { RichText } from '@/ui/RichText';
import { EmptyState } from '@/ui/states';
import type { Claim } from './model';

/** Утверждение и его цитата стоят рядом: проверка читается слева направо. */
export function ClaimList({ claims }: { claims: Claim[] }) {
  const { hash } = useLocation();
  const active = hash.slice(1);
  const found = useRef<HTMLLIElement>(null);
  // из поиска приходят по якорю: утверждение показывается, когда шаг уже загружен
  useEffect(() => {
    found.current?.scrollIntoView({ block: 'center' });
  }, [active]);
  if (claims.length === 0) return <EmptyState title="У шага нет утверждений" />;
  return (
    <ol className="claims">
      {claims.map((claim) => {
        const short = claim.id.split('#').pop() ?? claim.id;
        return (
          <li key={claim.id} id={short} ref={short === active ? found : undefined} data-active={short === active || undefined}>
            <div className="claim-text">
              <p><RichText text={claim.text} /></p>
              <p className="claim-meta muted">
                <span>{short}</span><span>{label(CLAIM_KIND, claim.kind)}</span>
                {!claim.byModel && <span>слова автора</span>}
              </p>
              {claim.needsScan && <p><Chip tone="warn" icon={<IconAlertTriangle aria-hidden />}>сверить со сканом</Chip></p>}
            </div>
            <blockquote className="claim-quote">
              <p><RichText text={claim.quote} /></p>
              <footer className="muted">
                {claim.page !== null ? `стр. ${claim.page}` : 'страница не указана'}
                {claim.pagePrint !== null && ` (в книге ${claim.pagePrint})`}, {label(SOURCE_KIND, claim.sourceKind)}
              </footer>
            </blockquote>
          </li>
        );
      })}
    </ol>
  );
}
