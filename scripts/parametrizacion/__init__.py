"""Paquete parametrizacion para plugin-claude/scripts/.

Cherry-pick determinista de:
- pipeline/parametrizacion/ : crm, discovery, applicator, ir, summary
- catalyst/appsail-worker/parametrizacion/ : generador_plantilla, plantilla_io, plantilla_a_ir

Archivos NO portados (dependen de un modelo externo; en el plugin razona Claude):
mapper, reviewer, mapear, revisar, _model.
"""
