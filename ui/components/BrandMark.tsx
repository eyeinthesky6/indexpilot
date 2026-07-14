type BrandMarkProps = {
  className?: string;
  decorative?: boolean;
};

export function BrandMark({ className = "h-10 w-10", decorative = true }: BrandMarkProps) {
  return (
    <svg
      viewBox="0 0 96 96"
      className={className}
      aria-hidden={decorative ? true : undefined}
      role={decorative ? undefined : "img"}
      aria-label={decorative ? undefined : "IndexPilot Evidence Gate"}
    >
      <rect width="96" height="96" rx="22" fill="#0b1728" />
      <path
        fill="#f7f5ee"
        d="M19 17h29v13H33v36h15v13H19V17Zm58 0H48v13h15v36H48v13h29V17Z"
      />
      <path fill="#b8f34a" d="M37 39h20l7 7v13H37V39Z" />
    </svg>
  );
}
