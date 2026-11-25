import { IconPhoto } from '@tabler/icons-react';
import { Link } from 'react-router-dom';
import { useIllustrations } from '@/api/queries';
import { EmptyState, QueryView } from '@/ui/states';
import { Picture } from './Picture';

export function PicturesTab({ id }: { id: string }) {
  const query = useIllustrations(id);
  return (
    <QueryView query={query}>
      {(pictures) => pictures.length === 0
        ? <EmptyState icon={<IconPhoto size={32} aria-hidden />} title="Рисунков ещё нет" text="Они появятся после этапа «Рисунки»." />
        : (
          <div className="pictures">
            {pictures.map((picture) => (
              <Picture key={picture.id} picture={picture}
                link={<Link to={`/admin/chapters/${encodeURIComponent(id)}/nodes/${encodeURIComponent(picture.step_id)}`}>К шагу</Link>} />
            ))}
          </div>
        )}
    </QueryView>
  );
}
