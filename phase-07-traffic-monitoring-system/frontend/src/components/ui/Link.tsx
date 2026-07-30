import type { AnchorHTMLAttributes, MouseEvent } from "react";
import { navigate } from "../../app/router";

type LinkProps = Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> & { to: string };

export function Link({ to, onClick, target, ...props }: LinkProps) {
  const handleClick = (event: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(event);
    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey ||
      (target && target !== "_self")
    ) return;

    event.preventDefault();
    navigate(to);
  };

  return <a {...props} href={to} target={target} onClick={handleClick} />;
}
