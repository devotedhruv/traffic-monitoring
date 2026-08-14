import { BRAND_ASSETS, PRODUCT_NAME } from "../../lib/brand";
import { cx } from "../../lib/format";

interface BrandLogoProps {
  variant?: "logo" | "mark";
  className?: string;
  decorative?: boolean;
}

export function BrandLogo({ variant = "mark", className, decorative = false }: BrandLogoProps) {
  return (
    <img
      src={BRAND_ASSETS[variant]}
      alt={decorative ? "" : `${PRODUCT_NAME} logo`}
      className={cx("block object-contain", className)}
      draggable={false}
    />
  );
}
