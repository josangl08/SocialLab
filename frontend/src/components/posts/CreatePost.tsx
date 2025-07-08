import React, { useState, FormEvent } from 'react';
import { useAuth } from '../../context/AuthContext'; // Ruta corregida
import './CreatePost.css';

interface CreatePostProps {
  onPostCreated: () => void; // Callback para notificar que una publicación ha sido creada
}

const CreatePost: React.FC<CreatePostProps> = ({ onPostCreated }) => {
  const { token } = useAuth();
  const [content, setContent] = useState<string>('');
  const [mediaFile, setMediaFile] = useState<File | null>(null); // Estado para el archivo multimedia
  const [mediaPreview, setMediaPreview] = useState<string | null>(null); // Nuevo estado para la URL de previsualización
  const [postType, setPostType] = useState<string>('post'); // Default to 'post'
  const [status, setStatus] = useState<string>('draft'); // Default to 'draft'
  const [scheduledAt, setScheduledAt] = useState<string>('');
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
    if (!mediaFile) {
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
    formData.append('media_file', mediaFile); // El archivo ahora es obligatorio

    try {
      const response = await fetch('http://localhost:8000/posts', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          // No establecer 'Content-Type', FormData lo hace automáticamente con boundary
        },
        body: formData,
      });

      if (response.ok) {
        const data = await response.json();
        setMessage('Publicación creada exitosamente!');
        setContent('');
        setMediaFile(null); // Limpiar el input de archivo
        setMediaPreview(null); // Limpiar la previsualización
        (event.target as HTMLFormElement).reset(); // Resetear el formulario completo
        setPostType('post');
        setStatus('draft');
        setScheduledAt('');
        onPostCreated(); // Llamar al callback para refrescar la lista
      } else {
        const errorData = await response.json();
        setMessage('Error al crear publicación: ' + formatErrorMessage(errorData));
      }
    } catch (error) {
      setMessage('Error de red o servidor: ' + error.message);
      console.error('Error de red o servidor:', error);
    } finally {
      setLoading(false); // Finalizar carga
    }
  };

  return (
    <div className="mt-4 p-4 bg-light rounded shadow-sm create-post-card">
      <h3 className="mb-4 text-primary">Crear Nueva Publicación</h3>
      <form onSubmit={handleSubmit}>
        <div className="mb-3">
          <textarea
            className="form-control"
            placeholder="Contenido de la publicación"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            rows={4}
            required
            disabled={loading}
          />
        </div>
        <div className="mb-3">
          <label htmlFor="mediaFile" className="form-label">Subir Imagen/Video <span className="text-danger">*</span></label>
          <input
            type="file"
            className="form-control"
            id="mediaFile"
            onChange={handleFileChange}
            required // Ahora es obligatorio
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
          <label htmlFor="postType" className="form-label">Tipo de Publicación</label>
          <select
            className="form-select"
            id="postType"
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
          <label htmlFor="status" className="form-label">Estado</label>
          <select
            className="form-select"
            id="status"
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
          <label htmlFor="scheduledAt" className="form-label">Programar para (opcional)</label>
          <input
            type="datetime-local"
            className="form-control"
            id="scheduledAt"
            value={scheduledAt}
            onChange={(e) => setScheduledAt(e.target.value)}
            disabled={loading}
          />
        </div>
        <button type="submit" className="btn btn-primary w-100" disabled={loading}>
            {loading ? (
              <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
            ) : (
              'Crear Publicación'
            )}
        </button>
      </form>
      {message && (
        <p className={`mt-3 text-center ${message.startsWith('Error') ? 'text-danger' : 'text-success'}`}>
          {message}
        </p>
      )}
    </div>
  );
};

export default CreatePost;
