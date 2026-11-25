import '@fontsource-variable/ibm-plex-sans';
import '@fontsource-variable/onest';
import '@mantine/core/styles.css';
import '@mantine/notifications/styles.css';
import './app/tokens.css';
import './app/styles.css';

import { MantineProvider } from '@mantine/core';
import { Notifications } from '@mantine/notifications';
import { QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { ApiError } from './api/client';
import { App } from './app/App';
import { theme } from './app/theme';

const STALE_MS = 15_000;

// сеанс автора кончился: экран переспросит, кто пришёл, и покажет вход
const onExpired = (error: unknown): void => {
  if (error instanceof ApiError && error.status === 401) void queryClient.invalidateQueries({ queryKey: ['me'] });
};

const queryClient: QueryClient = new QueryClient({
  queryCache: new QueryCache({ onError: onExpired }),
  defaultOptions: { queries: { retry: 1, staleTime: STALE_MS, refetchOnWindowFocus: true } },
});

async function start(): Promise<void> {
  // данные-заглушки подключаются только в разработке и в сборку не попадают
  if (import.meta.env.DEV && import.meta.env.VITE_MOCK === '1') {
    const { worker } = await import('./mocks/browser');
    await worker.start({ onUnhandledRequest: 'bypass', quiet: true });
  }
  const root = document.getElementById('root');
  if (!root) throw new Error('В index.html нет элемента #root');
  ReactDOM.createRoot(root).render(
    <React.StrictMode>
      <MantineProvider theme={theme} defaultColorScheme="auto">
        <QueryClientProvider client={queryClient}>
          <Notifications position="top-right" limit={3} />
          <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
            <App />
          </BrowserRouter>
        </QueryClientProvider>
      </MantineProvider>
    </React.StrictMode>,
  );
}

void start();
