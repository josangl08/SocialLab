-- Migración 019: Políticas RLS para posts, content_proposals, agent_logs, visual_analyses
-- Estas cuatro tablas no tenían RLS habilitado; las queries dependían
-- únicamente del filtrado por user_id/account_id en el código de la app.

-- posts: columna user_id directa
ALTER TABLE posts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS posts_user_access ON posts;
CREATE POLICY posts_user_access ON posts
FOR ALL USING (user_id = auth.uid())
WITH CHECK (user_id = auth.uid());

-- content_proposals, agent_logs, visual_analyses: solo tienen account_id,
-- propiedad resuelta vía instagram_accounts (mismo patrón que ai_strategy
-- y content_generation_queue en la migración 006)
ALTER TABLE content_proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE visual_analyses ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS content_proposals_user_access ON content_proposals;
CREATE POLICY content_proposals_user_access ON content_proposals
FOR ALL USING (
  account_id IN (SELECT id FROM instagram_accounts WHERE user_id = auth.uid())
);

DROP POLICY IF EXISTS agent_logs_user_access ON agent_logs;
CREATE POLICY agent_logs_user_access ON agent_logs
FOR ALL USING (
  account_id IN (SELECT id FROM instagram_accounts WHERE user_id = auth.uid())
);

DROP POLICY IF EXISTS visual_analyses_user_access ON visual_analyses;
CREATE POLICY visual_analyses_user_access ON visual_analyses
FOR ALL USING (
  account_id IN (SELECT id FROM instagram_accounts WHERE user_id = auth.uid())
);
