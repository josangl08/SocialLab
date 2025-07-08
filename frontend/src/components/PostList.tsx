import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import EditPostForm from './EditPostForm';
import './PostList.css';

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

interface PostListProps {
  refresh?: boolean; // Prop para forzar la recarga
}

const PostList: React.FC<PostListProps> = ({ refresh }) => {
  const { token } = useAuth();
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [deleteMessage, setDeleteMessage] = useState<string | null>(null);
  const [editingPost, setEditingPost] = useState<Post | null>(null); // Estado para la publicación en edición

  const fetchPosts = async () => {
    console.log('PostList: Iniciando fetchPosts...');
    if (!token) {
      console.log('PostList: Token no presente, no se hará la petición.');
      setError('No hay token de autenticación disponible.');
      setLoading(false);
      return;
    }

    console.log('PostList: Token presente, intentando hacer la petición GET a /posts...');
    try {
      const response = await fetch('http://localhost:8000/posts', {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      console.log('PostList: Petición fetch completada. Estado de la respuesta:', response.status);

      if (response.ok) {
        const data: Post[] = await response.json();
        console.log('PostList: Datos recibidos:', data);
        setPosts(data);
      } else {
        const errorData = await response.json();
        console.error('PostList: Error en la respuesta del servidor:', errorData);
        setError('Error al cargar publicaciones: ' + (errorData.detail || 'Error desconocido'));
      }
    } catch (err) {
      console.error('PostList: Error de red o servidor en fetch:', err);
      setError('Error de red o servidor: ' + err.message);
    } finally {
      setLoading(false);
      console.log('PostList: fetchPosts finalizado.');
    }
  };

  useEffect(() => {
    console.log('PostList: useEffect se ha ejecutado.');
    console.log('PostList: Token actual:', token);
    fetchPosts();
  }, [token, refresh]); // Añadir 'refresh' a las dependencias del useEffect

  const handleDelete = async (postId: number) => {
    if (!window.confirm('¿Estás seguro de que quieres eliminar esta publicación?')) {
      return;
    }

    setDeleteMessage(null);
    try {
      const response = await fetch(`http://localhost:8000/posts/${postId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        setDeleteMessage('Publicación eliminada exitosamente.');
        fetchPosts(); // Refrescar la lista de publicaciones
      } else {
        const errorData = await response.json();
        setDeleteMessage('Error al eliminar publicación: ' + (errorData.detail || 'Error desconocido'));
      }
    } catch (err) {
      setDeleteMessage('Error de red o servidor: ' + err.message);
      console.error('Error de red o servidor:', err);
    }
  };

  const handleEditClick = (post: Post) => {
    setEditingPost(post);
  };

  const handleEditSave = () => {
    setEditingPost(null); // Salir del modo edición
    fetchPosts(); // Refrescar la lista de publicaciones
  };

  const handleEditCancel = () => {
    setEditingPost(null); // Salir del modo edición
  };

  if (loading) {
    return <p className="text-center text-primary">Cargando publicaciones...</p>;
  }

  if (error) {
    return <p className="text-danger">{error}</p>;
  }

  return (
    <div className="mt-4 post-list-container">
      <h3 className="mb-4 text-dark">Mis Publicaciones</h3>
      {deleteMessage && <p className={`mb-3 ${deleteMessage.startsWith('Error') ? 'text-danger' : 'text-success'}`}>{deleteMessage}</p>}

      {editingPost ? (
        <EditPostForm post={editingPost} onSave={handleEditSave} onCancel={handleEditCancel} />
      ) : (
        posts.length === 0 ? (
          <p>No tienes publicaciones aún.</p>
        ) : (
          <div className="row row-cols-1 g-3">
            {posts.map((post) => (
              <div key={post.id} className="col">
                <div className="card shadow-sm post-card">
                  <div className="card-body">
                    <h5 className="card-title text-dark">Contenido:</h5>
                    <p className="card-text text-secondary">{post.content}</p>
                    {post.media_url && (
                      <div className="mb-2">
                        <strong className="text-dark">Medio:</strong> <a href={post.media_url} target="_blank" rel="noopener noreferrer" className="text-primary">Ver</a>
                      </div>
                    )}
                    <p className="card-text"><strong className="text-dark">Tipo:</strong> {post.post_type}</p>
                    <p className="card-text"><strong className="text-dark">Estado:</strong> {post.status}</p>
                    <p className="card-text"><strong className="text-dark">Creado:</strong> {new Date(post.created_at).toLocaleString()}</p>
                    {post.scheduled_at && <p className="card-text"><strong className="text-dark">Programado:</strong> {new Date(post.scheduled_at).toLocaleString()}</p>}
                    <div className="d-flex justify-content-end mt-3">
                      <button
                        onClick={() => handleEditClick(post)}
                        className="btn btn-primary btn-sm me-2"
                      >
                        Editar
                      </button>
                      <button
                        onClick={() => handleDelete(post.id)}
                        className="btn btn-danger btn-sm"
                      >
                        Eliminar
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )
      )}
    </div>
  );
};

export default PostList;
