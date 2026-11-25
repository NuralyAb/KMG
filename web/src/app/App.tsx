import { IconMapOff } from '@tabler/icons-react';
import { lazy } from 'react';
import { Link, Route, Routes } from 'react-router-dom';
import { EmptyState } from '@/ui/states';
import { Shell } from './Shell';

const ChaptersPage = lazy(() => import('@/features/chapters/ChaptersPage'));
const ChapterPage = lazy(() => import('@/features/chapter/ChapterPage'));
const NodePage = lazy(() => import('@/features/node/NodePage'));
const ReviewPage = lazy(() => import('@/features/review/ReviewPage'));
const ReviewDetailPage = lazy(() => import('@/features/review/ReviewDetailPage'));
const LibraryPage = lazy(() => import('@/features/library/LibraryPage'));
const SourcePage = lazy(() => import('@/features/library/SourcePage'));
const ModelPage = lazy(() => import('@/features/model/ModelPage'));
const RunsPage = lazy(() => import('@/features/runs/RunsPage'));
const MetricsPage = lazy(() => import('@/features/metrics/MetricsPage'));
const SearchPage = lazy(() => import('@/features/search/SearchPage'));

function NotFound() {
  return <EmptyState icon={<IconMapOff size={32} />} title="Такой страницы нет" action={<Link to="/">К списку глав</Link>} />;
}

export function App() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<ChaptersPage />} />
        <Route path="chapters/:id" element={<ChapterPage />} />
        <Route path="chapters/:id/nodes/:nodeId" element={<NodePage />} />
        <Route path="library" element={<LibraryPage />} />
        <Route path="library/:id" element={<SourcePage />} />
        <Route path="model" element={<ModelPage />} />
        <Route path="review" element={<ReviewPage />} />
        <Route path="review/:packageId" element={<ReviewDetailPage />} />
        <Route path="runs" element={<RunsPage />} />
        <Route path="metrics" element={<MetricsPage />} />
        <Route path="search" element={<SearchPage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
