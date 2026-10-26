import { ArrowRight, Star } from "lucide-react";
import type { LucideIcon } from "lucide-react";

export function ModuleTile({
  title,
  icon: Glyph,
  featured,
  disabled,
  note,
  favorite,
  onOpen,
  onFavorite,
}: {
  title: string;
  icon: LucideIcon;
  featured?: boolean;
  disabled?: boolean;
  note?: string;
  favorite: boolean;
  onOpen: () => void;
  onFavorite: () => void;
}) {
  return (
    <article className={`module-card${featured ? " featured" : ""}${disabled ? " denied" : ""}`}>
      <button className="module-open" type="button" disabled={disabled} aria-label={title} onClick={onOpen}>
        <span className="module-icon">
          <Glyph size={22} strokeWidth={2} />
        </span>
        <span>
          <strong>{title}</strong>
          {note ? <em>{note}</em> : null}
        </span>
        <ArrowRight size={16} />
      </button>
      <button className={favorite ? "star on" : "star"} type="button" aria-label={`Favorite ${title}`} onClick={onFavorite}>
        <Star size={14} />
      </button>
    </article>
  );
}
