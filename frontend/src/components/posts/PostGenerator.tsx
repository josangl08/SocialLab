import React from 'react';
import ContentStudio from '../studio/ContentStudio';

interface PostGeneratorProps {
  onPostGenerated?: () => void;
}

const PostGenerator: React.FC<PostGeneratorProps> = ({ onPostGenerated }) => {
  return <ContentStudio onPostGenerated={onPostGenerated} />;
};

export default PostGenerator;
