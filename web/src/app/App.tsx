import { IconMapOff } from '@tabler/icons-react';
import { lazy } from 'react';
import { Link, Route, Routes } from 'react-router-dom';
import { EmptyState } from '@/ui/states';
import { AdminGate } from './AdminGate';
import { LearnerShell } from './LearnerShell';
import { Shell } from './Shell';

const ChaptersPage = lazy(() => import('@/features/chapters/ChaptersPage'));
const BooksPage = lazy(() => import('@/features/books/BooksPage'));
const ChapterPage = lazy(() => import('@/features/chapter/ChapterPage'));
const NodePage = lazy(() => import('@/features/node/NodePage'));
const CoursePreviewPage = lazy(() => import('@/features/simulation/CoursePreviewPage'));
const ReviewPage = lazy(() => import('@/features/review/ReviewPage'));
const ReviewDetailPage = lazy(() => import('@/features/review/ReviewDetailPage'));
const CatalogPage = lazy(() => import('@/features/learn/CatalogPage'));
const CoursePage = lazy(() => import('@/features/learn/CoursePage'));
const LoginPage = lazy(() => import('@/features/learn/LoginPage'));
const LibraryPage = lazy(() => import('@/features/library/LibraryPage'));
const SourcePage = lazy(() => import('@/features/library/SourcePage'));
const ModelPage = lazy(() => import('@/features/model/ModelPage'));
const RunsPage = lazy(() => import('@/features/runs/RunsPage'));
const MetricsPage = lazy(() => import('@/features/metrics/MetricsPage'));
const SearchPage = lazy(() => import('@/features/search/SearchPage'));

function NotFound({ home }: { home: string }) {
  return <EmptyState icon={<IconMapOff size={32} />} title="Такой страницы нет" action={<Link to={home}>На главную</Link>} />;
}

/** Две области: ученик на «/», автор на «/admin». Доступ к данным автора закрывает сервер, а не меню. */
export function App() {
  return (
    <Routes>
      <Route element={<LearnerShell />}>
        <Route index element={<CatalogPage />} />
        <Route path="courses/:id" element={<CoursePage />} />
        <Route path="login" element={<LoginPage />} />
        <Route path="*" element={<NotFound home="/" />} />
      </Route>
      <Route path="admin" element={<AdminGate><Shell /></AdminGate>}>
        <Route index element={<ChaptersPage />} />
        <Route path="books" element={<BooksPage />} />
        <Route path="chapters/:id" element={<ChapterPage />} />
        <Route path="chapters/:id/preview" element={<CoursePreviewPage />} />
        <Route path="chapters/:id/nodes/:nodeId" element={<NodePage />} />
        <Route path="library" element={<LibraryPage />} />
        <Route path="library/:id" element={<SourcePage />} />
        <Route path="model" element={<ModelPage />} />
        <Route path="review" element={<ReviewPage />} />
        <Route path="review/:packageId" element={<ReviewDetailPage />} />
        <Route path="runs" element={<RunsPage />} />
        <Route path="metrics" element={<MetricsPage />} />
        <Route path="search" element={<SearchPage />} />
        <Route path="*" element={<NotFound home="/admin" />} />
      </Route>
    </Routes>
  );
}
