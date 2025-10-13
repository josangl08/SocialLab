-- Migración 007: Agregar políticas RLS para instagram_accounts
-- Permite que los usuarios gestionen sus propias cuentas de Instagram

-- Habilitar RLS en la tabla
ALTER TABLE instagram_accounts ENABLE ROW LEVEL SECURITY;

-- Política para SELECT: Los usuarios solo pueden ver sus propias cuentas
CREATE POLICY "Users can view their own Instagram accounts"
ON instagram_accounts
FOR SELECT
USING (auth.uid() = user_id);

-- Política para INSERT: Los usuarios solo pueden insertar sus propias cuentas
CREATE POLICY "Users can insert their own Instagram accounts"
ON instagram_accounts
FOR INSERT
WITH CHECK (auth.uid() = user_id);

-- Política para UPDATE: Los usuarios solo pueden actualizar sus propias cuentas
CREATE POLICY "Users can update their own Instagram accounts"
ON instagram_accounts
FOR UPDATE
USING (auth.uid() = user_id)
WITH CHECK (auth.uid() = user_id);

-- Política para DELETE: Los usuarios solo pueden eliminar sus propias cuentas
CREATE POLICY "Users can delete their own Instagram accounts"
ON instagram_accounts
FOR DELETE
USING (auth.uid() = user_id);
