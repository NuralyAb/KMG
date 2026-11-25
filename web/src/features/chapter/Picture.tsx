import { IconPhotoOff } from '@tabler/icons-react';
import { useState, type ReactNode } from 'react';
import { courseHref } from '@/api/client';
import type { Illustration } from '@/api/types';
import { FRAME_CLASS, ORIGIN, label } from '@/lib/labels';
import { RichText } from '@/ui/RichText';
import './chapter.css';

/** Рисунок курса. SVG грузится через <img>, поэтому скрипты внутри него не выполняются. */
export function Picture({ picture, link }: { picture: Illustration; link?: ReactNode }) {
  const [isBroken, setBroken] = useState(false);
  const src = courseHref(picture.url);
  return (
    <figure className="picture">
      {src && !isBroken
        ? <a href={src} target="_blank" rel="noopener noreferrer" title="Открыть рисунок целиком"><img src={src} alt={picture.alt} loading="lazy" onError={() => setBroken(true)} /></a>
        : <div className="picture-lost"><IconPhotoOff size={24} aria-hidden /><span>Файл не открылся: {picture.file}</span></div>}
      <figcaption>
        <RichText text={picture.caption} />
        <span className="picture-meta muted">
          <span>{picture.label ?? 'без метки'}</span>
          <span>класс {label(FRAME_CLASS, picture.frame_class)}</span>
          <span>{label(ORIGIN, picture.origin)}</span>
          {link}
        </span>
      </figcaption>
    </figure>
  );
}
