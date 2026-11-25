import { useEffect, useRef, useState } from 'react';
import { Rich } from './bits';
import { Icons } from './icons';
import type { Picture } from './types';

/** Схема во весь экран; смена урока кнопкой «назад» закрывает и её: урок размонтируется вместе с окном. */
function Zoom({ picture, onClose }: { picture: Picture; onClose: () => void }) {
  const box = useRef<HTMLDialogElement>(null);
  useEffect(() => { box.current?.showModal(); }, []);
  return (
    <dialog ref={box} className="zoom" aria-label="Схема во весь экран" onClose={onClose} onClick={() => box.current?.close()}>
      <img src={picture.file} alt={picture.alt} />
      <button type="button" className="ctl corner" aria-label="Закрыть"><Icons.close /></button>
    </dialog>
  );
}

/** Схема внутри текста: в свой размер, подпись рядом. */
export function PictureFigure({ picture }: { picture: Picture }) {
  const [isZoomed, setZoomed] = useState(false);
  return (
    <figure className="pic">
      <button type="button" className="pic-open" data-stage="zoom" aria-label={`Открыть схему во весь экран: ${picture.caption}`} onClick={() => setZoomed(true)}>
        <img src={picture.file} alt={picture.alt} width={picture.width} height={picture.height} loading="lazy" />
        <span className="pic-zoom" aria-hidden><Icons.full /></span>
      </button>
      <figcaption><span className="chip">{picture.label}</span><span className="pic-text"><Rich text={picture.caption} /></span>{picture.source && <span className="muted">{picture.source}</span>}</figcaption>
      {isZoomed && <Zoom picture={picture} onClose={() => setZoomed(false)} />}
    </figure>
  );
}
