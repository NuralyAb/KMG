import { MantineProvider } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, type RenderResult } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { theme } from '@/app/theme';

const FUTURE = { v7_startTransition: true, v7_relativeSplatPath: true };

/** Экран со всеми провайдерами и чистым кэшем. */
export function renderApp(node: ReactNode, path = '/'): RenderResult {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MantineProvider theme={theme} env="test">
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[path]} future={FUTURE}>{node}</MemoryRouter>
      </QueryClientProvider>
    </MantineProvider>,
  );
}
