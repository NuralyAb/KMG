import {
  IconArrowsMaximize, IconBadgeCc, IconBook, IconCards, IconChevronDown, IconChevronLeft, IconChevronRight, IconFileText, IconHelpCircle, IconHome, IconList, IconLogout2,
  IconMoon, IconPlayerPauseFilled, IconPlayerPlayFilled, IconStack2, IconSun, IconTopologyStar3, IconVolume, IconVolumeOff, IconX, type Icon,
} from '@tabler/icons-react';

const icon = (Shape: Icon) => function CourseIcon() { return <Shape className="icon" size={24} stroke={1.7} aria-hidden />; };

export const Icons = {
  home: icon(IconHome), cards: icon(IconCards), summary: icon(IconFileText), map: icon(IconTopologyStar3), help: icon(IconHelpCircle), exit: icon(IconLogout2),
  moon: icon(IconMoon), sun: icon(IconSun), list: icon(IconList), layers: icon(IconStack2), down: icon(IconChevronDown), left: icon(IconChevronLeft), right: icon(IconChevronRight),
  book: icon(IconBook), play: icon(IconPlayerPlayFilled), pause: icon(IconPlayerPauseFilled), sound: icon(IconVolume), mute: icon(IconVolumeOff),
  captions: icon(IconBadgeCc), full: icon(IconArrowsMaximize), close: icon(IconX),
};

/** Тот же знак стоит в каталоге (app/LearnerShell.tsx). */
export const Logo = () => (
  <svg className="logo-mark" viewBox="0 0 48 32" width="42" height="28" fill="currentColor" aria-hidden>
    <path d="M24 1 1 11l23 10 23-10z" /><path d="M10 18v6c0 3 6.3 6 14 6s14-3 14-6v-6l-14 6z" opacity=".72" /><path d="M42.5 13.5H45V24h-2.5z" />
  </svg>
);

/** Отметка урока в содержании: открыт сейчас, пройден, ещё впереди. */
export function Mark({ state }: { state: 'now' | 'done' | 'todo' }) {
  const frame = { className: 'mark', viewBox: '0 0 24 24', width: 24, height: 24, 'aria-hidden': true };
  if (state === 'done') return <svg {...frame}><circle className="mark-done" cx="12" cy="12" r="10.5" /><path d="m7.7 12.3 2.9 2.9 5.7-5.9" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>;
  if (state === 'now') return <svg {...frame}><circle cx="12" cy="12" r="10.5" fill="#fff" /><path className="mark-now" d="m10 8.2 6 3.8-6 3.8z" /></svg>;
  return <svg {...frame} fill="none" stroke="currentColor" strokeWidth="1.6"><circle cx="12" cy="12" r="10" /><path d="m10 8.5 5.5 3.5-5.5 3.5z" strokeLinejoin="round" /></svg>;
}
