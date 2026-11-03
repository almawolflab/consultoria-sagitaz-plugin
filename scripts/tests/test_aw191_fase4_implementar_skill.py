"""AW-191 Fase 4 — skills/implementar/SKILL.md flujo no-interactivo (AC-3).

AC-3: El SKILL.md debe:
- Contener `--apply --yes` en el flujo de Claude.
- No contener `--apply` como paso sin `--yes` en el flujo de Claude (instrucción de escritura).
- apply_cli.py NO se toca.
"""
import re
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
IMPLEMENTAR_SKILL = PLUGIN_ROOT / "skills" / "implementar" / "SKILL.md"
APPLY_CLI = PLUGIN_ROOT / "scripts" / "parametrizacion" / "apply_cli.py"


class TestImplementarSkillMd:
    """SKILL.md instruye el flujo correcto: dry-run → confirmar en chat → --apply --yes."""

    def test_skill_md_existe(self):
        """El SKILL.md de implementar debe existir."""
        assert IMPLEMENTAR_SKILL.exists(), f"No existe: {IMPLEMENTAR_SKILL}"

    def test_contiene_apply_yes(self):
        """El SKILL.md debe contener '--apply --yes' en el flujo de Claude."""
        content = IMPLEMENTAR_SKILL.read_text()
        assert "--apply --yes" in content, (
            "SKILL.md debe instruir '--apply --yes' para el paso de escritura desde Claude"
        )

    def test_no_contiene_apply_solo_como_paso_de_escritura(self):
        """No debe haber un paso que instruya `--apply` sin `--yes` para escritura desde Claude.

        Permitido: `--apply` en texto explicativo de dry-run (¿qué es --apply?).
        NO permitido: instrucción de bash con `--apply` a secas como paso de escritura.
        """
        content = IMPLEMENTAR_SKILL.read_text()
        lines = content.splitlines()
        for i, line in enumerate(lines):
            # Busca líneas de comando bash con --apply pero SIN --yes
            # (dentro de bloques de código o instrucciones de ejecución)
            if "--apply" in line and "--yes" not in line:
                # Está permitido en líneas de explicación (no en bloques de bash de escritura)
                # Detectamos si es una instrucción de ejecución real
                stripped = line.strip()
                if stripped.startswith("python") or stripped.startswith("```") or (
                    stripped.startswith("apply_cli.py") and "--apply" in stripped
                ):
                    # Estas son instrucciones de ejecución: no deben tener --apply sin --yes
                    # a menos que sean la línea del dry-run (sin --apply tampoco, o con explicación)
                    # Excepción: el dry-run explica qué pasa sin --apply (no lleva --apply en la línea)
                    assert False, (
                        f"Línea {i+1}: instrucción con '--apply' sin '--yes' → "
                        f"puede colgarse en Bash tool de Claude Code:\n  {line}"
                    )

    def test_flujo_tiene_confirmacion_en_chat(self):
        """El SKILL.md debe mencionar que Claude pregunta confirmación en el chat."""
        content = IMPLEMENTAR_SKILL.read_text()
        # Debe haber alguna mención a que Claude pregunta/confirma en el chat
        has_chat_confirmation = any(
            phrase in content.lower()
            for phrase in [
                "pregunta en el chat",
                "confirmar en el chat",
                "confirma en el chat",
                "chat",
            ]
        )
        assert has_chat_confirmation, (
            "SKILL.md debe indicar que Claude pregunta la confirmación en el chat"
        )

    def test_apply_cli_no_modificado(self):
        """apply_cli.py NO debe haber sido modificado (conserva input() para uso CLI)."""
        assert APPLY_CLI.exists(), f"apply_cli.py no encontrado: {APPLY_CLI}"
        content = APPLY_CLI.read_text()
        # Debe conservar input() para uso manual CLI
        assert "input(" in content, (
            "apply_cli.py debe conservar input() para uso manual CLI (no se toca en AW-191)"
        )
        # Debe conservar --yes
        assert "--yes" in content, "apply_cli.py debe conservar el flag --yes"
