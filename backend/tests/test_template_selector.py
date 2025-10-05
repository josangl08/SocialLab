"""
Test del Template Selector Service.

Este script:
1. Actualiza templates con selection_rules apropiadas
2. Prueba el selector con diferentes tipos de metadata
3. Verifica que seleccione el template correcto
"""

import logging
from database.supabase_client import get_supabase_admin_client
from services.template_selector import get_template_selector

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def update_template_rules():
    """Actualiza templates con selection_rules inteligentes."""
    supabase = get_supabase_admin_client()

    logger.info("\n" + "="*60)
    logger.info("ACTUALIZANDO SELECTION RULES")
    logger.info("="*60 + "\n")

    # Mapeo de templates → reglas
    template_rules = {
        'player_stats_modern_blue.png': {
            'selection_rules': {
                'export_types': ['player'],
                'positions': ['Forward', 'Midfielder', 'Defender', 'Goalkeeper']
            },
            'description': 'Template moderno azul para stats de jugadores'
        },
        'player_stats_dark_elegant.png': {
            'selection_rules': {
                'export_types': ['player'],
                'min_goals': 5  # Para jugadores destacados
            },
            'description': 'Template elegante para jugadores estrella'
        },
        'team_performance_gradient.png': {
            'selection_rules': {
                'export_types': ['team']
            },
            'description': 'Template para estadísticas de equipos'
        },
        'match_result_victory_green.png': {
            'selection_rules': {
                'export_types': ['match'],
                'match_status': ['finished'],
                'winners': ['home']  # Solo victorias locales
            },
            'description': 'Template verde para victorias en casa'
        },
        'story_player_highlight.png': {
            'selection_rules': {
                'export_types': ['player'],
                'contexts': ['highlight', 'best_moment']
            },
            'description': 'Template vertical 9:16 para Stories de jugadores'
        }
    }

    updated = 0
    for name, data in template_rules.items():
        try:
            result = supabase.table('templates').update({
                'selection_rules': data['selection_rules'],
                'description': data['description']
            }).eq('name', name).execute()

            if result.data:
                logger.info(f"✅ {name}")
                logger.info(f"   Reglas: {data['selection_rules']}")
                updated += 1
        except Exception as e:
            logger.error(f"❌ Error actualizando {name}: {str(e)}")

    logger.info(f"\n✅ {updated} templates actualizados con reglas\n")


def test_template_selection():
    """Prueba el selector con diferentes metadatas."""
    supabase = get_supabase_admin_client()
    selector = get_template_selector(supabase)

    # Obtener user_id
    result = supabase.table('posts').select('user_id').limit(1).execute()
    user_id = result.data[0]['user_id'] if result.data else None

    if not user_id:
        logger.error("No se encontró user_id")
        return

    logger.info("="*60)
    logger.info("PROBANDO TEMPLATE SELECTOR")
    logger.info("="*60 + "\n")

    # Test 1: Player stats básico
    logger.info("📊 Test 1: Estadísticas de jugador (básico)")
    metadata1 = {
        'export_type': 'player',
        'player': {
            'name': 'Cristiano Ronaldo',
            'position': 'Forward'
        },
        'stats': {
            'goals': 3,
            'assists': 2,
            'shots': 15
        }
    }

    template1 = selector.select_template(metadata1, user_id)
    if template1:
        logger.info(f"✅ Seleccionado: {template1['name']}")
        logger.info(f"   Descripción: {template1.get('description', 'N/A')}\n")
    else:
        logger.warning("⚠️  No se seleccionó template\n")

    # Test 2: Player stats con muchos goles (debería elegir elegant)
    logger.info("📊 Test 2: Jugador estrella (10 goles)")
    metadata2 = {
        'export_type': 'player',
        'player': {
            'name': 'Lionel Messi',
            'position': 'Forward'
        },
        'stats': {
            'goals': 10,
            'assists': 7,
            'shots': 40
        }
    }

    template2 = selector.select_template(metadata2, user_id)
    if template2:
        logger.info(f"✅ Seleccionado: {template2['name']}")
        logger.info(f"   Descripción: {template2.get('description', 'N/A')}\n")

    # Test 3: Team performance
    logger.info("📊 Test 3: Estadísticas de equipo")
    metadata3 = {
        'export_type': 'team',
        'team': {
            'name': 'Real Madrid',
            'id': 'real_madrid'
        },
        'stats': {
            'wins': 12,
            'draws': 3,
            'losses': 2,
            'points': 39
        }
    }

    template3 = selector.select_template(metadata3, user_id)
    if template3:
        logger.info(f"✅ Seleccionado: {template3['name']}")
        logger.info(f"   Descripción: {template3.get('description', 'N/A')}\n")

    # Test 4: Match result (victoria local)
    logger.info("📊 Test 4: Resultado de partido (victoria local)")
    metadata4 = {
        'export_type': 'match',
        'match': {
            'home_team': {'name': 'Barcelona', 'id': 'barcelona'},
            'away_team': {'name': 'Valencia', 'id': 'valencia'},
            'score': '3-1',
            'status': 'finished',
            'winner': 'home'
        }
    }

    template4 = selector.select_template(metadata4, user_id)
    if template4:
        logger.info(f"✅ Seleccionado: {template4['name']}")
        logger.info(f"   Descripción: {template4.get('description', 'N/A')}\n")

    # Test 5: Player highlight para Story
    logger.info("📊 Test 5: Highlight de jugador (para Story)")
    metadata5 = {
        'export_type': 'player',
        'context': 'highlight',
        'player': {
            'name': 'Kylian Mbappé',
            'position': 'Forward'
        },
        'stats': {
            'goals': 2,
            'assists': 1
        }
    }

    template5 = selector.select_template(metadata5, user_id)
    if template5:
        logger.info(f"✅ Seleccionado: {template5['name']}")
        logger.info(f"   Descripción: {template5.get('description', 'N/A')}\n")

    logger.info("="*60)
    logger.info("TESTS COMPLETADOS")
    logger.info("="*60)


def main():
    """Ejecutar tests."""
    print("\n" + "🚀 "*30)
    print("TEST TEMPLATE SELECTOR SERVICE")
    print("🚀 "*30 + "\n")

    # Paso 1: Actualizar reglas
    update_template_rules()

    # Paso 2: Probar selector
    test_template_selection()


if __name__ == '__main__':
    main()
