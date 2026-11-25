import { createRoot } from 'react-dom/client';
import { App } from './App';

/** Вход собранного курса: данные уже лежат в window.COURSE (data.js), сервера и сети нет. */
const root = document.getElementById('app');
if (root) {
  if (window.COURSE?.steps.length) createRoot(root).render(<App course={window.COURSE} />);
  else root.textContent = 'Курс не загрузился: рядом с index.html должны лежать data.js и папка assets.';
}
