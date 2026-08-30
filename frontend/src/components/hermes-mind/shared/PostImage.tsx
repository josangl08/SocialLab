import React, { useEffect, useState } from 'react';

interface PostImageProps {
  src: string | null;
  /** shown while loading fails or there is no src (e.g. Drive not connected) */
  fallback: React.ReactNode;
}

/**
 * A post's image with a graceful fallback: if the src is missing or fails to
 * load (draft with no media_url and Drive not reachable), the icon shows instead
 * of a broken-image glyph.
 */
export const PostImage: React.FC<PostImageProps> = ({ src, fallback }) => {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [src]);

  if (!src || failed) return <>{fallback}</>;
  return (
    <img
      src={src}
      alt="Vista previa de la publicación"
      loading="lazy"
      onError={() => setFailed(true)}
    />
  );
};
