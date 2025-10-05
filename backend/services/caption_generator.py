"""
Caption Generator Service
Generación de captions para Instagram usando Google Gemini AI.
"""

import logging
import os
import google.generativeai as genai
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class CaptionGeneratorService:
    """Servicio para generar captions con IA."""

    def __init__(self):
        """Inicializa el generador de captions."""
        api_key = os.getenv('GOOGLE_API_KEY')

        if not api_key:
            raise Exception(
                "GOOGLE_API_KEY no configurada. "
                "Necesaria para generar captions con IA."
            )

        # Configurar Gemini
        genai.configure(api_key=api_key)
        # Usar Gemini 2.0 Flash (rápido y gratuito)
        self.model = genai.GenerativeModel('gemini-2.0-flash')

        logger.info("✅ Gemini AI configurado correctamente")

    def generate_caption(
        self,
        metadata: Dict,
        tone: str = 'energetic',
        language: str = 'es',
        max_hashtags: int = 7,
        custom_instructions: Optional[str] = None
    ) -> Optional[str]:
        """
        Genera caption para Instagram basado en metadata de PROJECT 1.

        Args:
            metadata: Metadata del export (export_type, player, stats, etc)
            tone: Tono del caption ('energetic', 'professional', 'casual')
            language: Idioma ('es', 'en')
            max_hashtags: Máximo número de hashtags
            custom_instructions: Instrucciones personalizadas adicionales

        Returns:
            Caption generado o None si falla
        """
        try:
            # Construir prompt basado en metadata
            prompt = self._build_prompt(
                metadata,
                tone,
                language,
                max_hashtags,
                custom_instructions
            )

            logger.info("🤖 Generando caption con Gemini...")
            logger.debug(f"Prompt: {prompt[:200]}...")

            # Generar con Gemini
            response = self.model.generate_content(prompt)
            caption = response.text.strip()

            logger.info(f"✅ Caption generado ({len(caption)} caracteres)")
            return caption

        except Exception as e:
            logger.error(f"❌ Error generando caption: {str(e)}")
            return None

    def _build_prompt(
        self,
        metadata: Dict,
        tone: str,
        language: str,
        max_hashtags: int,
        custom_instructions: Optional[str]
    ) -> str:
        """
        Construye prompt para Gemini basado en metadata.

        Args:
            metadata: Metadata del export
            tone: Tono del caption
            language: Idioma
            max_hashtags: Máximo hashtags
            custom_instructions: Instrucciones custom

        Returns:
            Prompt completo para Gemini
        """
        export_type = metadata.get('export_type', 'unknown')

        # Base del prompt
        prompt = f"""Eres un community manager experto en contenido deportivo para Instagram.

Genera un caption atractivo en {language} con tono {tone} para una publicación de Instagram.

"""

        # Añadir contexto según tipo de export
        if export_type == 'player':
            prompt += self._build_player_context(metadata)

        elif export_type == 'team':
            prompt += self._build_team_context(metadata)

        elif export_type == 'match':
            prompt += self._build_match_context(metadata)

        elif export_type == 'competition':
            prompt += self._build_competition_context(metadata)

        # Instrucciones de formato
        prompt += f"""
INSTRUCCIONES:
- Tono: {tone}
- Idioma: {language}
- Máximo {max_hashtags} hashtags relevantes
- Longitud ideal: 100-150 caracteres
- Incluir emojis apropiados
- Enfoque en engagement y viralidad
- No uses comillas al inicio ni final del caption
"""

        # Instrucciones personalizadas
        if custom_instructions:
            prompt += f"\nINSTRUCCIONES ADICIONALES:\n{custom_instructions}\n"

        return prompt

    def _build_player_context(self, metadata: Dict) -> str:
        """Construye contexto para stats de jugador."""
        player = metadata.get('player', {})
        stats = metadata.get('stats', {})

        context = f"""
TIPO: Estadísticas de jugador

JUGADOR:
- Nombre: {player.get('name', 'Jugador')}
- Posición: {player.get('position', 'N/A')}

ESTADÍSTICAS:
"""
        for key, value in stats.items():
            context += f"- {key}: {value}\n"

        return context

    def _build_team_context(self, metadata: Dict) -> str:
        """Construye contexto para stats de equipo."""
        team = metadata.get('team', {})
        stats = metadata.get('stats', {})

        context = f"""
TIPO: Estadísticas de equipo

EQUIPO:
- Nombre: {team.get('name', 'Equipo')}

ESTADÍSTICAS:
"""
        for key, value in stats.items():
            context += f"- {key}: {value}\n"

        return context

    def _build_match_context(self, metadata: Dict) -> str:
        """Construye contexto para resultado de partido."""
        match = metadata.get('match', {})

        home = match.get('home_team', {})
        away = match.get('away_team', {})

        context = f"""
TIPO: Resultado de partido

PARTIDO:
- Local: {home.get('name', 'Equipo Local')}
- Visitante: {away.get('name', 'Equipo Visitante')}
- Marcador: {match.get('score', 'N/A')}
- Estado: {match.get('status', 'N/A')}
"""

        if match.get('winner'):
            context += f"- Ganador: {match['winner']}\n"

        return context

    def _build_competition_context(self, metadata: Dict) -> str:
        """Construye contexto para competición/tabla."""
        competition = metadata.get('competition', {})

        context = f"""
TIPO: Tabla de competición

COMPETICIÓN:
- Nombre: {competition.get('name', 'Competición')}
"""
        return context

    def generate_caption_fallback(self, metadata: Dict) -> str:
        """
        Genera caption básico sin IA (fallback).

        Args:
            metadata: Metadata del export

        Returns:
            Caption básico
        """
        export_type = metadata.get('export_type', 'content')

        if export_type == 'player':
            player = metadata.get('player', {})
            name = player.get('name', 'Jugador')
            return f"📊 Estadísticas de {name} #Football #Stats #Soccer"

        elif export_type == 'team':
            team = metadata.get('team', {})
            name = team.get('name', 'Equipo')
            return f"📈 Performance de {name} #TeamStats #Football"

        elif export_type == 'match':
            match = metadata.get('match', {})
            score = match.get('score', 'Resultado')
            return f"⚽ {score} #MatchResult #Football #Soccer"

        else:
            return f"📊 {export_type.title()} #Football #Stats"


def get_caption_generator() -> CaptionGeneratorService:
    """Factory function para obtener generador de captions."""
    return CaptionGeneratorService()


def generate_caption(
    prompt: str,
    model_name: str = 'gemini-2.0-flash'
) -> Optional[str]:
    """
    Función helper para generar caption con prompt directo.

    Args:
        prompt: Prompt directo para Gemini
        model_name: Nombre del modelo a usar

    Returns:
        Caption generado o None
    """
    try:
        api_key = os.getenv('GOOGLE_API_KEY')

        if not api_key:
            logger.error("GOOGLE_API_KEY no configurada")
            return None

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)

        response = model.generate_content(prompt)
        return response.text.strip()

    except Exception as e:
        logger.error(f"❌ Error generando caption: {str(e)}")
        return None


# Testing
if __name__ == '__main__':
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    generator = get_caption_generator()

    print("\n" + "🤖 "*30)
    print("TEST CAPTION GENERATOR")
    print("🤖 "*30 + "\n")

    # Test 1: Player stats
    print("📊 Test 1: Player Stats\n")
    metadata1 = {
        'export_type': 'player',
        'player': {
            'name': 'Cristiano Ronaldo',
            'position': 'Forward'
        },
        'stats': {
            'goals': 15,
            'assists': 8,
            'shots': 67,
            'pass_accuracy': '87%'
        }
    }

    caption1 = generator.generate_caption(metadata1, tone='energetic')
    if caption1:
        print(f"Caption generado:\n{caption1}\n")
        print(f"Longitud: {len(caption1)} caracteres\n")

    # Test 2: Match result
    print("⚽ Test 2: Match Result\n")
    metadata2 = {
        'export_type': 'match',
        'match': {
            'home_team': {'name': 'Barcelona'},
            'away_team': {'name': 'Real Madrid'},
            'score': '2-1',
            'status': 'finished',
            'winner': 'home'
        }
    }

    caption2 = generator.generate_caption(metadata2, tone='professional')
    if caption2:
        print(f"Caption generado:\n{caption2}\n")
        print(f"Longitud: {len(caption2)} caracteres\n")

    print("="*60)
    print("TESTS COMPLETADOS")
    print("="*60)
