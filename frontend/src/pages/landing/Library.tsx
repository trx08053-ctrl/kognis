// Секции лендинга: истории, статьи, частые вопросы.
import { useEffect, useRef, useState } from "react";
import { ArrowIcon, ChevronLeftIcon, ChevronRightIcon, CloseIcon } from "../../Icons";
import { ARTICLES, type Article, FAQ, STORIES } from "./content";
import { Reveal } from "./motion";
import { SectionHead } from "./Sections";

export function Stories() {
  const [index, setIndex] = useState(0);
  const story = STORIES[index] ?? STORIES[0];
  const go = (delta: number) => setIndex((index + delta + STORIES.length) % STORIES.length);
  return (
    <section aria-labelledby="stories-title" id="stories" className="lp-section lp-container">
      <SectionHead
        id="stories-title"
        eyebrow="Истории"
        title="Небольшие шаги — заметные перемены"
        text="Истории-примеры: так Kognis помогает в типичных жизненных ситуациях."
      />
      <Reveal className="lp-story-wrap">
        <div aria-live="polite">
          <article className="lp-story" data-testid="story" key={story.name}>
            <img src={story.photo} alt="" className="lp-story-photo" loading="lazy" />
            <div className="lp-story-body">
              <p className="text-sm muted">Было: {story.before}</p>
              <blockquote className="lp-story-quote">«{story.quote}»</blockquote>
              <p className="font-semibold">
                {story.name} <span className="font-normal muted">· {story.role}</span>
              </p>
              <p className="badge mt-3">{story.result}</p>
              <p className="mt-4 text-xs muted">Вымышленная история-пример, фото — иллюстрация.</p>
            </div>
          </article>
        </div>
        <div className="mt-6 flex items-center justify-center gap-4">
          <button
            type="button"
            className="lp-round"
            aria-label="Предыдущая история"
            onClick={() => go(-1)}
          >
            <ChevronLeftIcon />
          </button>
          <div className="flex gap-2">
            {STORIES.map((s, i) => (
              <button
                key={s.name}
                type="button"
                className="lp-dot"
                aria-label={`История ${i + 1}: ${s.name}`}
                aria-current={i === index}
                onClick={() => setIndex(i)}
              />
            ))}
          </div>
          <button
            type="button"
            className="lp-round"
            aria-label="Следующая история"
            onClick={() => go(1)}
          >
            <ChevronRightIcon />
          </button>
        </div>
      </Reveal>
    </section>
  );
}

export function Articles() {
  const dialog = useRef<HTMLDialogElement>(null);
  const [open, setOpen] = useState<Article | null>(null);
  // модальное окно открывается после отрисовки статьи — фокус попадает на «Закрыть»
  useEffect(() => {
    const node = dialog.current;
    if (open && node && typeof node.showModal === "function" && !node.open) node.showModal();
  }, [open]);
  function show(article: Article) {
    setOpen(article);
  }
  function close() {
    const node = dialog.current;
    if (node && typeof node.close === "function") node.close();
    setOpen(null);
  }
  return (
    <section aria-labelledby="articles-title" id="articles" className="lp-section lp-container">
      <SectionHead
        id="articles-title"
        eyebrow="Статьи"
        title="Читайте о психологии просто"
        text="Короткие материалы о подходах, на которых построен Kognis."
      />
      <ul className="lp-articles">
        {ARTICLES.map((a, i) => (
          <li key={a.id}>
            <Reveal delay={i as 0 | 1 | 2} className="lp-card lp-article h-full">
              <img src={a.image} alt="" loading="lazy" className="lp-article-img" />
              <div className="p-5">
                <p className="text-sm muted">
                  <span className="badge">{a.tag}</span> · {a.minutes} мин чтения
                </p>
                <h3 className="mt-3 text-lg font-semibold">{a.title}</h3>
                <p className="mt-2 muted">{a.lead}</p>
                <button type="button" className="lp-link mt-4" onClick={() => show(a)}>
                  Читать статью <ArrowIcon />
                </button>
              </div>
            </Reveal>
          </li>
        ))}
      </ul>
      <dialog
        ref={dialog}
        className="lp-dialog"
        aria-labelledby="article-title"
        onClose={() => setOpen(null)}
      >
        {open && (
          <article data-testid="article">
            <img src={open.image} alt="" className="lp-dialog-img" />
            <div className="p-6">
              <div className="flex items-start justify-between gap-4">
                <h3 id="article-title" className="text-2xl font-semibold">
                  {open.title}
                </h3>
                <button
                  type="button"
                  className="lp-round"
                  aria-label="Закрыть статью"
                  onClick={close}
                >
                  <CloseIcon />
                </button>
              </div>
              <div className="mt-4 space-y-3">
                {open.body.map((p) => (
                  <p key={p.slice(0, 24)}>{p}</p>
                ))}
              </div>
            </div>
          </article>
        )}
      </dialog>
    </section>
  );
}

export function Faq() {
  return (
    <section aria-labelledby="faq-title" id="faq" className="lp-section lp-container">
      <SectionHead id="faq-title" eyebrow="Вопросы" title="Частые вопросы" />
      <div className="mx-auto max-w-3xl space-y-3">
        {FAQ.map((f) => (
          <details key={f.q} className="lp-faq">
            <summary>{f.q}</summary>
            <p className="mt-3 muted">{f.a}</p>
          </details>
        ))}
      </div>
    </section>
  );
}
