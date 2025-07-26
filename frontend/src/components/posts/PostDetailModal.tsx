import React from 'react';
import { Modal, Button } from 'react-bootstrap';

interface Post {
  id: number;
  user_id: string;
  content: string;
  media_url: string | null;
  post_type: string;
  status: string;
  scheduled_at: string | null;
  created_at: string;
}

interface PostDetailModalProps {
  show: boolean;
  onHide: () => void;
  post: Post | null;
}

const PostDetailModal: React.FC<PostDetailModalProps> = ({ show, onHide, post }) => {
  if (!post) {
    return null; // No renderizar si no hay publicación
  }

  return (
    <Modal show={show} onHide={onHide} size="md" centered>
      <Modal.Header closeButton>
        <Modal.Title>Detalles de la Publicación</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <h6>Contenido:</h6>
        <p style={{ fontSize: '0.9em' }}>{post.content}</p>

        {post.media_url && (
          <div className="mb-3 text-center">
            <h6>Medio:</h6>
            {post.media_url.match(/\.(jpeg|jpg|gif|png|webp|svg)(\?.*)?$/i) ? (
              <img src={post.media_url} alt="Publicación" className="img-fluid rounded" style={{ maxHeight: '150px' }} />
            ) : post.media_url.match(/\.(mp4|webm|ogg)(\?.*)?$/i) ? (
              <video src={post.media_url} controls className="img-fluid rounded" style={{ maxHeight: '150px' }} />
            ) : (
              <p className="text-warning" style={{ fontSize: '0.85em' }}>Formato de medio no soportado para previsualización. <a href={post.media_url} target="_blank" rel="noopener noreferrer">Ver</a></p>
            )}
          </div>
        )}

        <p style={{ fontSize: '0.85em' }}><strong>Tipo:</strong> {post.post_type}</p>
        <p style={{ fontSize: '0.85em' }}><strong>Estado:</strong> {post.status}</p>
        <p style={{ fontSize: '0.85em' }}><strong>Creado:</strong> {new Date(post.created_at).toLocaleString()}</p>
        {post.scheduled_at && <p style={{ fontSize: '0.85em' }}><strong>Programado:</strong> {new Date(post.scheduled_at).toLocaleString()}</p>}
      </Modal.Body>
      <Modal.Footer>
        <Button variant="secondary" onClick={onHide}>
          Cerrar
        </Button>
      </Modal.Footer>
    </Modal>
  );
};

export default PostDetailModal;
