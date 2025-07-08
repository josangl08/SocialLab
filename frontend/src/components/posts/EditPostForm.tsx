import React, { useState, FormEvent, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext'; // Ruta corregida
import './EditPostForm.css';

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

interface EditPostFormProps {
  post: Post;
  onSave: () => void; // Callback para cuando se guarda la publicación
  onCancel: () => void; // Callback para cuando se cancela la edición
}

const EditPostForm: React.FC<EditPostFormProps> = ({ post, onSave, onCancel }) => {
  const { token } = useAuth();
  const [content, setContent] = useState<string>(post.content);
  const [mediaFile, setMediaFile] = useState<File | null>(null); // Estado para el nuevo archivo multimedia
  const [mediaPreview, setMediaPreview] = useState<string | null>(null); // Nuevo estado para la URL de previsualización
  const [currentMediaUrl, setCurrentMediaUrl] = useState<string | null>(post.media_url); // Para mostrar la URL actual
  const [postType, setPostType] = useState<string>(post.post_type);
  const [status, setStatus] = useState<string>(post.status);
  const [scheduledAt, setScheduledAt] = useState<string>(
    post.scheduled_at ? new Date(post.scheduled_at).toISOString().slice(0, 16) : ''
  );
  const [message, setMessage] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false); // Nuevo estado de carga

  const formatErrorMessage = (errorData: any) => {
    if (errorData && Array.isArray(errorData.detail)) {
      return errorData.detail.map((err: any) => err.msg || err.message || JSON.stringify(err)).join('; ');
    } else if (errorData && errorData.detail) {
      return errorData.detail;
    } else if (errorData && errorData.message) {
      return errorData.message;
    }
    return 'Error desconocido';
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files ? e.target.files[0] : null;
    setMediaFile(file);
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setMediaPreview(reader.result as string);
      };
      reader.readAsDataURL(file);
    } else {
      setMediaPreview(null);
    }
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setMessage('');
    setLoading(true); // Iniciar carga

    if (!token) {
      setMessage('Error: No hay token de autenticación.');
      setLoading(false);
      return;
    }

    // Validación adicional para el archivo multimedia si es obligatorio
    // Si no hay un archivo actual y no se ha seleccionado uno nuevo, mostrar error
    if (!currentMediaUrl && !mediaFile) {
      setMessage('Error: Un archivo multimedia es obligatorio para publicaciones de Instagram.');
      setLoading(false);
      return;
    }

    const formData = new FormData();
    formData.append('content', content);
    formData.append('post_type', postType);
    formData.append('status', status);
    if (scheduledAt) {
      formData.append('scheduled_at', new Date(scheduledAt).toISOString());
    }
    if (mediaFile) {
      formData.append('media_file', mediaFile);
    } else if (currentMediaUrl) {
      // Si no se sube un nuevo archivo pero hay uno existente, no hacemos nada
      // El backend mantendrá el media_url existente si media_file no se envía
    }

    try {
      const response = await fetch(`http://localhost:8000/posts/${post.id}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          // No establecer 'Content-Type', FormData lo hace automáticamente con boundary
        },
        body: formData,
      });

      if (response.ok) {
        setMessage('Publicación actualizada exitosamente!');
        onSave(); // Notificar al componente padre que se guardó
      } else {
        const errorData = await response.json();
        setMessage('Error al actualizar publicación: ' + formatErrorMessage(errorData));
      }
    } catch (error) {
      setMessage('Error de red o servidor: ' + error.message);
      console.error('Error de red o servidor:', error);
    } finally {
      setLoading(false); // Finalizar carga
    }
  };

  return (
    <div className="mt-4 p-4 bg-light rounded shadow-sm edit-post-form-card">
      <h4 className="mb-3 text-primary">Editar Publicación (ID: {post.id})</h4>
      <form onSubmit={handleSubmit}>
        <div className="mb-3">
          <textarea
            className="form-control"
            placeholder="Contenido de la publicación"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            rows={3}
            required
            disabled={loading}
          />
        </div>
        {currentMediaUrl && (
          <div className="mb-3">
            <p className="text-secondary">Medio actual: <a href={currentMediaUrl} target="_blank" rel="noopener noreferrer" className="text-primary">Ver</a></p>
          </div>
        )}
        <div className="mb-3">
          <label htmlFor="mediaFileEdit" className="form-label">Subir nueva Imagen/Video (opcional si ya hay una)</label>
          <input
            type="file"
            className="form-control"
            id="mediaFileEdit"
            onChange={handleFileChange}
            disabled={loading}
            accept="image/*,video/*" // Aceptar solo imágenes y videos
          />
          {mediaPreview && (
            <div className="mt-2 text-center">
              {mediaPreview.startsWith('data:image') ? (
                <img src={mediaPreview} alt="Previsualización" className="img-fluid rounded" style={{ maxHeight: '200px' }} />
              ) : (
                <video src={mediaPreview} controls className="img-fluid rounded" style={{ maxHeight: '200px' }} />
              )}
            </div>
          )}
        </div>
        <div className="mb-3">
          <label htmlFor="postTypeEdit" className="form-label">Tipo de Publicación</label>
          <select
            className="form-select"
            id="postTypeEdit"
            value={postType}
            onChange={(e) => setPostType(e.target.value)}
            disabled={loading}
          >
            <option value="post">Post</option>
            <option value="reel">Reel</option>
            <option value="story">Story</option>
          </select>
        </div>
        <div className="mb-3">
          <label htmlFor="statusEdit" className="form-label">Estado</label>
          <select
            className="form-select"
            id="statusEdit"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            disabled={loading}
          >
            <option value="draft">Borrador</option>
            <option value="scheduled">Programado</option>
            <option value="published">Publicado</option>
          </select>
        </div>
        <div className="mb-3">
          <label htmlFor="scheduledAtEdit" className="form-label">Programar para (opcional)</label>
          <input
            type="datetime-local"
            className="form-control"
            id="scheduledAtEdit"
            value={scheduledAt}
            onChange={(e) => setScheduledAt(e.target.value)}
            disabled={loading}
          />
        </div>
        <div className="d-flex justify-content-end mt-3">
          <button type="submit" className="btn btn-success me-2" disabled={loading}>
            {loading ? (
              <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
            ) : (
              'Guardar Cambios'
            )}
          </button>
          <button type="button" onClick={onCancel} className="btn btn-secondary" disabled={loading}>
            Cancelar
          </button>
        </div>
      </form>
      {message && (
        <p className={`mt-3 text-center ${message.startsWith('Error') ? 'text-danger' : 'text-success'}`}>
          {message}
        </p>
      )}
    </div>
  );
};

export default EditPostForm;