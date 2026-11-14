"""Reglas de negocio y cálculo de GUIOS PRO (§4.1-§4.10).

Funciones puras: sin ORM, sin vistas, sin acceso a datos.
"""

from decimal import ROUND_HALF_UP, Decimal

ESCALA = {1: "Irrelevante", 2: "Opcional", 3: "Importante", 4: "Fundamental"}

# MATRIZ[ID][IS] -> IR   (ID: importancia del decisor; IS: importancia sugerida)
MATRIZ = {
    4: {1: 2, 2: 3, 3: 3, 4: 4},
    3: {1: 2, 2: 2, 3: 3, 4: 3},
    2: {1: 1, 2: 2, 3: 2, 4: 3},
    1: {1: 1, 2: 1, 3: 2, 4: 2},
}

RA = (
    "Recomendación A: Adoptar. Todos los factores relevantes han sido "
    "identificados como Oportunidades y/o Fortalezas. Esto quiere decir "
    "que la organización cumple satisfactoriamente con la mayoría de "
    "requisitos para adoptar la solución."
)

RB = (
    "Recomendación B: Adoptar con matices. Es posible adoptar. A pesar de que se han "
    "detectado amenazas y/o debilidades, estas corresponden a factores cuya importancia "
    "relativa es opcional; por lo tanto, se sugiere revisar los criterios que no cumplen "
    "con lo mínimo requerido para adoptar."
)

RC = (
    "Recomendación C: Analizar y posponer la adopción. Se han detectado debilidades "
    "y/o amenazas en factores cuya importancia relativa es importante o fundamental. "
    "Se sugiere analizar estos factores y posponer la adopción hasta resolverlos."
)

TEXTOS_RECOMENDACION = {"A": RA, "B": RB, "C": RC}

MENSAJE_EMPATE = (
    "Las evaluaciones están empatadas: cualquiera de las alternativas puede adoptarse"
)

ORDEN = {"A": 0, "B": 1, "C": 2}


def importancia_relativa(id_decisor, is_sugerida):
    return MATRIZ[id_decisor][is_sugerida]


def es_relevante(ir):
    return ir > 1


def resumen_factor(calificaciones):
    """calificaciones: lista de enteros 1..4 de los subfactores del factor."""
    n = len(calificaciones)
    suma = sum(calificaciones)
    pm = Decimal(suma) / Decimal(n)  # solo para mostrar (2 decimales)
    cumple = suma >= 3 * n  # equivale a PM >= 3, sin redondeo
    return pm, cumple


def formatear_pm(pm):
    """Muestra la PM con 2 decimales y coma decimal (p. ej. "2,88")."""
    redondeada = pm.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{redondeada:.2f}".replace(".", ",")


def clasificar_foda(cumple, alcance):  # alcance: "interno" | "externo"
    if alcance == "interno":
        return "Fortaleza" if cumple else "Debilidad"
    return "Oportunidad" if cumple else "Amenaza"


def recomendar(factores_relevantes):
    """Cada factor debe tener .foda y .importancia_relativa"""
    problemas = [f for f in factores_relevantes if f.foda in ("Debilidad", "Amenaza")]
    if not problemas:
        return "A"
    if all(f.importancia_relativa == 2 for f in problemas):
        return "B"
    return "C"


def clave_comparacion(ev):
    """Menor clave = mejor. ev.recomendacion y ev.num_problemas."""
    return (ORDEN[ev.recomendacion], ev.num_problemas)


def comparar(evaluaciones):
    ordenadas = sorted(evaluaciones, key=clave_comparacion)
    mejores = [
        e for e in ordenadas if clave_comparacion(e) == clave_comparacion(ordenadas[0])
    ]
    return ordenadas, mejores  # len(mejores) > 1  ->  empate


# ---------- Importancia sugerida desde la literatura (doc/sugerida.pdf, Tablas 12-17) ----------

def cortes_cuartiles(valores):
    """Cortes rq1..rq4 con el mismo método que CUARTIL.INC de Excel.

    Posición (base 1) = 1 + (n - 1) * k / 4; si cae entre dos valores se interpola.
    """
    ordenados = sorted(Decimal(v) for v in valores)
    n = len(ordenados)
    if n < 2:
        raise ValueError("Se necesitan al menos dos factores para calcular cuartiles.")
    cortes = []
    for k in (1, 2, 3, 4):
        posicion = Decimal(n - 1) * k / 4  # base 0
        inferior = int(posicion)
        fraccion = posicion - inferior
        if inferior + 1 < n:
            valor = ordenados[inferior] + fraccion * (ordenados[inferior + 1] - ordenados[inferior])
        else:
            valor = ordenados[inferior]
        cortes.append(valor)
    return tuple(cortes)


def importancia_literatura(r, cortes):
    """IL de 1 a 4. Un valor igual a un corte va al cuartil inferior (regla «menor o igual»)."""
    rq1, rq2, rq3, _ = cortes
    if r <= rq1:
        return 1
    if r <= rq2:
        return 2
    if r <= rq3:
        return 3
    return 4


def importancia_sugerida(importancia_experto, importancia_lectura):
    """IS = MATRIZ[IE][IL] (Tabla 12): la misma matriz que combina dos niveles de importancia."""
    if importancia_experto not in MATRIZ or importancia_lectura not in MATRIZ:
        raise ValueError("IE e IL deben estar entre 1 y 4.")
    return MATRIZ[importancia_experto][importancia_lectura]


def calcular_importancia_sugerida(conteos, importancia_experto):
    """conteos: {factor: (NS, TC)}. Devuelve {factor: {"ns", "tc", "r", "il", "is"}} y aplica los 5 pasos."""
    razones = {factor: Decimal(tc) / Decimal(ns) for factor, (ns, tc) in conteos.items()}
    cortes = cortes_cuartiles(razones.values())
    resultado = {}
    for factor, (ns, tc) in conteos.items():
        il = importancia_literatura(razones[factor], cortes)
        resultado[factor] = {
            "ns": ns,
            "tc": tc,
            "r": razones[factor],
            "il": il,
            "is": importancia_sugerida(importancia_experto, il),
        }
    return resultado
