"""
Template Selector Service
Selección inteligente y flexible de templates basada en metadata.json de PROJECT 1.
"""

import logging
from typing import Dict, List, Optional
from supabase import Client

logger = logging.getLogger(__name__)


class TemplateSelectorService:
    """Servicio para selección flexible de templates."""

    def __init__(self, supabase_client: Client):
        """
        Inicializa el selector de templates.

        Args:
            supabase_client: Cliente de Supabase
        """
        self.supabase = supabase_client

    def select_template(
        self,
        metadata: Dict,
        user_id: str,
        instagram_account_id: Optional[int] = None
    ) -> Optional[Dict]:
        """
        Selecciona el mejor template basado en metadata de PROJECT 1.

        Args:
            metadata: Metadata.json del export de PROJECT 1
            user_id: UUID del usuario
            instagram_account_id: ID de cuenta Instagram (opcional)

        Returns:
            Template seleccionado o None
        """
        try:
            # 1. Extraer export_type
            export_type = metadata.get('export_type')

            if not export_type:
                logger.error("metadata.json sin export_type")
                return None

            logger.info(f"🔍 Buscando template para export_type: {export_type}")

            # 2. Buscar templates compatibles
            query = self.supabase.table('templates').select(
                '*',
                'template_categories(name)'
            ).eq('user_id', user_id).eq('is_active', True)

            # Filtrar por cuenta si se especifica
            if instagram_account_id:
                query = query.or_(
                    f'instagram_account_id.eq.{instagram_account_id},'
                    f'instagram_account_id.is.null'
                )

            # Ordenar por prioridad
            query = query.order('priority', desc=True)

            result = query.execute()
            templates = result.data

            if not templates:
                logger.warning(f"⚠️  No hay templates activos para {user_id}")
                return None

            # 3. Filtrar templates aplicables
            applicable_templates = []

            for template in templates:
                if self._is_template_applicable(template, metadata):
                    applicable_templates.append(template)

            if not applicable_templates:
                logger.warning(
                    f"⚠️  Ningún template cumple las reglas para {export_type}"
                )
                # Fallback: retornar el de mayor prioridad genérico
                return templates[0]

            # 4. Seleccionar el de mayor prioridad
            selected = applicable_templates[0]

            logger.info(
                f"✅ Template seleccionado: {selected['name']} "
                f"(prioridad: {selected['priority']})"
            )

            return selected

        except Exception as e:
            logger.error(f"❌ Error seleccionando template: {str(e)}")
            return None

    def _is_template_applicable(
        self,
        template: Dict,
        metadata: Dict
    ) -> bool:
        """
        Verifica si un template es aplicable al metadata dado.

        Args:
            template: Template a evaluar
            metadata: Metadata del export

        Returns:
            True si el template es aplicable
        """
        export_type = metadata.get('export_type')

        # 1. Verificar si el template tiene reglas de selección
        selection_rules = template.get('selection_rules', {})

        # Si no hay reglas, el template es aplicable a todo
        if not selection_rules:
            return True

        # 2. Verificar export_type compatible
        if 'export_types' in selection_rules:
            compatible_types = selection_rules['export_types']
            if export_type not in compatible_types:
                return False

        # 3. Verificar reglas específicas por tipo
        if export_type == 'player':
            return self._check_player_rules(selection_rules, metadata)

        elif export_type == 'team':
            return self._check_team_rules(selection_rules, metadata)

        elif export_type == 'match':
            return self._check_match_rules(selection_rules, metadata)

        elif export_type == 'competition':
            return self._check_competition_rules(selection_rules, metadata)

        return True

    def _check_player_rules(
        self,
        rules: Dict,
        metadata: Dict
    ) -> bool:
        """Verifica reglas específicas para export_type='player'."""
        stats = metadata.get('stats', {})

        # Regla: min_goals
        if 'min_goals' in rules:
            if stats.get('goals', 0) < rules['min_goals']:
                return False

        # Regla: min_assists
        if 'min_assists' in rules:
            if stats.get('assists', 0) < rules['min_assists']:
                return False

        # Regla: position
        if 'positions' in rules:
            player_position = metadata.get('player', {}).get('position')
            if player_position not in rules['positions']:
                return False

        # Regla: context
        if 'contexts' in rules:
            if metadata.get('context') not in rules['contexts']:
                return False

        return True

    def _check_team_rules(
        self,
        rules: Dict,
        metadata: Dict
    ) -> bool:
        """Verifica reglas específicas para export_type='team'."""
        stats = metadata.get('stats', {})

        # Regla: min_wins
        if 'min_wins' in rules:
            if stats.get('wins', 0) < rules['min_wins']:
                return False

        # Regla: min_points (si aplica)
        if 'min_points' in rules:
            if stats.get('points', 0) < rules['min_points']:
                return False

        # Regla: team específico
        if 'team_ids' in rules:
            team_id = metadata.get('team', {}).get('id')
            if team_id not in rules['team_ids']:
                return False

        return True

    def _check_match_rules(
        self,
        rules: Dict,
        metadata: Dict
    ) -> bool:
        """Verifica reglas específicas para export_type='match'."""
        match = metadata.get('match', {})

        # Regla: match_status
        if 'match_status' in rules:
            if match.get('status') not in rules['match_status']:
                return False

        # Regla: winner (para resultados)
        if 'winners' in rules:
            if match.get('winner') not in rules['winners']:
                return False

        # Regla: rivalry/derby (basado en teams)
        if 'is_derby' in rules and rules['is_derby']:
            # Detectar derbies comunes
            home = match.get('home_team', {}).get('id', '')
            away = match.get('away_team', {}).get('id', '')

            # Lista de derbies conocidos (expandible)
            derbies = [
                ('real_madrid', 'barcelona'),
                ('barcelona', 'real_madrid'),
                ('manchester_united', 'manchester_city'),
                ('liverpool', 'everton'),
            ]

            is_derby = (home, away) in derbies
            if not is_derby:
                return False

        return True

    def _check_competition_rules(
        self,
        rules: Dict,
        metadata: Dict
    ) -> bool:
        """Verifica reglas específicas para export_type='competition'."""

        # Regla: competition_id específico
        if 'competition_ids' in rules:
            comp_id = metadata.get('competition', {}).get('id')
            if comp_id not in rules['competition_ids']:
                return False

        return True

    def get_templates_by_export_type(
        self,
        export_type: str,
        user_id: str
    ) -> List[Dict]:
        """
        Obtiene templates compatibles con un export_type.

        Args:
            export_type: Tipo de export (player/team/match/competition)
            user_id: UUID del usuario

        Returns:
            Lista de templates compatibles
        """
        try:
            result = self.supabase.table('templates').select('*').eq(
                'user_id', user_id
            ).eq('is_active', True).order('priority', desc=True).execute()

            templates = result.data

            # Filtrar por export_type si el template tiene reglas
            compatible = []
            for template in templates:
                rules = template.get('selection_rules', {})

                # Si no tiene reglas o incluye este export_type
                if not rules or export_type in rules.get('export_types', [export_type]):
                    compatible.append(template)

            return compatible

        except Exception as e:
            logger.error(f"❌ Error obteniendo templates: {str(e)}")
            return []

    def get_template_stats(self, user_id: str) -> Dict:
        """
        Obtiene estadísticas de uso de templates.

        Args:
            user_id: UUID del usuario

        Returns:
            Diccionario con estadísticas
        """
        try:
            # Templates totales
            total = self.supabase.table('templates').select(
                'id', count='exact'
            ).eq('user_id', user_id).execute()

            # Templates activos
            active = self.supabase.table('templates').select(
                'id', count='exact'
            ).eq('user_id', user_id).eq('is_active', True).execute()

            # Template más usado
            most_used = self.supabase.table('templates').select(
                'name, use_count'
            ).eq('user_id', user_id).order(
                'use_count', desc=True
            ).limit(1).execute()

            return {
                'total_templates': total.count,
                'active_templates': active.count,
                'most_used': most_used.data[0] if most_used.data else None
            }

        except Exception as e:
            logger.error(f"❌ Error obteniendo stats: {str(e)}")
            return {}


def get_template_selector(supabase_client: Client) -> TemplateSelectorService:
    """Factory function para obtener selector de templates."""
    return TemplateSelectorService(supabase_client)


# Testing
if __name__ == '__main__':
    import os
    import json
    from supabase import create_client
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    # Setup
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    supabase = create_client(supabase_url, supabase_key)

    # Test con metadata de ejemplo
    selector = get_template_selector(supabase)

    # Metadata de prueba: Player con hatrick
    test_metadata = {
        "export_id": "2025-01-15_player_ronaldo_hatrick_001",
        "export_type": "player",
        "competition": {
            "id": "saudi_pro_league_2024",
            "name": "Saudi Pro League"
        },
        "team": {
            "id": "al_nassr",
            "name": "Al Nassr"
        },
        "player": {
            "id": "ronaldo_cr7",
            "name": "Cristiano Ronaldo",
            "position": "Forward"
        },
        "context": "match",
        "stats": {
            "goals": 3,
            "assists": 1
        }
    }

    print("\n🎯 Seleccionando template para metadata de prueba...")
    print(json.dumps(test_metadata, indent=2))

    template = selector.select_template(
        metadata=test_metadata,
        user_id='test-user-id'
    )

    if template:
        print(f"\n✅ Template seleccionado: {template['name']}")
        print(f"   Prioridad: {template['priority']}")
        print(f"   Reglas: {template.get('selection_rules', {})}")
    else:
        print("\n❌ No se encontró template")

    # Estadísticas
    print("\n📊 Estadísticas de templates:")
    stats = selector.get_template_stats('test-user-id')
    for key, value in stats.items():
        print(f"   {key}: {value}")
