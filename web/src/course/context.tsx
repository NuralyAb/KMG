import { createContext, useContext, type ReactNode } from 'react';
import { makeRich, numbering, type Rich, type State } from './core';
import type { Store } from './store';
import type { Course, Part, Step } from './types';

/** Всё, что нужно страницам курса: данные, прогресс, номера уроков и текст с формулами. */
export interface CourseContext { course: Course; store: Store; state: State; num: (s: Step) => string; rich: Rich; catalog: string }

const Context = createContext<CourseContext | null>(null);
export const CourseProvider = ({ value, children }: { value: CourseContext; children: ReactNode }) => <Context.Provider value={value}>{children}</Context.Provider>;

export function useCourse(): CourseContext {
  const value = useContext(Context);
  if (!value) throw new Error('Нет данных курса');
  return value;
}

export function courseTools(course: Course): Pick<CourseContext, 'course' | 'num' | 'rich'> {
  const nums = numbering(course.parts, course.steps);
  return { course, num: (s) => nums.get(s.id) ?? String(s.order), rich: makeRich(window.katex) };
}

export const lessonsOf = (course: Course, part: Part): Step[] => part.nodes.flatMap((id) => course.steps.find((s) => s.id === id) ?? []);
export const stepUrl = (s: Step, section = ''): string => `#/step/${s.order}${section ? `/${section}` : ''}`;
export const isDone = (state: State, s: Step): boolean => state.done.includes(s.id);
